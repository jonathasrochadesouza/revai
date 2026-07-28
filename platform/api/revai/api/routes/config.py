"""Configuration and credential endpoints.

Two rules enforced here:

* **A secret never leaves the process.** Credential responses carry a masked
  preview and nothing else, so an API key cannot leak into a browser devtools
  panel, a log line, or a screenshot.
* **A save is all-or-nothing.** The whole config document is replaced atomically
  rather than patched field by field, which means a failed write leaves the
  previous configuration intact.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from revai.api.deps import ConfigRepo, CredentialsRepo
from revai.domain.enums import ProviderId
from revai.domain.models import Credentials, ProviderCredential, RevaiConfig
from revai.storage.base import StorageError

router = APIRouter(tags=["configuration"])


# ===========================================================================
# Config
# ===========================================================================


class ConfigResponse(BaseModel):
    """The configuration plus where it lives, so the UI can name the file."""

    config: RevaiConfig
    path: str
    exists: bool = Field(
        description="False before the first save â€” the UI shows defaults as unsaved."
    )


@router.get("/config", response_model=ConfigResponse, summary="Read configuration")
async def read_config(repo: ConfigRepo) -> ConfigResponse:
    try:
        config = repo.load()
    except StorageError as exc:
        # 422 rather than 500: the file is hand-editable, so this is almost always
        # a malformed edit the user can fix. The message names the file and field.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return ConfigResponse(config=config, path=str(repo.path), exists=repo.exists())


@router.put(
    "/config",
    response_model=ConfigResponse,
    summary="Save configuration to config.yaml",
)
async def write_config(payload: RevaiConfig, repo: ConfigRepo) -> ConfigResponse:
    """Replace ``config.yaml``.

    Backs the **Save to config.yaml** action bar. ``updated_at`` is stamped
    server-side so the timestamp reflects the write, not the client's clock.
    """
    payload.updated_at = datetime.now(UTC)

    try:
        saved = repo.save(payload)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail=str(exc)
        ) from exc

    return ConfigResponse(config=saved, path=str(repo.path), exists=True)


# ===========================================================================
# Credentials
# ===========================================================================


class CredentialSummary(BaseModel):
    """A configured credential, without the secret."""

    provider_id: ProviderId
    label: str | None = None
    masked_key: str
    created_at: datetime


class CredentialsResponse(BaseModel):
    credentials: list[CredentialSummary]
    path: str


class CredentialRequest(BaseModel):
    """Write a credential. The only place a raw key is accepted."""

    provider_id: ProviderId
    api_key: str = Field(min_length=1, repr=False)  # repr=False keeps it out of logs
    label: str | None = None


def _summarise(credentials: Credentials) -> list[CredentialSummary]:
    return [
        CredentialSummary(
            provider_id=credential.provider_id,
            label=credential.label,
            masked_key=credential.masked(),
            created_at=credential.created_at,
        )
        for credential in sorted(credentials.providers.values(), key=lambda c: c.provider_id.value)
    ]


@router.get(
    "/credentials",
    response_model=CredentialsResponse,
    summary="List configured credentials (masked)",
)
async def list_credentials(repo: CredentialsRepo) -> CredentialsResponse:
    try:
        credentials = repo.load()
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return CredentialsResponse(credentials=_summarise(credentials), path=str(repo.path))


@router.put(
    "/credentials",
    response_model=CredentialsResponse,
    summary="Store or replace a credential",
)
async def put_credential(payload: CredentialRequest, repo: CredentialsRepo) -> CredentialsResponse:
    try:
        credentials = repo.load()
        credentials.put(
            ProviderCredential(
                provider_id=payload.provider_id,
                api_key=payload.api_key,
                label=payload.label,
            )
        )
        saved = repo.save(credentials)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail=str(exc)
        ) from exc

    return CredentialsResponse(credentials=_summarise(saved), path=str(repo.path))


@router.delete(
    "/credentials/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a credential",
)
async def delete_credential(provider_id: ProviderId, repo: CredentialsRepo) -> None:
    try:
        credentials = repo.load()
        if not credentials.remove(provider_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No credential stored for {provider_id.value}",
            )
        repo.save(credentials)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail=str(exc)
        ) from exc
