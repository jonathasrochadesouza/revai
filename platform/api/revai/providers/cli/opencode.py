"""opencode CLI headless adapter."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

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

_SPEC = next(spec for spec in CLI_SPECS if spec.provider_id is ProviderId.OPENCODE_CLI)


class OpencodeCliProvider:
    provider_id = ProviderId.OPENCODE_CLI
    kind = ProviderKind.CLI

    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable

    async def health(self) -> ProviderHealth:
        return await detect_cli(_SPEC)

    async def analyze(self, request: AnalysisRequest) -> AsyncIterator[ProviderEvent]:
        executable = executable_for(_SPEC, self._executable)
        if executable is None:
            yield FailedEvent(message="opencode CLI is not installed or is not on PATH.")
            return

        args = [
            "run",
            "--model",
            request.model,
            "--format",
            "json",
            combined_prompt(request, include_json_schema=True),
        ]
        yield StartedEvent(model=request.model)
        result = await run_cli_command(executable, args, request.timeout_s)
        if failure := command_failure(
            result,
            label="opencode CLI",
            timeout_s=request.timeout_s,
        ):
            yield failure
            return

        text, usage = _parse_output(result.stdout)
        if not text:
            yield FailedEvent(message="opencode CLI completed without a response.")
            return
        yield DeltaEvent(text=text)
        yield FinishedEvent(text=text, usage=usage)


def _parse_output(stdout: str) -> tuple[str, UsageStats]:
    """Extract the assistant's reply from opencode's newline-delimited JSON events.

    ``--format json`` streams one JSON object per line (session, message part,
    step-finish, etc). The concatenated text parts of assistant messages are the
    review response; a trailing usage payload, when present, is kept for cost
    reporting.
    """
    texts: list[str] = []
    usage = UsageStats(is_estimated=True)
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue

        if candidate := _text_from(event):
            texts.append(candidate)
        if raw_usage := _find_usage(event):
            usage = UsageStats(
                input_tokens=_integer(raw_usage.get("input", raw_usage.get("input_tokens"))),
                output_tokens=_integer(raw_usage.get("output", raw_usage.get("output_tokens"))),
                cached_tokens=_integer(raw_usage.get("cache", {}).get("read"))
                if isinstance(raw_usage.get("cache"), dict)
                else _integer(raw_usage.get("cached_tokens")),
                cost_usd=_cost(raw_usage),
                is_estimated=_cost(raw_usage) is None,
            )

    if texts:
        return "".join(texts), usage
    # No recognised event shape matched — fall back to raw stdout rather than
    # silently dropping a response the model actually produced.
    return stdout.strip(), usage


def _text_from(event: dict[str, Any]) -> str | None:
    part = event.get("part")
    if isinstance(part, dict) and part.get("type") == "text":
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            return text

    info = event.get("info")
    if isinstance(info, dict):
        role = info.get("role")
        text = info.get("text")
        if role == "assistant" and isinstance(text, str) and text.strip():
            return text

    for key in ("text", "content", "message"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _find_usage(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        usage = value.get("tokens", value.get("usage"))
        if isinstance(usage, dict):
            return usage
        for nested in value.values():
            found = _find_usage(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_usage(nested)
            if found is not None:
                return found
    return None


def _integer(value: object) -> int:
    return value if isinstance(value, int) else 0


def _cost(usage: dict[str, Any]) -> float | None:
    value = usage.get("cost_usd", usage.get("cost"))
    return float(value) if isinstance(value, int | float) else None
