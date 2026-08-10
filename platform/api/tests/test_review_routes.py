"""Phase 4 deterministic review API contracts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from revai.config import Settings
from revai.providers.base import (
    DeltaEvent,
    FinishedEvent,
    StartedEvent,
    UsageStats,
)
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


def test_finding_status_is_persisted(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    _ruff_only(settings)
    repository = _repository(tmp_path / "finding-status")
    project = client.post("/api/projects/open", json={"path": str(repository)}).json()
    (repository / "app.py").write_text("import os\n\nanswer = 42\n", encoding="utf-8")
    review = client.post(
        f"/api/projects/{project['id']}/reviews/deterministic",
        json={"base": "main", "head": "main"},
    ).json()["review"]

    response = client.patch(
        f"/api/projects/{project['id']}/reviews/{review['id']}/findings/{review['findings'][0]['id']}",
        json={"status": "false_positive"},
    )

    assert response.status_code == 200
    assert response.json()["findings"][0]["status"] == "false_positive"
    stored = client.get(f"/api/projects/{project['id']}/reviews").json()["reviews"]
    assert stored[0]["findings"][0]["status"] == "false_positive"


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
    assert [item["rule_id"] for item in response.json()["review"]["findings"]] == ["F401"]
    assert _git(repository, "branch", "--show-current") == "main"


class _AIProvider:
    async def analyze(self, _request):
        text = json.dumps(
            {
                "findings": [
                    {
                        "severity": "critical",
                        "category": "security",
                        "title": "Dynamic code execution",
                        "description": "Untrusted input reaches eval.",
                        "rationale": "The token can execute arbitrary Python.",
                        "file": "app.py",
                        "line_start": 4,
                        "line_end": 4,
                        "rule_id": "eval-detected",
                        "confidence": 0.97,
                        "suggested_patch": None,
                    }
                ]
            }
        )
        yield StartedEvent(model="test/model")
        yield DeltaEvent(text=text[:24])
        yield FinishedEvent(
            text=text,
            usage=UsageStats(
                input_tokens=160,
                output_tokens=70,
                cached_tokens=20,
                cost_usd=0.005,
            ),
        )


class _AIRegistry:
    def active(self):
        return _AIProvider()


def _stream_events(response) -> list[dict]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.iter_lines()
        if line.startswith("data: ")
    ]


def test_ai_review_streams_progress_and_persists_combined_findings(
    client: TestClient,
    settings: Settings,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _ruff_only(settings)
    repository = _repository(tmp_path / "ai-demo")
    project = client.post("/api/projects/open", json={"path": str(repository)}).json()
    (repository / "app.py").write_text(
        "import os\n\ndef auth(token):\n    return eval(token)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "revai.api.routes.reviews.build_registry",
        lambda _config, _credentials: _AIRegistry(),
    )

    with client.stream(
        "POST",
        f"/api/projects/{project['id']}/reviews/stream",
        json={"base": "main", "head": "main"},
    ) as response:
        events = _stream_events(response)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    kinds = [event["type"] for event in events]
    assert kinds[:2] == ["review_queued", "review_started"]
    assert kinds.count("stage") == 7
    assert "provider" in kinds
    assert "delta" in kinds
    assert "usage" in kinds
    assert kinds[-1] == "completed"
    review = events[-1]["result"]["review"]
    assert review["status"] == "completed"
    assert review["provider_id"] == "openrouter"
    assert review["stats"]["tokens_input"] == 160
    assert review["stats"]["tokens_output"] == 70
    assert review["stats"]["cost_usd"] == 0.005
    assert {item["source"] for item in review["findings"]} == {"ruff", "ai"}
    stored = client.get(f"/api/projects/{project['id']}/reviews").json()["reviews"]
    assert stored[0]["id"] == review["id"]
