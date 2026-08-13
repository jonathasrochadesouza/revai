"""Kiro CLI headless adapter."""

from __future__ import annotations

import json
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

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
        health = await detect_cli(_SPEC)
        if health.is_usable and health.version and _version_tuple(health.version) < (2, 18):
            return health.model_copy(
                update={
                    "state": "error",
                    "detail": (
                        f"Kiro CLI {health.version} is too old for isolated, "
                        "explicit-model reviews. "
                        "RevAI requires 2.18 or newer."
                    ),
                    "remediation": "kiro-cli update",
                }
            )
        return health

    async def analyze(self, request: AnalysisRequest) -> AsyncIterator[ProviderEvent]:
        executable = executable_for(_SPEC, self._executable)
        if executable is None:
            yield FailedEvent(message="Kiro CLI is not installed or is not on PATH.")
            return

        # A per-invocation workspace prevents global/user MCP configuration from
        # loading. The agent itself has no resources or tools, and the command also
        # explicitly trusts an empty tool set. Nothing in a review needs filesystem,
        # shell, network, or MCP access.
        with tempfile.TemporaryDirectory(prefix="revai-kiro-") as directory:
            workspace = Path(directory)
            agents = workspace / ".kiro" / "agents"
            agents.mkdir(parents=True)
            (agents / "revai-review.json").write_text(
                json.dumps(
                    {
                        "name": "revai-review",
                        "description": "Read-only structured code review for RevAI",
                        "model": request.model,
                        "tools": [],
                        "allowedTools": [],
                        "resources": [],
                        "includeMcpJson": False,
                    }
                ),
                encoding="utf-8",
            )
            args = [
                "chat",
                "--no-interactive",
                "--agent",
                "revai-review",
                "--model",
                request.model,
                "--trust-tools=",
                combined_prompt(request, include_json_schema=True),
            ]
            yield StartedEvent(model=request.model)
            result = await run_cli_command(
                executable,
                args,
                request.timeout_s,
                cwd=workspace,
            )
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


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("-")[0].split(".") if part.isdigit())
