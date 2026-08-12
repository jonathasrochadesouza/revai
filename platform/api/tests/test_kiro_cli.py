"""Kiro CLI adapter regression tests."""

from __future__ import annotations

import pytest

from revai.domain.enums import ProviderId
from revai.providers.base import AnalysisRequest
from revai.providers.cli.base import CliCommandResult
from revai.providers.cli.kiro import KiroCliProvider
from revai.providers.detection import CLI_SPECS, resolve_executable, run_command


async def test_kiro_cli_adapter_runs_non_interactive_chat(monkeypatch) -> None:
    provider = KiroCliProvider(executable="kiro-cli")

    captured: dict[str, object] = {}

    async def fake_run(executable: str, args: list[str], timeout_s: float):
        captured.update(executable=executable, args=args, timeout_s=timeout_s)
        return CliCommandResult(0, '{"findings":[]}', "")

    monkeypatch.setattr("revai.providers.cli.kiro.run_cli_command", fake_run)

    events = [
        event
        async for event in provider.analyze(
            AnalysisRequest(
                model="claude-haiku-4.5",
                system_prompt="Return only JSON.",
                user_prompt="Review app.py.",
                json_schema={"type": "object"},
                timeout_s=30,
            )
        )
    ]

    assert captured["args"][:2] == ["chat", "--no-interactive"]
    assert "--model" not in captured["args"]
    assert "Return only JSON." in captured["args"][-1]
    assert "Review app.py." in captured["args"][-1]
    assert events[0].type == "started"
    assert events[-1].type == "finished"
    assert events[-1].text == '{"findings":[]}'


@pytest.mark.cli
async def test_installed_kiro_cli_reports_a_version_without_spending_credits() -> None:
    """A real CLI probe is safe; model selection belongs to Kiro settings."""

    spec = next(spec for spec in CLI_SPECS if spec.provider_id is ProviderId.KIRO_CLI)
    resolved = resolve_executable(spec)
    if resolved is None:
        pytest.skip("Kiro CLI is not installed.")

    _, executable = resolved
    result = await run_command(executable, ["--version"])

    assert result.ok, result.combined
    assert result.stdout.strip()
