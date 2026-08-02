"""GitHub Copilot CLI programmatic adapter."""

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

_SPEC = next(spec for spec in CLI_SPECS if spec.provider_id is ProviderId.COPILOT_CLI)


class CopilotCliProvider:
    provider_id = ProviderId.COPILOT_CLI
    kind = ProviderKind.CLI

    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable

    async def health(self) -> ProviderHealth:
        return await detect_cli(_SPEC)

    async def analyze(self, request: AnalysisRequest) -> AsyncIterator[ProviderEvent]:
        executable = executable_for(_SPEC, self._executable)
        if executable is None:
            yield FailedEvent(message="GitHub Copilot CLI is not installed or is not on PATH.")
            return

        args = [
            "-p",
            combined_prompt(request, include_json_schema=True),
            "--silent",
            "--stream=off",
            "--no-custom-instructions",
            "--no-ask-user",
            "--model",
            request.model,
        ]
        yield StartedEvent(model=request.model)
        result = await run_cli_command(executable, args, request.timeout_s)
        if failure := command_failure(
            result,
            label="GitHub Copilot CLI",
            timeout_s=request.timeout_s,
        ):
            yield failure
            return

        text, usage = _parse_output(result.stdout)
        if not text:
            yield FailedEvent(message="GitHub Copilot CLI completed without a response.")
            return
        yield DeltaEvent(text=text)
        yield FinishedEvent(text=text, usage=usage)


def _parse_output(stdout: str) -> tuple[str, UsageStats]:
    documents: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            documents.append(parsed)

    texts: list[str] = []
    usage = UsageStats(is_estimated=True)
    for document in documents:
        if (candidate := _text_from(document)) and candidate not in texts:
            texts.append(candidate)
        if raw_usage := _find_usage(document):
            usage = UsageStats(
                input_tokens=_integer(
                    raw_usage.get("input_tokens", raw_usage.get("prompt_tokens"))
                ),
                output_tokens=_integer(
                    raw_usage.get("output_tokens", raw_usage.get("completion_tokens"))
                ),
                cached_tokens=_integer(raw_usage.get("cached_tokens")),
                cost_usd=_cost(raw_usage),
                is_estimated=_cost(raw_usage) is None,
            )

    if texts:
        return "".join(texts), usage
    # `--silent` is Copilot's documented scripting path and returns only the
    # assistant response. Keep JSONL parsing above for versions/configurations that
    # still emit envelopes despite that flag.
    return stdout.strip(), usage


def _text_from(document: dict[str, Any]) -> str | None:
    for key in ("content", "text", "result", "response"):
        value = document.get(key)
        if isinstance(value, str) and value.strip():
            return value
    for key in ("data", "message", "payload"):
        nested = document.get(key)
        if isinstance(nested, dict):
            candidate = _text_from(nested)
            if candidate:
                return candidate
    return None


def _find_usage(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        usage = value.get("usage")
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
