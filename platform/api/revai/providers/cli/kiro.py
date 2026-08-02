"""Kiro CLI headless adapter."""

from __future__ import annotations

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

_SPEC = next(spec for spec in CLI_SPECS if spec.provider_id is ProviderId.KIRO_CLI)


class KiroCliProvider:
    provider_id = ProviderId.KIRO_CLI
    kind = ProviderKind.CLI

    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable

    async def health(self) -> ProviderHealth:
        return await detect_cli(_SPEC)

    async def analyze(self, request: AnalysisRequest) -> AsyncIterator[ProviderEvent]:
        executable = executable_for(_SPEC, self._executable)
        if executable is None:
            yield FailedEvent(message="Kiro CLI is not installed or is not on PATH.")
            return

        args = [
            "chat",
            "--no-interactive",
            combined_prompt(request, include_json_schema=True),
        ]
        yield StartedEvent(model=request.model)
        result = await run_cli_command(executable, args, request.timeout_s)
        if failure := command_failure(
            result,
            label="Kiro CLI",
            timeout_s=request.timeout_s,
        ):
            yield failure
            return

        text = result.stdout.strip()
        if not text:
            yield FailedEvent(message="Kiro CLI completed without a response.")
            return
        usage = UsageStats(is_estimated=True)
        yield DeltaEvent(text=text)
        yield FinishedEvent(text=text, usage=usage)
