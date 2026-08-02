"""Phase 8 CLI adapter contracts."""

from __future__ import annotations

import json
import sys

import pytest

from revai.domain.enums import ProviderId, ProviderKind
from revai.domain.models import Credentials, RevaiConfig
from revai.pipeline.ai import run_ai_stage
from revai.pipeline.deterministic import CodeChunk
from revai.providers.base import AnalysisRequest, Provider
from revai.providers.cli import ClaudeCodeProvider, CopilotCliProvider, KiroCliProvider
from revai.providers.cli.base import CliCommandResult, run_cli_command
from revai.providers.registry import build_registry


async def _collect(provider: Provider, request: AnalysisRequest):
    return [event async for event in provider.analyze(request)]


async def test_claude_code_uses_validated_headless_output_and_reports_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_run(executable: str, args: list[str], timeout_s: float):
        captured.update(executable=executable, args=args, timeout_s=timeout_s)
        return CliCommandResult(
            0,
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "structured_output": {"findings": []},
                    "session_id": "session-1",
                    "total_cost_usd": 0.012,
                    "usage": {
                        "input_tokens": 120,
                        "output_tokens": 18,
                        "cache_read_input_tokens": 40,
                    },
                }
            ),
            "",
        )

    monkeypatch.setattr("revai.providers.cli.claude_code.run_cli_command", fake_run)
    request = AnalysisRequest(
        model="sonnet",
        system_prompt="Return JSON.",
        user_prompt="Review $(touch /tmp/never-run).",
        json_schema={"type": "object", "properties": {"findings": {"type": "array"}}},
        timeout_s=42,
    )

    events = await _collect(ClaudeCodeProvider(executable="/fake/claude"), request)

    assert [event.type for event in events] == ["started", "delta", "finished"]
    assert events[-1].text == '{"findings": []}'
    assert events[-1].session_id == "session-1"
    assert events[-1].usage.input_tokens == 120
    assert events[-1].usage.cached_tokens == 40
    assert events[-1].usage.cost_usd == pytest.approx(0.012)
    args = captured["args"]
    assert isinstance(args, list)
    assert "--json-schema" in args
    assert args[args.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in args
    assert "$(touch /tmp/never-run)" in args[1]
    assert captured["timeout_s"] == 42


async def test_claude_code_rejects_an_invalid_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run(_executable: str, _args: list[str], _timeout_s: float):
        return CliCommandResult(0, "not json", "")

    monkeypatch.setattr("revai.providers.cli.claude_code.run_cli_command", fake_run)

    events = await _collect(
        ClaudeCodeProvider(executable="/fake/claude"),
        AnalysisRequest(model="sonnet", user_prompt="review"),
    )

    assert events[-1].type == "failed"
    assert "invalid JSON" in events[-1].message


async def test_copilot_cli_extracts_jsonl_response_and_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []
    response = '{"findings":[]}'

    async def fake_run(_executable: str, args: list[str], _timeout_s: float):
        captured.extend(args)
        return CliCommandResult(
            0,
            "\n".join(
                [
                    json.dumps({"type": "assistant.message", "data": {"content": response}}),
                    json.dumps(
                        {
                            "type": "result",
                            "data": {
                                "usage": {
                                    "input_tokens": 50,
                                    "output_tokens": 9,
                                    "cost_usd": 0.003,
                                }
                            },
                        }
                    ),
                ]
            ),
            "",
        )

    monkeypatch.setattr("revai.providers.cli.copilot.run_cli_command", fake_run)

    events = await _collect(
        CopilotCliProvider(executable="/fake/copilot"),
        AnalysisRequest(
            model="gpt-5.3-codex",
            user_prompt="review",
            json_schema={"type": "object", "properties": {"findings": {"type": "array"}}},
        ),
    )

    assert [event.type for event in events] == ["started", "delta", "finished"]
    assert events[-1].text == response
    assert events[-1].usage.input_tokens == 50
    assert events[-1].usage.cost_usd == pytest.approx(0.003)
    assert "--silent" in captured
    assert "--output-format=json" not in captured
    assert "--stream=off" in captured
    assert "--no-custom-instructions" in captured
    assert '"findings"' in captured[1]
    assert all("allow-all" not in argument for argument in captured)


async def test_copilot_keeps_older_silent_plain_text_compatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run(_executable: str, _args: list[str], _timeout_s: float):
        return CliCommandResult(0, '```json\n{"findings": []}\n```\n', "")

    monkeypatch.setattr("revai.providers.cli.copilot.run_cli_command", fake_run)
    events = await _collect(
        CopilotCliProvider(executable="/fake/copilot"),
        AnalysisRequest(model="auto", user_prompt="review"),
    )

    assert events[-1].text.startswith("```json")
    assert events[-1].usage.is_estimated is True


async def test_kiro_uses_supported_headless_mode_without_granting_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    async def fake_run(_executable: str, args: list[str], _timeout_s: float):
        captured.extend(args)
        return CliCommandResult(0, 'Here is the result:\n{"findings": []}', "")

    monkeypatch.setattr("revai.providers.cli.kiro.run_cli_command", fake_run)
    events = await _collect(
        KiroCliProvider(executable="/fake/kiro-cli"),
        AnalysisRequest(
            model="kiro-default",
            user_prompt="review",
            json_schema={"type": "object", "properties": {"findings": {"type": "array"}}},
        ),
    )

    assert captured[:2] == ["chat", "--no-interactive"]
    assert all("trust" not in argument for argument in captured)
    assert '"findings"' in captured[2]
    assert events[-1].text.endswith('{"findings": []}')
    assert events[-1].usage.is_estimated is True


async def test_cli_timeout_becomes_a_retryable_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run(_executable: str, _args: list[str], _timeout_s: float):
        return CliCommandResult(None, "", "", timed_out=True)

    monkeypatch.setattr("revai.providers.cli.kiro.run_cli_command", fake_run)
    events = await _collect(
        KiroCliProvider(executable="/fake/kiro-cli"),
        AnalysisRequest(model="default", user_prompt="review", timeout_s=3),
    )

    assert events[-1].type == "failed"
    assert events[-1].retryable is True
    assert "3s" in events[-1].message


async def test_cli_runner_executes_without_a_shell() -> None:
    result = await run_cli_command(
        sys.executable,
        ["-c", "import sys; print(sys.argv[1])", "$(echo never-expanded)"],
        5,
    )

    assert result.ok is True
    assert result.stdout.strip() == "$(echo never-expanded)"


def test_registry_resolves_every_phase_8_adapter() -> None:
    config = RevaiConfig()
    registry = build_registry(config, Credentials())

    assert isinstance(registry.get(ProviderId.CLAUDE_CODE), ClaudeCodeProvider)
    assert isinstance(registry.get(ProviderId.COPILOT_CLI), CopilotCliProvider)
    assert isinstance(registry.get(ProviderId.KIRO_CLI), KiroCliProvider)
    for provider_id in (
        ProviderId.CLAUDE_CODE,
        ProviderId.COPILOT_CLI,
        ProviderId.KIRO_CLI,
    ):
        provider = registry.get(provider_id)
        assert provider is not None
        assert provider.kind is ProviderKind.CLI


async def test_kiro_adapter_completes_the_existing_ai_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "findings": [
            {
                "severity": "critical",
                "category": "security",
                "title": "Dynamic execution",
                "description": "Untrusted input reaches eval.",
                "rationale": "This permits arbitrary code execution.",
                "file": "src/auth.py",
                "line_start": 11,
                "line_end": 11,
                "rule_id": "eval",
                "confidence": 0.9,
                "suggested_patch": None,
            }
        ]
    }

    async def fake_run(_executable: str, _args: list[str], _timeout_s: float):
        return CliCommandResult(0, f"```json\n{json.dumps(payload)}\n```", "")

    monkeypatch.setattr("revai.providers.cli.kiro.run_cli_command", fake_run)
    config = RevaiConfig()
    config.engine.provider_id = ProviderId.KIRO_CLI
    chunk = CodeChunk(
        path="src/auth.py",
        symbol="authenticate",
        line_start=10,
        line_end=12,
        content="def authenticate(value):\n    return eval(value)",
        estimated_tokens=20,
    )

    result = await run_ai_stage(KiroCliProvider(executable="/fake/kiro-cli"), config, [chunk])

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "eval"
    assert result.usage.is_estimated is True
