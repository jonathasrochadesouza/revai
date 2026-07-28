"""Phase 0 acceptance tests.

These assert the contract the web app depends on, so a breaking change to the
health payload fails here rather than in the browser.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from revai.config import Settings, get_settings
from revai.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """A client backed by a throwaway data directory.

    Overriding the settings dependency keeps the real ``~/.revai`` untouched.
    """
    get_settings.cache_clear()

    def _settings() -> Settings:
        return Settings(data_dir=tmp_path / ".revai", environment="test")

    app = create_app()
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app)


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "RevAI Platform"
    assert body["version"]


def test_runtime_reports_the_overridden_data_dir(client: TestClient, tmp_path: Path) -> None:
    response = client.get("/api/runtime")

    assert response.status_code == 200
    body = response.json()
    assert str(tmp_path) in body["data_dir"]
    assert body["python_version"].startswith("3.")


def test_openapi_schema_is_generated(client: TestClient) -> None:
    """The web app generates its types from this schema, so it must be valid."""
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/health" in schema["paths"]


def test_ensure_dirs_creates_the_whole_tree(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "fresh")

    settings.ensure_dirs()

    for path in (
        settings.data_dir,
        settings.projects_dir,
        settings.reviews_dir,
        settings.rules_dir,
        settings.cache_dir,
    ):
        assert path.is_dir(), f"{path} was not created"


def test_ensure_dirs_is_idempotent(tmp_path: Path) -> None:
    """Called on every start-up, so running it twice must be harmless."""
    settings = Settings(data_dir=tmp_path / "twice")

    settings.ensure_dirs()
    settings.ensure_dirs()

    assert settings.data_dir.is_dir()


def test_data_dir_is_always_absolute(tmp_path: Path) -> None:
    """Relative paths would break once the process changes directory."""
    settings = Settings(data_dir=Path("./relative-dir"))

    assert settings.data_dir.is_absolute()
