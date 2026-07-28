"""Provider discovery and verification endpoints.

Backs the **Detected providers** panel. Two properties matter here:

* **Probing never fails the request.** A broken provider is data to render, not an
  error — the panel has to show every engine, including the ones that are missing or
  misconfigured.
* **A probe never spends money.** ``GET /key`` validates an OpenRouter key without
  consuming tokens, and CLI probes only run ``--version`` and an auth check.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from revai.api.deps import ConfigRepo, CredentialsRepo
from revai.domain.enums import ProviderId, ProviderKind
from revai.providers.base import ProviderHealth
from revai.providers.registry import build_registry
from revai.storage.base import StorageError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["providers"])


class ProvidersResponse(BaseModel):
    """Every provider RevAI knows about, with its current state."""

    providers: list[ProviderHealth]
    active_provider_id: ProviderId
    active_is_usable: bool = Field(
        description="Whether a review could be started with the configured engine."
    )


def _load(config_repo: ConfigRepo, credentials_repo: CredentialsRepo):
    """Read config and credentials, translating storage faults into 422.

    Both files are hand-editable, so a parse failure is almost always a bad edit the
    user can fix — and the message names the file and field.
    """
    try:
        return config_repo.load(), credentials_repo.load()
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.get(
    "/providers",
    response_model=ProvidersResponse,
    summary="Detect and probe every provider",
)
async def list_providers(
    config_repo: ConfigRepo,
    credentials_repo: CredentialsRepo,
    kind: Annotated[
        ProviderKind | None,
        Query(description="Return only providers of this kind. Omit for all."),
    ] = None,
) -> ProvidersResponse:
    """Probe all providers concurrently.

    CLI detection runs three subprocesses, so this can take a couple of seconds on a
    cold start. It is still a single round trip rather than one request per provider,
    which keeps the panel from rendering in a staggered, flickering way.

    ``kind`` filters the list only — the sweep is always complete, because
    ``active_is_usable`` has to answer for the configured engine whatever kind it is.
    Filtering here rather than in the browser also means a ``kind=cli`` request does
    not make the caller receive, and then discard, provider records it never wanted.
    """
    config, credentials = _load(config_repo, credentials_repo)
    registry = build_registry(config, credentials)

    healths = await registry.health_all()
    active_id = config.engine.provider_id
    active = next((h for h in healths if h.provider_id == active_id), None)

    return ProvidersResponse(
        providers=[h for h in healths if kind is None or h.kind is kind],
        active_provider_id=active_id,
        active_is_usable=active.is_usable if active else False,
    )


@router.post(
    "/providers/{provider_id}/verify",
    response_model=ProviderHealth,
    summary="Re-probe a single provider",
)
async def verify_provider(
    provider_id: ProviderId,
    config_repo: ConfigRepo,
    credentials_repo: CredentialsRepo,
) -> ProviderHealth:
    """Check one provider on demand.

    Backs the **Test** button. Returns 200 with an unhealthy body rather than an
    error status: "I checked, and it is not working" is a successful check.
    """
    config, credentials = _load(config_repo, credentials_repo)
    registry = build_registry(config, credentials)

    # An implemented adapter can answer for itself.
    provider = registry.get(provider_id)
    if provider is not None:
        return await provider.health()

    # Otherwise fall back to the full sweep, which covers CLIs and planned
    # providers. Filtering here keeps a single source of truth for their states.
    healths = await registry.health_all()
    found = next((h for h in healths if h.provider_id == provider_id), None)
    if found is not None:
        return found

    # Unreachable while ProviderId stays exhaustive, but a 404 beats a 500 if a
    # member is ever added without a corresponding probe.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No probe is implemented for {provider_id.value}.",
    )
