"""The RevAI review agent: template, renderer, generator, installer, routes, CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from revai.agents.generator import (
    MARKER_BEGIN,
    MARKER_END,
    collect_rules,
    compose_block,
    compose_document,
)
from revai.agents.installer import install
from revai.agents.renderer import (
    PLACEHOLDER,
    inject_data,
    load_template,
    render_report,
    report_filename,
    slugify_name,
    validate_payload,
)
from revai.cli import main
from revai.config import get_settings
from revai.domain.models import RevaiConfig
from revai.domain.prompts import PROMPT_INJECTION_GUARD


@pytest.fixture
def config() -> RevaiConfig:
    return RevaiConfig()


# --- template ------------------------------------------------------------------


def test_template_has_exactly_one_placeholder_and_a_json_node() -> None:
    template = load_template()
    assert template.count(PLACEHOLDER) == 1
    assert '<script type="application/json" id="revai-data">' in template
    # The renderer must never fall back to remote assets: the page works offline.
    assert "http://" not in template and "https://" not in template


# --- renderer ------------------------------------------------------------------


def test_inject_data_escapes_closing_script_tags() -> None:
    template = f"<i-data>{PLACEHOLDER}</i-data>"
    document = inject_data(template, {"findings": [{"description": "</script><script>alert(1)"}]})
    payload = document[len("<i-data>") : -len("</i-data>")]
    assert "</script>" not in payload
    assert json.loads(payload.replace("<\\/", "</"))["findings"][0]["description"].endswith(
        "<script>alert(1)"
    )


def test_inject_data_rejects_a_broken_template() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        inject_data("no placeholder here", {"findings": []})


def test_validate_payload_accepts_the_compact_agent_envelope() -> None:
    finding = {"title": "x", "file": "a.py", "line_start": 1}
    payload = validate_payload(json.dumps({"findings": [finding]}))
    assert payload["findings"][0]["file"] == "a.py"


def test_validate_payload_accepts_the_full_export_envelope() -> None:
    review = {
        "id": "abc123",
        "findings": [
            {
                "severity": "critical",
                "category": "security",
                "title": "t",
                "description": "d",
                "file": "a.py",
                "line_start": 3,
                "source": "ai",
            }
        ],
    }
    payload = validate_payload(json.dumps({"format_version": 1, "review": review}))
    assert payload["review"]["id"] == "abc123"


def test_validate_payload_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        validate_payload("not json")
    with pytest.raises(ValueError, match="findings"):
        validate_payload(json.dumps({"items": []}))
    with pytest.raises(ValueError, match="contract"):
        validate_payload(json.dumps({"findings": [{"file": 1}]}))


def test_render_report_writes_the_branch_named_file(tmp_path: Path) -> None:
    destination = render_report(
        json.dumps({"findings": [{"title": "x", "file": "a.py", "line_start": 4}]}),
        name="feat/user",
        out_dir=tmp_path,
    )
    assert destination.name == "feat-user-revai.html"
    document = destination.read_text(encoding="utf-8")
    assert PLACEHOLDER not in document
    assert '"title": "x"' in document


def test_slugify_name_is_filename_safe() -> None:
    assert slugify_name("feat///user x") == "feat-user-x"
    assert slugify_name("   ") == "review"


def test_report_filename_pattern() -> None:
    assert report_filename("feat-user") == "feat-user-revai.html"


# --- generator -----------------------------------------------------------------


def test_compose_block_carries_persona_guard_and_contract(config: RevaiConfig) -> None:
    block = compose_block(config)
    assert block.startswith(MARKER_BEGIN) and block.endswith(MARKER_END)
    assert "senior code reviewer" in block
    assert PROMPT_INJECTION_GUARD.strip() in block
    assert "revai-findings.json" in block
    assert "<branch-slug>-revai.html" in block
    assert "__REVAI_DATA__" in block
    # No API key or credential may ever reach the project.
    assert "sk-" not in block


def test_compose_block_inlines_rules(config: RevaiConfig, tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "api.md").write_text("# Never return raw objects\n", encoding="utf-8")
    block = compose_block(config, rules=collect_rules(rules))
    assert "#### api.md" in block
    assert "Never return raw" in block
    # The rules section sits inside the managed block.
    assert block.index("#### api.md") < block.index(MARKER_END)


def test_compose_document_is_idempotent(config: RevaiConfig) -> None:
    block = compose_block(config)
    once = compose_document("# My notes", block)
    twice = compose_document(once, block)
    assert twice == once
    assert twice.startswith("# My notes")
    assert once.count(MARKER_BEGIN) == 1


# --- installer -----------------------------------------------------------------


def test_install_creates_agents_md_and_template(tmp_path: Path) -> None:
    block = compose_block(RevaiConfig())
    result = install(tmp_path, block)
    assert not result.dry_run
    agents_md = tmp_path / "AGENTS.md"
    assert agents_md.is_file()
    assert MARKER_BEGIN in agents_md.read_text(encoding="utf-8")
    assert (tmp_path / ".revai" / "agent-report.html").is_file()
    assert result.agents_md_created
    assert not result.backup_created


def test_install_merges_without_touching_other_content_and_backs_up(tmp_path: Path) -> None:
    original = "# My project rules\n- always typecheck\n"
    (tmp_path / "AGENTS.md").write_text(original, encoding="utf-8")
    result = install(tmp_path, compose_block(RevaiConfig()))
    document = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert document.startswith("# My project rules")
    assert "always typecheck" in document
    backup = (tmp_path / "AGENTS.md.revai-bak").read_text(encoding="utf-8")
    assert backup.startswith("# My project rules")
    assert result.backup_created
    # A second install refreshes in place, without a second backup.
    assert not install(tmp_path, compose_block(RevaiConfig())).backup_created
    assert document.count(MARKER_END) == 1


def test_install_dry_run_writes_nothing(tmp_path: Path) -> None:
    result = install(tmp_path, compose_block(RevaiConfig()), dry_run=True)
    assert result.dry_run
    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / ".revai").exists()


def test_install_requires_a_directory(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        install(tmp_path / "missing", compose_block(RevaiConfig()))


# --- routes --------------------------------------------------------------------


def _open_project(client: TestClient, repo: Path) -> str:
    response = client.post("/api/projects/open", json={"path": str(repo)})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _repository(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "-C", str(path), "init", "-q", "-b", "main"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "agent@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Agent Test"],
        check=True,
        capture_output=True,
    )
    (path / "README.md").write_text("# Demo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-q", "-m", "initial"], check=True, capture_output=True
    )
    return path


def test_agent_preview_returns_merged_document(client: TestClient, tmp_path: Path) -> None:
    project_id = _open_project(client, _repository(tmp_path / "demo"))

    response = client.get("/api/agent/preview", params={"project_id": project_id})

    payload = response.json()
    assert response.status_code == 200
    assert payload["agents_md_exists"] is False
    assert payload["agents_md"].startswith("<!-- revai:begin")
    assert "RevAI Code Review" in payload["agents_md"]
    assert payload["agents_md_path"].endswith("AGENTS.md")


def test_agent_apply_writes_both_files(client: TestClient, tmp_path: Path) -> None:
    project_id = _open_project(client, _repository(tmp_path / "demo"))

    response = client.post("/api/agent/apply", json={"project_id": project_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["agents_md_created"] is True
    assert Path(payload["agents_md"]).is_file()
    assert Path(payload["template"]).is_file()


def test_agent_apply_rejects_an_unknown_project(client: TestClient) -> None:
    assert client.post("/api/agent/apply", json={"project_id": "nope"}).status_code == 404


def test_agent_report_demo_renders_html(client: TestClient) -> None:
    response = client.get("/api/agent/report-demo")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "revai-data" in response.text


# --- CLI -----------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_cli_agent_install_dry_run_prints_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("REVAI_DATA_DIR", str(tmp_path / "state"))
    target = tmp_path / "project"
    target.mkdir()

    exit_code = main(["agent", "install", str(target), "--dry-run"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "RevAI Code Review" in output
    assert not (target / "AGENTS.md").exists()


def test_cli_agent_install_writes_with_yes_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("REVAI_DATA_DIR", str(tmp_path / "state"))
    target = tmp_path / "project"
    target.mkdir()

    exit_code = main(["agent", "install", str(target), "--yes"])

    assert exit_code == 0
    assert (target / "AGENTS.md").is_file()
    assert (target / ".revai" / "agent-report.html").is_file()


def test_cli_agent_install_refuses_to_write_without_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REVAI_DATA_DIR", str(tmp_path / "state"))
    target = tmp_path / "project"
    target.mkdir()

    assert main(["agent", "install", str(target)]) == 2
    assert not (target / "AGENTS.md").exists()


def test_cli_agent_render_writes_the_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    findings = tmp_path / "revai-findings.json"
    findings.write_text(
        json.dumps({"findings": [{"title": "x", "file": "a.py", "line_start": 2}]}),
        encoding="utf-8",
    )
    out = tmp_path / "out"

    exit_code = main(["agent", "render", str(findings), "--name", "feat-user", "--out", str(out)])

    report = out / "feat-user-revai.html"
    assert exit_code == 0
    assert report.is_file()
    assert PLACEHOLDER not in report.read_text(encoding="utf-8")


def test_cli_agent_render_rejects_an_invalid_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("REVAI_DATA_DIR", str(tmp_path / "state"))
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")

    exit_code = main(["agent", "render", str(broken), "--name", "x"])

    assert exit_code == 2
    assert "revai agent render failed" in capsys.readouterr().err
