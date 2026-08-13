"""Phase 0 acceptance tests.

These assert the contract the web app depends on, so a breaking change to the
health payload fails here rather than in the browser.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from revai.config import Settings, get_settings
from revai.domain.enums import ReviewScope, ReviewStatus
from revai.domain.models import Review
from revai.main import create_app
from revai.storage import ReviewRepository


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """A client backed by a throwaway data directory.

    Overriding the settings dependency keeps the real ``~/.revai`` untouched.
    """
    get_settings.cache_clear()

    settings = Settings(data_dir=tmp_path / ".revai", environment="test")

    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
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


def test_cors_allows_web_app_on_another_loopback_port(client: TestClient) -> None:
    response = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:3010"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3010"


def test_cors_allows_loopback_preflight_without_allowing_remote_origins(
    client: TestClient,
) -> None:
    response = client.options(
        "/api/projects/pick-folder",
        headers={
            "Origin": "http://127.0.0.1:4173",
            "Access-Control-Request-Method": "POST",
        },
    )
    remote_response = client.get(
        "/api/health",
        headers={"Origin": "https://example.com"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:4173"
    assert "access-control-allow-origin" not in remote_response.headers


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


def test_startup_marks_interrupted_jobs_as_aborted(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "restart", environment="test")
    settings.ensure_dirs()
    repository = ReviewRepository(settings)
    review = Review(
        project_id="project-1",
        scope=ReviewScope.BRANCH_DIFF,
        status=ReviewStatus.RUNNING,
    )
    repository.save(review)

    with TestClient(create_app(settings)):
        pass

    recovered = repository.get(review.id, review.project_id)
    assert recovered is not None
    assert recovered.status is ReviewStatus.ABORTED
    assert recovered.finished_at is not None
    assert "restarted" in (recovered.error or "")


def test_data_dir_is_always_absolute(tmp_path: Path) -> None:
    """Relative paths would break once the process changes directory."""
    settings = Settings(data_dir=Path("./relative-dir"))

    assert settings.data_dir.is_absolute()
