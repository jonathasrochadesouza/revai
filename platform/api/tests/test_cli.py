"""Phase 9 installed command contracts."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from revai.cli import main
from revai.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_doctor_initializes_and_validates_a_fresh_data_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_dir = tmp_path / "state"
    monkeypatch.setenv("REVAI_DATA_DIR", str(data_dir))

    exit_code = main(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["data_dir"] == str(data_dir)
    assert data_dir.is_dir()
    assert {check["name"] for check in payload["checks"]} >= {
        "python",
        "data_dir",
        "config",
        "credentials",
    }


def test_doctor_reports_invalid_yaml_without_a_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_dir = tmp_path / "state"
    data_dir.mkdir()
    (data_dir / "config.yaml").write_text("engine: [broken\n", encoding="utf-8")
    monkeypatch.setenv("REVAI_DATA_DIR", str(data_dir))

    exit_code = main(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "error"
    config = next(check for check in payload["checks"] if check["name"] == "config")
    assert config["status"] == "error"
    assert config["detail"] == "storage.invalid_yaml"


def test_serve_preserves_loopback_and_accepts_a_valid_port_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("REVAI_ENVIRONMENT", "test")

    def fake_run(app: str, **kwargs: object) -> None:
        captured.update(app=app, configured_port=get_settings().port, **kwargs)

    monkeypatch.setattr("revai.cli.uvicorn.run", fake_run)

    assert main(["serve", "--port", "8800"]) == 0
    assert captured["app"] == "revai.main:app"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8800
    assert captured["configured_port"] == 8800
    assert captured["reload"] is False


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not portable")
def test_doctor_rejects_a_world_readable_credentials_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_dir = tmp_path / "state"
    data_dir.mkdir()
    credentials = data_dir / "credentials.yaml"
    credentials.write_text("schema_version: 1\nproviders: {}\n", encoding="utf-8")
    credentials.chmod(0o644)
    monkeypatch.setenv("REVAI_DATA_DIR", str(data_dir))

    exit_code = main(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    check = next(check for check in payload["checks"] if check["name"] == "credential_permissions")
    assert exit_code == 1
    assert check["status"] == "error"
    assert "expected 0600" in check["detail"]


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "doctor" in capsys.readouterr().out


def test_headless_static_review_writes_sarif_and_uses_quality_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "-C", str(repository), "init", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(repository), "config", "user.name", "CLI Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "cli@example.com"],
        check=True,
    )
    (repository / "app.py").write_text("answer = 42\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-m", "initial"], check=True)
    (repository / "app.py").write_text("result = eval(input())\n", encoding="utf-8")
    output = tmp_path / "review.sarif"
    monkeypatch.setenv("REVAI_DATA_DIR", str(tmp_path / "state"))

    exit_code = main(
        [
            "review",
            str(repository),
            "--mode",
            "static",
            "--format",
            "sarif",
            "--output",
            str(output),
            "--fail-on",
            "critical",
            "--no-persist",
        ]
    )

    assert exit_code == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["version"] == "2.1.0"
    assert payload["runs"][0]["results"][0]["level"] == "error"


_F401_PATCH = "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,2 @@\n-import os\n \n answer = 42\n"


def _fix_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "-C", str(repository), "init", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(repository), "config", "user.name", "CLI Fix"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "clifix@example.com"],
        check=True,
    )
    (repository / "app.py").write_text("answer = 42\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-m", "initial"], check=True)
    (repository / "app.py").write_text("import os\n\nanswer = 42\n", encoding="utf-8")
    return repository


def _stored_ruff_finding(tmp_path: Path, repository: Path) -> tuple[str, str]:
    """Run a persisted static review and stage a patch on the F401 finding."""
    review_json = tmp_path / "review.json"
    exit_code = main(
        [
            "review",
            str(repository),
            "--mode",
            "static",
            "--format",
            "json",
            "--output",
            str(review_json),
            "--fail-on",
            "medium",
        ]
    )
    assert exit_code == 1
    from revai.storage.repositories import ReviewRepository

    review_repo = ReviewRepository(get_settings())
    review = next(item for item in review_repo.list() if item.findings)
    finding = next(item for item in review.findings if item.rule_id == "F401")
    finding.suggested_patch = _F401_PATCH
    review_repo.save(review)
    return review.id, finding.id


def test_headless_fix_applies_the_stored_patch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _fix_repository(tmp_path)
    monkeypatch.setenv("REVAI_DATA_DIR", str(tmp_path / "state"))
    review_id, finding_id = _stored_ruff_finding(tmp_path, repository)

    exit_code = main(
        ["fix", str(repository), "--review", review_id, "--finding", finding_id, "--json"]
    )

    assert exit_code == 0
    assert (repository / "app.py").read_text(encoding="utf-8") == "\nanswer = 42\n"
    staged = subprocess.run(
        ["git", "-C", str(repository), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert staged.stdout.strip() == ""


def test_headless_fix_dry_run_leaves_the_tree_alone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = _fix_repository(tmp_path)
    monkeypatch.setenv("REVAI_DATA_DIR", str(tmp_path / "state"))
    review_id, finding_id = _stored_ruff_finding(tmp_path, repository)

    exit_code = main(
        [
            "fix",
            str(repository),
            "--review",
            review_id,
            "--finding",
            finding_id,
            "--dry-run",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "import os" in out
    assert (repository / "app.py").read_text(encoding="utf-8") == "import os\n\nanswer = 42\n"


def test_headless_fix_reports_a_failing_outcome_with_exit_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _fix_repository(tmp_path)
    monkeypatch.setenv("REVAI_DATA_DIR", str(tmp_path / "state"))
    review_id, finding_id = _stored_ruff_finding(tmp_path, repository)
    # A patch for a file state the tree no longer has cannot apply.
    from revai.config import Settings
    from revai.storage.repositories import ReviewRepository

    review_repo = ReviewRepository(Settings(data_dir=tmp_path / "state", environment="test"))
    review = review_repo.get(review_id)
    assert review is not None
    finding = next(item for item in review.findings if item.id == finding_id)
    finding.suggested_patch = (
        "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,2 @@\n-import io\n \n answer = 42\n"
    )
    review_repo.save(review)

    exit_code = main(
        ["fix", str(repository), "--review", review_id, "--finding", finding_id, "--json"]
    )

    assert exit_code == 1
    assert (repository / "app.py").read_text(encoding="utf-8") == "import os\n\nanswer = 42\n"
