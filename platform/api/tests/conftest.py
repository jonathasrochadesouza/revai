"""Shared fixtures.

Every fixture points at a temporary data directory, so no test can touch the real
``~/.revai``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from revai.config import Settings, get_settings
from revai.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings rooted in a throwaway directory, with the tree already created."""
    resolved = Settings(data_dir=tmp_path / ".revai", environment="test")
    resolved.ensure_dirs()
    return resolved


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """A client whose repositories all resolve to the temporary directory."""
    get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
