"""Phase 4 deterministic review API contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from revai.config import Settings
from revai.storage.repositories import ConfigRepository


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repository(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "phase4@example.com")
    _git(path, "config", "user.name", "Phase Four")
    source = path / "app.py"
    source.write_text("answer = 42\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "initial")
    return path


def _ruff_only(settings: Settings) -> None:
    repo = ConfigRepository(settings)
    config = repo.load()
    config.analyzers.semgrep = False
    config.analyzers.eslint = False
    config.analyzers.gitleaks = False
    config.analyzers.checkstyle = False
    config.analyzers.treesitter = False
    repo.save(config)


def test_deterministic_review_finds_changed_lines_without_tokens(
    client: TestClient,
    settings: Settings,
    tmp_path: Path,
) -> None:
    _ruff_only(settings)
    repository = _repository(tmp_path / "demo")
    project = client.post(
        "/api/projects/open",
        json={"path": str(repository)},
    ).json()
    (repository / "app.py").write_text(
        "import os\n\nanswer = 42\n",
        encoding="utf-8",
    )

    response = client.post(
        f"/api/projects/{project['id']}/reviews/deterministic",
        json={"base": "main", "head": "main"},
    )

    assert response.status_code == 201
    payload = response.json()
    review = payload["review"]
    assert review["status"] == "completed"
    assert review["provider_id"] is None
    assert review["model"] is None
    assert review["stats"]["files_analysed"] == 1
    assert review["stats"]["hunks_total"] == 1
    assert review["stats"]["hunks_sent_to_ai"] == 0
    assert review["stats"]["chunks_prepared"] == 1
    assert review["stats"]["estimated_context_tokens"] > 0
    assert review["stats"]["tokens_input"] == 0
    assert review["stats"]["tokens_output"] == 0
    assert review["stats"]["cost_usd"] == 0
    assert [finding["rule_id"] for finding in review["findings"]] == ["F401"]
    assert review["findings"][0]["line_start"] == 1
    assert [stage["name"] for stage in payload["stages"]] == [
        "collect",
        "filter",
        "parse",
        "static",
        "chunk",
    ]
    assert all(stage["status"] == "completed" for stage in payload["stages"])
    assert payload["analyzers"] == [
        {
            "name": "ruff",
            "status": "completed",
            "findings": 1,
            "duration_ms": payload["analyzers"][0]["duration_ms"],
            "detail": None,
        }
    ]
    assert payload["chunks"][0]["estimated_tokens"] > 0

    stored = client.get(f"/api/projects/{project['id']}/reviews").json()
    assert [item["id"] for item in stored["reviews"]] == [review["id"]]
    refreshed_project = client.get(f"/api/projects/{project['id']}").json()
    assert refreshed_project["last_reviewed_at"] is not None


def test_deterministic_review_rejects_an_unknown_project(client: TestClient) -> None:
    response = client.post(
        "/api/projects/missing/reviews/deterministic",
        json={"base": "main", "head": "main"},
    )

    assert response.status_code == 404


def test_deterministic_review_analyzes_a_non_checked_out_head(
    client: TestClient,
    settings: Settings,
    tmp_path: Path,
) -> None:
    _ruff_only(settings)
    repository = _repository(tmp_path / "demo")
    _git(repository, "switch", "-c", "feature")
    (repository / "app.py").write_text(
        "import os\n\nanswer = 42\n",
        encoding="utf-8",
    )
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "add feature")
    _git(repository, "switch", "main")
    project = client.post(
        "/api/projects/open",
        json={"path": str(repository)},
    ).json()

    response = client.post(
        f"/api/projects/{project['id']}/reviews/deterministic",
        json={"base": "main", "head": "feature"},
    )

    assert response.status_code == 201
    assert [item["rule_id"] for item in response.json()["review"]["findings"]] == [
        "F401"
    ]
    assert _git(repository, "branch", "--show-current") == "main"
