"""Aggregated connection status endpoint.

Backs both the global connection banner and the **API & AI** settings screen, so the
two can never disagree. The contract mirrors the provider endpoints: an unhealthy
component is data to render (200), while an unparseable hand-edited configuration is
a fixable user error (422).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from revai.api.deps import ConfigRepo, CredentialsRepo, SettingsDep
from revai.connection import StatusResponse, StatusService
from revai.errors import RevaiError
from revai.storage.base import StorageError

router = APIRouter(tags=["system"])


def _service(request: Request) -> StatusService:
    """One cache per application, created on first use.

    Lazily attached to ``app.state``: nothing to wire in the factory, and a
    test app starts with an empty cache.
    """
    if not hasattr(request.app.state, "status_service"):
        request.app.state.status_service = StatusService()
    return request.app.state.status_service


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Backend and AI provider status in one call",
)
async def connection_status(
    request: Request,
    settings: SettingsDep,
    config_repo: ConfigRepo,
    credentials_repo: CredentialsRepo,
    refresh: Annotated[
        bool,
        Query(description="Bypass the cache and probe again. Costs a full CLI sweep."),
    ] = False,
) -> StatusResponse:
    """Report whether a review could run right now.

    Never fails because a probed component is unhealthy: the banner and the settings
    screen exist precisely to render those states.
    """
    try:
        config, credentials = config_repo.load(), credentials_repo.load()
    except StorageError as exc:
        # Both files are hand-editable, so a parse failure names the file and field.
        raise RevaiError(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.error_key, exc.params) from exc

    return await _service(request).collect(settings, config, credentials, refresh=refresh)
