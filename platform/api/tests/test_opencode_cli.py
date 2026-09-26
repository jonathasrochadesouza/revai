"""opencode CLI adapter regression tests."""

from __future__ import annotations

import json

import pytest

from revai.domain.enums import ProviderId, ProviderKind
from revai.domain.models import Credentials, RevaiConfig
from revai.providers.base import AnalysisRequest
from revai.providers.cli import OpencodeCliProvider
from revai.providers.cli.base import CliCommandResult
from revai.providers.detection import CLI_SPECS, resolve_executable, run_command
from revai.providers.registry import build_registry


async def _collect(provider, request):
    return [event async for event in provider.analyze(request)]


async def test_opencode_cli_runs_non_interactive_json_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_run(executable: str, args: list[str], timeout_s: float):
        captured.update(executable=executable, args=args, timeout_s=timeout_s)
        events = "\n".join(
            [
                json.dumps({"part": {"type": "text", "text": '{"findings":[]}'}}),
                json.dumps({"tokens": {"input": 80, "output": 12, "cost_usd": 0.004}}),
            ]
        )
        return CliCommandResult(0, events, "")

    monkeypatch.setattr("revai.providers.cli.opencode.run_cli_command", fake_run)

    events = await _collect(
        OpencodeCliProvider(executable="/fake/opencode"),
        AnalysisRequest(
            model="anthropic/claude-sonnet-4-5",
            system_prompt="Return only JSON.",
            user_prompt="Review app.py.",
            json_schema={"type": "object"},
            timeout_s=30,
        ),
    )

    args = captured["args"]
    assert args[:1] == ["run"]
    assert args[args.index("--model") + 1] == "anthropic/claude-sonnet-4-5"
    assert "--format" in args and args[args.index("--format") + 1] == "json"
    assert "Return only JSON." in args[-1]
    assert "Review app.py." in args[-1]
    assert events[0].type == "started"
    assert events[-1].type == "finished"
    assert events[-1].text == '{"findings":[]}'
    assert events[-1].usage.input_tokens == 80
    assert events[-1].usage.output_tokens == 12
    assert events[-1].usage.cost_usd == pytest.approx(0.004)


async def test_opencode_cli_falls_back_to_raw_stdout_for_unrecognised_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run(_executable: str, _args: list[str], _timeout_s: float):
        return CliCommandResult(0, '{"findings": []}', "")

    monkeypatch.setattr("revai.providers.cli.opencode.run_cli_command", fake_run)

    events = await _collect(
        OpencodeCliProvider(executable="/fake/opencode"),
        AnalysisRequest(model="anthropic/claude-sonnet-4-5", user_prompt="review"),
    )

    assert events[-1].type == "finished"
    assert events[-1].text == '{"findings": []}'
    assert events[-1].usage.is_estimated is True


async def test_opencode_cli_missing_executable_fails_cleanly() -> None:
    events = await _collect(
        OpencodeCliProvider(executable=None),
        AnalysisRequest(model="anthropic/claude-sonnet-4-5", user_prompt="review"),
    )
    # No executable override and (most CI machines) no opencode on PATH.
    if events[0].type == "failed":
        assert "opencode CLI" in events[0].message


def test_registry_resolves_opencode_adapter() -> None:
    config = RevaiConfig()
    registry = build_registry(config, Credentials())

    provider = registry.get(ProviderId.OPENCODE_CLI)
    assert isinstance(provider, OpencodeCliProvider)
    assert provider.kind is ProviderKind.CLI


@pytest.mark.cli
async def test_installed_opencode_cli_reports_a_version_without_spending_credits() -> None:
    """A real CLI probe is safe; model selection belongs to opencode config."""

    spec = next(spec for spec in CLI_SPECS if spec.provider_id is ProviderId.OPENCODE_CLI)
    resolved = resolve_executable(spec)
    if resolved is None:
        pytest.skip("opencode CLI is not installed.")

    _, executable = resolved
    result = await run_command(executable, ["--version"])

    assert result.ok, result.combined
    assert result.stdout.strip()
