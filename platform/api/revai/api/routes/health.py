"""Health and environment inspection.

Phase 0 only. The ``/health`` endpoint is what the web app calls to prove the two
halves of the stack are talking to each other.
"""

from __future__ import annotations

import platform
import sys
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from revai.config import Settings, get_settings

router = APIRouter(tags=["system"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


class HealthResponse(BaseModel):
    """Minimal liveness payload."""

    status: Literal["ok"] = "ok"
    app: str
    version: str
    environment: str


class RuntimeInfo(BaseModel):
    """Environment details, surfaced in the UI so setup problems are visible."""

    python_version: str
    platform: str
    data_dir: str
    data_dir_exists: bool = Field(
        description="False on a fresh install until the first write happens."
    )


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(
        app=settings.app_name,
        version=settings.version,
        environment=settings.environment,
    )


@router.get("/runtime", response_model=RuntimeInfo, summary="Runtime environment")
async def runtime(settings: SettingsDep) -> RuntimeInfo:
    return RuntimeInfo(
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}"
        f".{sys.version_info.micro}",
        platform=f"{platform.system()} {platform.release()}",
        data_dir=str(settings.data_dir),
        data_dir_exists=settings.data_dir.exists(),
    )
