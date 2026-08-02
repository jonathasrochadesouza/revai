"""Phase 3 project and Git API contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from revai.git.repo import diff_preview


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
    _git(path, "config", "user.email", "phase3@example.com")
    _git(path, "config", "user.name", "Phase Three")
    (path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (path / "src").mkdir()
    (path / "src" / "app.py").write_text("answer = 41\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "initial")
    return path


def test_open_local_repository_persists_detected_metadata(
    client: TestClient, tmp_path: Path
) -> None:
    repo = _repository(tmp_path / "demo")

    response = client.post("/api/projects/open", json={"path": str(repo)})

    assert response.status_code == 201
    project = response.json()
    assert project["name"] == "demo"
    assert project["path"] == str(repo.resolve())
    assert project["base_branch"] == "main"
    assert project["current_branch"] == "main"
    assert project["branches"] == ["main"]
    assert project["languages"] == ["Markdown", "Python"]
    assert client.get("/api/projects").json()["projects"][0]["id"] == project["id"]


def test_opening_a_subdirectory_reuses_the_existing_project(
    client: TestClient, tmp_path: Path
) -> None:
    repo = _repository(tmp_path / "demo")

    first = client.post("/api/projects/open", json={"path": str(repo)}).json()
    second_response = client.post("/api/projects/open", json={"path": str(repo / "src")})

    assert second_response.status_code == 200
    assert second_response.json()["id"] == first["id"]
    assert len(client.get("/api/projects").json()["projects"]) == 1


def test_open_rejects_a_folder_that_is_not_a_git_repository(
    client: TestClient, tmp_path: Path
) -> None:
    folder = tmp_path / "ordinary-folder"
    folder.mkdir()

    response = client.post("/api/projects/open", json={"path": str(folder)})

    assert response.status_code == 422
    assert response.json()["detail"] == "The selected folder is not a Git repository."


def test_project_tree_lists_tracked_files(client: TestClient, tmp_path: Path) -> None:
    repo = _repository(tmp_path / "demo")
    project_id = client.post("/api/projects/open", json={"path": str(repo)}).json()["id"]

    response = client.get(f"/api/projects/{project_id}/tree")

    assert response.status_code == 200
    assert response.json() == {
        "ref": "HEAD",
        "files": ["README.md", "src/app.py"],
    }


def test_branch_diff_preview_reports_files_lines_and_estimates(
    client: TestClient, tmp_path: Path
) -> None:
    repo = _repository(tmp_path / "demo")
    _git(repo, "switch", "-c", "feature")
    (repo / "src" / "app.py").write_text("answer = 42\nprint(answer)\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "answer the question")
    project_id = client.post("/api/projects/open", json={"path": str(repo)}).json()["id"]

    response = client.get(
        f"/api/projects/{project_id}/diff",
        params={"base": "main", "head": "feature"},
    )

    assert response.status_code == 200
    preview = response.json()
    assert preview["base"] == "main"
    assert preview["head"] == "feature"
    assert preview["files"] == [
        {
            "path": "src/app.py",
            "additions": 2,
            "deletions": 1,
            "binary": False,
        }
    ]
    assert preview["additions"] == 2
    assert preview["deletions"] == 1
    assert preview["estimated_tokens"] > 0
    assert preview["estimated_cost_usd"] > 0
    assert "-answer = 41" in preview["patch"]
    assert "+answer = 42" in preview["patch"]


def test_ollama_diff_preview_reports_zero_estimated_spend(
    client: TestClient, tmp_path: Path
) -> None:
    repo = _repository(tmp_path / "demo")
    (repo / "src" / "app.py").write_text("answer = 42\n", encoding="utf-8")
    project_id = client.post("/api/projects/open", json={"path": str(repo)}).json()["id"]
    config = client.get("/api/config").json()["config"]
    config["engine"].update({"provider_id": "ollama", "model": "qwen3-coder:30b", "base_url": None})
    assert client.put("/api/config", json=config).status_code == 200

    preview = client.get(
        f"/api/projects/{project_id}/diff",
        params={"base": "main", "head": "main"},
    ).json()

    assert preview["estimated_tokens"] > 0
    assert preview["estimated_cost_usd"] == 0.0


def test_same_branch_previews_uncommitted_worktree_changes(
    client: TestClient, tmp_path: Path
) -> None:
    repo = _repository(tmp_path / "demo")
    (repo / "src" / "app.py").write_text("answer = 42\n", encoding="utf-8")
    project_id = client.post("/api/projects/open", json={"path": str(repo)}).json()["id"]

    preview = client.get(
        f"/api/projects/{project_id}/diff",
        params={"base": "main", "head": "main"},
    ).json()

    assert preview["files"][0]["path"] == "src/app.py"
    assert preview["additions"] == 1
    assert preview["deletions"] == 1
    assert "+answer = 42" in preview["patch"]


def test_same_branch_preview_includes_untracked_files(client: TestClient, tmp_path: Path) -> None:
    repo = _repository(tmp_path / "demo")
    (repo / "src" / "new_module.py").write_text(
        "def greet():\n    return 'hello'\n",
        encoding="utf-8",
    )
    project_id = client.post("/api/projects/open", json={"path": str(repo)}).json()["id"]

    preview = client.get(
        f"/api/projects/{project_id}/diff",
        params={"base": "main", "head": "main"},
    ).json()

    assert preview["files"] == [
        {
            "path": "src/new_module.py",
            "additions": 2,
            "deletions": 0,
            "binary": False,
        }
    ]
    assert "new_module.py" in preview["patch"]
    assert "+def greet():" in preview["patch"]


def test_pipeline_can_collect_a_patch_without_the_transport_limit(
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path / "demo")
    (repo / "large.txt").write_text("x" * 1_010_000 + "\n", encoding="utf-8")

    transported = diff_preview(repo, "main", "main")
    collected = diff_preview(repo, "main", "main", patch_limit_bytes=None)

    assert transported.truncated is True
    assert len(transported.patch.encode("utf-8")) <= 1_000_000
    assert collected.truncated is False
    assert len(collected.patch.encode("utf-8")) > 1_000_000


def test_clone_creates_a_project_in_the_selected_folder(client: TestClient, tmp_path: Path) -> None:
    source = _repository(tmp_path / "source")
    destination = tmp_path / "checkouts"
    destination.mkdir()

    response = client.post(
        "/api/projects/clone",
        json={
            "remote_url": source.as_uri(),
            "destination_path": str(destination),
        },
    )

    assert response.status_code == 201
    project = response.json()
    clone_path = Path(project["path"])
    assert clone_path == destination / "source"
    assert clone_path.joinpath(".git").is_dir()
    assert project["remote_url"] == source.as_uri()
    assert project["branches"] == ["main"]


def test_clone_does_not_overwrite_an_existing_destination(
    client: TestClient, tmp_path: Path
) -> None:
    source = _repository(tmp_path / "source")
    destination = tmp_path / "checkouts"
    existing = destination / "source"
    existing.mkdir(parents=True)
    marker = existing / "keep.txt"
    marker.write_text("keep me", encoding="utf-8")

    response = client.post(
        "/api/projects/clone",
        json={
            "remote_url": source.as_uri(),
            "destination_path": str(destination),
        },
    )

    assert response.status_code == 422
    assert "already exists" in response.json()["detail"]
    assert marker.read_text(encoding="utf-8") == "keep me"


def test_clone_requires_a_destination_folder(client: TestClient, tmp_path: Path) -> None:
    source = _repository(tmp_path / "source")

    response = client.post(
        "/api/projects/clone",
        json={"remote_url": source.as_uri()},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "destination_path"


def test_unknown_project_returns_404(client: TestClient) -> None:
    assert client.get("/api/projects/missing/tree").status_code == 404
    assert (
        client.get(
            "/api/projects/missing/diff", params={"base": "main", "head": "feature"}
        ).status_code
        == 404
    )


def test_diff_rejects_an_unknown_branch(client: TestClient, tmp_path: Path) -> None:
    repo = _repository(tmp_path / "demo")
    project_id = client.post("/api/projects/open", json={"path": str(repo)}).json()["id"]

    response = client.get(
        f"/api/projects/{project_id}/diff",
        params={"base": "main", "head": "does-not-exist"},
    )

    assert response.status_code == 422
    assert "does-not-exist" in response.json()["detail"]


def test_folder_picker_returns_the_native_absolute_path(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    selected = (tmp_path / "selected-repository").resolve()
    monkeypatch.setattr(
        "revai.api.routes.projects.pick_directory",
        lambda: selected,
        raising=False,
    )

    response = client.post("/api/projects/pick-folder")

    assert response.status_code == 200
    assert response.json() == {"path": str(selected)}


def test_folder_picker_returns_null_when_the_dialog_is_cancelled(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "revai.api.routes.projects.pick_directory",
        lambda: None,
        raising=False,
    )

    response = client.post("/api/projects/pick-folder")

    assert response.status_code == 200
    assert response.json() == {"path": None}


def test_openapi_documents_the_project_endpoints(client: TestClient) -> None:
    paths = client.get("/api/openapi.json").json()["paths"]

    assert "/api/projects" in paths
    assert "/api/projects/open" in paths
    assert "/api/projects/clone" in paths
    assert "/api/projects/pick-folder" in paths
    assert "/api/projects/{project_id}/tree" in paths
    assert "/api/projects/{project_id}/diff" in paths
