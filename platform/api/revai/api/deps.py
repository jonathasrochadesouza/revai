"""Dependency wiring.

Repositories are constructed per request. They hold no state beyond a path, so
this costs nothing and keeps test overrides trivial — replace ``get_settings`` and
every repository follows.

This module is also the seam described in the architecture plan: pointing the app
at a different backend means changing the constructors here and nothing else.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from revai.config import Settings, get_settings
from revai.pipeline.limiter import ReviewLimiter
from revai.storage.repositories import (
    ConfigRepository,
    CredentialsRepository,
    ProjectRepository,
    ReviewRepository,
)

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_config_repository(settings: SettingsDep) -> ConfigRepository:
    return ConfigRepository(settings)


def get_credentials_repository(settings: SettingsDep) -> CredentialsRepository:
    return CredentialsRepository(settings)


def get_project_repository(settings: SettingsDep) -> ProjectRepository:
    return ProjectRepository(settings)


def get_review_repository(settings: SettingsDep) -> ReviewRepository:
    return ReviewRepository(settings)


ConfigRepo = Annotated[ConfigRepository, Depends(get_config_repository)]
CredentialsRepo = Annotated[CredentialsRepository, Depends(get_credentials_repository)]
ProjectRepo = Annotated[ProjectRepository, Depends(get_project_repository)]
ReviewRepo = Annotated[ReviewRepository, Depends(get_review_repository)]


def get_review_limiter(request: Request) -> ReviewLimiter:
    return request.app.state.review_limiter


ReviewLimiterDep = Annotated[ReviewLimiter, Depends(get_review_limiter)]
