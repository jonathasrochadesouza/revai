"""Claude Code headless adapter."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from revai.domain.enums import ProviderId, ProviderKind
from revai.providers.base import (
    AnalysisRequest,
    DeltaEvent,
    FailedEvent,
    FinishedEvent,
    ProviderEvent,
    ProviderHealth,
    StartedEvent,
    UsageStats,
)
from revai.providers.cli.base import (
    combined_prompt,
    command_failure,
    executable_for,
    run_cli_command,
)
from revai.providers.detection import CLI_SPECS, detect_cli

_SPEC = next(spec for spec in CLI_SPECS if spec.provider_id is ProviderId.CLAUDE_CODE)


class ClaudeCodeProvider:
    provider_id = ProviderId.CLAUDE_CODE
    kind = ProviderKind.CLI

    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable

    async def health(self) -> ProviderHealth:
        return await detect_cli(_SPEC)

    async def analyze(self, request: AnalysisRequest) -> AsyncIterator[ProviderEvent]:
        executable = executable_for(_SPEC, self._executable)
        if executable is None:
            yield FailedEvent(message="Claude Code is not installed or is not on PATH.")
            return

        args = [
            "-p",
            combined_prompt(request),
            "--output-format",
            "json",
            "--model",
            request.model,
            "--tools",
            "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]
        if request.json_schema is not None:
            args.extend(
                [
                    "--json-schema",
                    json.dumps(request.json_schema, ensure_ascii=False, separators=(",", ":")),
                ]
            )

        yield StartedEvent(model=request.model)
        result = await run_cli_command(executable, args, request.timeout_s)
        if failure := command_failure(
            result,
            label="Claude Code",
            timeout_s=request.timeout_s,
        ):
            yield failure
            return

        try:
            envelope = json.loads(result.stdout)
        except json.JSONDecodeError:
            yield FailedEvent(message="Claude Code returned an invalid JSON envelope.")
            return
        if not isinstance(envelope, dict):
            yield FailedEvent(message="Claude Code returned an unexpected JSON envelope.")
            return
        if envelope.get("is_error") is True or envelope.get("subtype") not in {None, "success"}:
            message = envelope.get("result") or envelope.get("error") or "Claude Code failed."
            yield FailedEvent(message=str(message), retryable=False)
            return

        text = _response_text(envelope)
        if text is None:
            yield FailedEvent(message="Claude Code completed without structured output.")
            return
        usage = _usage(envelope)
        session_id = envelope.get("session_id")
        session = session_id if isinstance(session_id, str) else None
        yield DeltaEvent(text=text)
        yield FinishedEvent(text=text, usage=usage, session_id=session)


def _response_text(envelope: dict) -> str | None:
    structured = envelope.get("structured_output")
    if isinstance(structured, dict | list):
        return json.dumps(structured, ensure_ascii=False)
    result = envelope.get("result")
    if isinstance(result, str) and result.strip():
        return result
    if isinstance(result, dict | list):
        return json.dumps(result, ensure_ascii=False)
    return None


def _usage(envelope: dict) -> UsageStats:
    raw = envelope.get("usage")
    usage = raw if isinstance(raw, dict) else {}
    cached = _integer(usage.get("cache_read_input_tokens"))
    cost = envelope.get("total_cost_usd")
    return UsageStats(
        input_tokens=_integer(usage.get("input_tokens")),
        output_tokens=_integer(usage.get("output_tokens")),
        cached_tokens=cached,
        cost_usd=float(cost) if isinstance(cost, int | float) else None,
        is_estimated=not isinstance(cost, int | float),
    )


def _integer(value: object) -> int:
    return value if isinstance(value, int) else 0
