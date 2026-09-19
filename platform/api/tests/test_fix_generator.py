"""Search/replace generation: provider contract and diff conversion."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from revai.domain.enums import FindingSource, ProviderId
from revai.domain.models import Finding, Project, RevaiConfig
from revai.errors import RevaiError
from revai.fixes.generator import (
    PROMPT_INJECTION_GUARD,
    generate_fix_patch,
    search_replace_to_diff,
)
from revai.providers.base import (
    FinishedEvent,
    ProviderHealth,
    StartedEvent,
    UsageStats,
)


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
    _git(path, "config", "user.email", "gen@example.com")
    _git(path, "config", "user.name", "Generator Test")
    (path / "app.py").write_text("import os\n\nanswer = 42\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "initial")
    return path


def _finding() -> Finding:
    return Finding(
        severity="medium",
        category="maintainability",
        title="Unused import",
        description="os is imported and never used.",
        file="app.py",
        line_start=1,
        source=FindingSource.RUFF,
        rule_id="F401",
    )


def _provider(text: str) -> type:
    class _FakeProvider:
        provider_id = ProviderId.OPENROUTER

        async def health(self) -> ProviderHealth:
            return ProviderHealth(provider_id="openrouter", kind="api", state="ready")

        async def analyze(self, _request):
            yield StartedEvent(model="test/model")
            yield FinishedEvent(
                text=text,
                usage=UsageStats(input_tokens=120, output_tokens=40, cost_usd=0.001),
            )

    return _FakeProvider


def test_search_replace_to_diff_builds_applicable_patch() -> None:
    diff = search_replace_to_diff(
        "app.py",
        "import os\n\nanswer = 42\n",
        "import os\n\nanswer = 42\n",
        "answer = 42\n",
    )
    assert diff.startswith("--- a/app.py\n+++ b/app.py\n")
    assert "@@" in diff
    assert "-import os" in diff


def test_search_replace_rejects_missing_block() -> None:
    with pytest.raises(RevaiError) as caught:
        search_replace_to_diff(
            "app.py", "import os\n\nanswer = 42\n", "import sys\n", "x\n"
        )
    assert caught.value.error_key == "fix.search_block_not_found"


def test_search_replace_rejects_no_change() -> None:
    with pytest.raises(RevaiError) as caught:
        search_replace_to_diff("app.py", "a\n", "a\n", "a\n")
    assert caught.value.error_key == "fix.no_change_generated"


def test_extract_block_repairs_fenced_json() -> None:
    from revai.fixes.generator import _extract_block

    text = "```json\n{\"search\": \"import os\\n\", \"replace\": \"\",}\n```"
    block = _extract_block(text)
    assert block.search == "import os\n"
    assert block.replace == ""


async def test_generate_fix_patch_converts_model_output(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "demo")
    text = json.dumps(
        {
            "search": "import os\n",
            "replace": "",
        }
    )
    provider = _provider(text)()

    generated = await generate_fix_patch(
        provider, RevaiConfig(), Project(name="demo", path=str(repository)), _finding()
    )

    assert generated.patch.startswith("--- a/app.py")
    assert "-import os" in generated.patch
    assert generated.usage.output_tokens == 40


async def test_generate_fix_prompt_wraps_content_in_the_guard(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "demo")
    captured: dict = {}

    class _CapturingProvider:
        provider_id = ProviderId.OPENROUTER

        async def health(self) -> ProviderHealth:
            return ProviderHealth(provider_id="openrouter", kind="api", state="ready")

        async def analyze(self, request):
            captured["system"] = request.system_prompt
            captured["user"] = request.user_prompt
            yield FinishedEvent(text=json.dumps({"search": "import os\n", "replace": ""}))

    await generate_fix_patch(
        _CapturingProvider(),
        RevaiConfig(),
        Project(name="demo", path=str(repository)),
        _finding(),
    )

    assert PROMPT_INJECTION_GUARD in captured["user"]
    assert "search" in captured["system"]
    # Numbered excerpt makes the model quote exact content, not line offsets.
    assert "1: import os" in captured["user"]


async def test_generate_fix_rejects_non_matching_block(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "demo")
    provider = _provider(json.dumps({"search": "import sys\n", "replace": ""}))()

    with pytest.raises(RevaiError) as caught:
        await generate_fix_patch(
            provider, RevaiConfig(), Project(name="demo", path=str(repository)), _finding()
        )

    assert caught.value.error_key == "fix.search_block_not_found"


async def test_generate_fix_rejects_malformed_output(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "demo")
    provider = _provider("I cannot do that.")()

    with pytest.raises(RevaiError) as caught:
        await generate_fix_patch(
            provider, RevaiConfig(), Project(name="demo", path=str(repository)), _finding()
        )

    assert caught.value.error_key == "fix.invalid_generation"
