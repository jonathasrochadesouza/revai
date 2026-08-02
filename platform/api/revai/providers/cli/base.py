"""Shared, shell-free execution helpers for local CLI providers."""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from dataclasses import dataclass

from revai.providers.base import AnalysisRequest, FailedEvent
from revai.providers.detection import CliSpec, resolve_executable

_ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
_ERROR_LIMIT = 600


@dataclass(frozen=True)
class CliCommandResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    launch_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and self.launch_error is None


def _run_cli_command_blocking(
    executable: str,
    args: tuple[str, ...] | list[str],
    timeout_s: float,
) -> CliCommandResult:
    try:
        completed = subprocess.run(
            [executable, *args],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout_s,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CliCommandResult(None, "", "", timed_out=True)
    except (OSError, ValueError) as exc:
        return CliCommandResult(None, "", "", launch_error=f"{type(exc).__name__}: {exc}")

    return CliCommandResult(
        exit_code=completed.returncode,
        stdout=completed.stdout.decode("utf-8", errors="replace"),
        stderr=completed.stderr.decode("utf-8", errors="replace"),
    )


async def run_cli_command(
    executable: str,
    args: tuple[str, ...] | list[str],
    timeout_s: float,
) -> CliCommandResult:
    """Run one CLI without a shell and without blocking uvicorn's event loop."""
    return await asyncio.to_thread(_run_cli_command_blocking, executable, args, timeout_s)


def executable_for(spec: CliSpec, configured: str | None) -> str | None:
    if configured:
        return configured
    resolved = resolve_executable(spec)
    return resolved[1] if resolved is not None else None


def combined_prompt(request: AnalysisRequest, *, include_json_schema: bool = False) -> str:
    sections: list[str] = []
    if request.system_prompt:
        sections.append(f"<system>\n{request.system_prompt}\n</system>")
    sections.append(request.user_prompt)
    if include_json_schema and request.json_schema is not None:
        schema = json.dumps(request.json_schema, ensure_ascii=False, separators=(",", ":"))
        sections.append(
            f"Return one JSON object matching this schema. Do not wrap it in commentary:\n{schema}"
        )
    return "\n\n".join(sections)


def command_failure(
    result: CliCommandResult,
    *,
    label: str,
    timeout_s: int,
) -> FailedEvent | None:
    if result.timed_out:
        return FailedEvent(
            message=f"{label} did not respond within {timeout_s}s.",
            retryable=True,
        )
    if result.launch_error:
        return FailedEvent(message=f"Could not launch {label}: {result.launch_error}")
    if result.exit_code != 0:
        detail = clean_error(result.stderr or result.stdout)
        return FailedEvent(
            message=f"{label} exited with code {result.exit_code}.{f' {detail}' if detail else ''}",
            retryable=False,
        )
    return None


def clean_error(value: str) -> str:
    """Keep vendor errors actionable without flooding SSE responses or logs."""
    cleaned = " ".join(_ANSI_ESCAPE.sub("", value).split())
    if len(cleaned) <= _ERROR_LIMIT:
        return cleaned
    return f"{cleaned[:_ERROR_LIMIT].rstrip()}…"
