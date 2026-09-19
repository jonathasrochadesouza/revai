"""Fix endpoints: apply-fix and generate-fix contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from revai.config import Settings
from revai.storage.repositories import ConfigRepository, ReviewRepository


def _git(path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _repository(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "fix@example.com")
    _git(path, "config", "user.name", "Fix Routes")
    (path / "app.py").write_text("answer = 42\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "initial")
    # An unstaged working-tree change gives the review something to analyse.
    (path / "app.py").write_text("import os\n\nanswer = 42\n", encoding="utf-8")
    return path


def _ruff_only(settings: Settings) -> None:
    repo = ConfigRepository(settings)
    config = repo.load()
    config.analyzers.security = False
    config.analyzers.semgrep = False
    config.analyzers.eslint = False
    config.analyzers.gitleaks = False
    config.analyzers.checkstyle = False
    config.analyzers.treesitter = False
    repo.save(config)


def _run_review(client: TestClient, project_id: str) -> dict:
    response = client.post(
        f"/api/projects/{project_id}/reviews/deterministic",
        json={"base": "main", "head": "main"},
    )
    assert response.status_code == 201
    return response.json()["review"]


def _open_project(client: TestClient, repository: Path) -> str:
    response = client.post("/api/projects/open", json={"path": str(repository)})
    assert response.status_code == 201
    return response.json()["id"]


_F401_PATCH = "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,2 @@\n-import os\n \n answer = 42\n"


def _attach_patch(settings: Settings, project_id: str, review_id: str) -> None:
    """Deterministic analyzers report patches only rarely; stage one in.

    The endpoint plumbing under test is identical whether the patch came from
    the AI stage or from a hand-written rule fix.
    """
    review_repo = ReviewRepository(settings)
    document = review_repo.get(review_id, project_id)
    assert document is not None
    document.findings[0].suggested_patch = _F401_PATCH
    review_repo.save(document)


def test_dry_run_and_apply_round_trip(
    client: TestClient,
    settings: Settings,
    tmp_path: Path,
) -> None:
    _ruff_only(settings)
    repository = _repository(tmp_path / "demo")
    project_id = _open_project(client, repository)
    review = _run_review(client, project_id)
    finding = review["findings"][0]
    assert finding["rule_id"] == "F401"
    assert finding["suggested_patch"] is None
    _attach_patch(settings, project_id, review["id"])
    fix_url = (
        f"/api/projects/{project_id}/reviews/{review['id']}"
        f"/findings/{finding['id']}/apply-fix"
    )

    preview = client.post(fix_url, json={"dry_run": True})
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["applied"] is False
    assert preview_payload["dry_run"] is True
    assert preview_payload["files"] == ["app.py"]
    assert (repository / "app.py").read_text(encoding="utf-8") == "import os\n\nanswer = 42\n"

    applied = client.post(fix_url, json={"dry_run": False})
    assert applied.status_code == 200
    applied_payload = applied.json()
    assert applied_payload["applied"] is True
    assert applied_payload["validation"] == "validated (ruff clean)"
    assert (repository / "app.py").read_text(encoding="utf-8") == "\nanswer = 42\n"
    # Working tree only: nothing is staged for commit.
    staged = subprocess.run(
        ["git", "-C", str(repository), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert staged.stdout.strip() == ""

    stored = client.get(f"/api/projects/{project_id}/reviews").json()
    stored_review = next(
        item for item in stored["reviews"] if item["id"] == review["id"]
    )
    stored_finding = next(
        item for item in stored_review["findings"] if item["id"] == finding["id"]
    )
    assert stored_finding["fix_state"] == "applied"
    assert stored_finding["status"] == "open"
    assert stored_finding["fix_validation"] == "validated (ruff clean)"

    again = client.post(fix_url, json={})
    assert again.status_code == 409
    assert again.json()["detail"]["error_key"] == "fix.already_applied"


def test_apply_unknown_finding_returns_404(
    client: TestClient,
    settings: Settings,
    tmp_path: Path,
) -> None:
    _ruff_only(settings)
    repository = _repository(tmp_path / "demo")
    project_id = _open_project(client, repository)
    review = _run_review(client, project_id)

    response = client.post(
        f"/api/projects/{project_id}/reviews/{review['id']}/findings/nope/apply-fix",
        json={},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error_key"] == "review.finding_not_found"


def test_generate_without_provider_reports_unavailable(
    client: TestClient,
    settings: Settings,
    tmp_path: Path,
) -> None:
    _ruff_only(settings)
    repository = _repository(tmp_path / "demo")
    project_id = _open_project(client, repository)
    review = _run_review(client, project_id)
    finding = review["findings"][0]

    response = client.post(
        f"/api/projects/{project_id}/reviews/{review['id']}"
        f"/findings/{finding['id']}/generate-fix",
        json={},
    )
    assert response.status_code == 422
    # Without a key the registry either yields nothing or yields an unusable
    # provider; both are honest 422s.
    assert response.json()["detail"]["error_key"] in {
        "provider.unavailable",
        "provider.not_ready",
    }
