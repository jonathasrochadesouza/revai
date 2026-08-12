"""CLI discovery.

Everything here follows from behaviour measured on a real Windows machine rather
than from the vendors' documentation. The four findings that shaped it:

1. **A bare command name cannot be launched.** ``create_subprocess_exec("copilot")``
   fails with ``FileNotFoundError [WinError 2]`` because ``copilot`` is a ``.BAT``
   shim. Every invocation must go through ``shutil.which`` first and pass the
   resolved absolute path.

2. **Version output is not a bare version.** ``copilot --version`` prints two lines
   — the version and an update notice. ``kiro --version`` prints three: version, git
   hash, architecture. Parsing therefore extracts a semver pattern instead of
   trusting the whole of stdout.

3. **``copilot`` exits 0 even for invalid input.** ``copilot whoami`` returns 0 with
   the error only on stderr. Exit code alone cannot decide health, so stderr is
   inspected too.

4. **An unrecognised flag can hang.** ``copilot --definitely-not-a-flag`` never
   returned. Every call therefore has a hard timeout and ``stdin=DEVNULL``, so a CLI
   waiting for input fails fast instead of blocking a request forever.

5. **asyncio cannot spawn subprocesses under uvicorn on Windows.** uvicorn installs
   ``WindowsSelectorEventLoopPolicy``, and a selector loop raises a bare
   ``NotImplementedError`` from ``create_subprocess_exec``. Detection therefore runs
   ``subprocess.run`` on a worker thread. This was found by calling the real server:
   the test suite runs on the proactor loop and never saw it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field

from revai.domain.enums import ProviderId, ProviderKind
from revai.providers.base import HealthState, ProviderHealth
from revai.shell import command_for_execution, git_bash_session, resolve_command

logger = logging.getLogger(__name__)

# Long enough for a cold start on Windows, short enough that a hung CLI surfaces
# as an error the user can act on rather than a stalled page.
PROBE_TIMEOUT_S = 20.0

# Matches 1.2, v1.2, 1.2.3 and 1.2.3-beta.1 anywhere in the output.
#
# Three details are load-bearing, each pinned by a test:
#
#   `(?:^|[^\w.])`  rejects a preceding word character, so `abc1.2.3` yields nothing
#                   instead of the misleading `2.3`. A preceding dot is rejected too,
#                   which stops `.windows.1` being read as a version of its own.
#   `v?`            outside the capture group, so `v3.4` is matched but reported as
#                   `3.4`. A `\b` here would fail — `v` and `3` are both word
#                   characters, so there is no boundary between them.
#   `[-+][A-Za-z]`  a prerelease has to start with a letter, so `1.2.3-beta.1` is
#                   kept whole while `git version 2.54.0.windows.1` still yields
#                   `2.54.0` rather than swallowing the platform suffix.
#
# No trailing lookahead: `copilot` prints `1.0.69.` with a full stop, and anything
# stricter would reject it.
_SEMVER = re.compile(r"(?:^|[^\w.])v?(\d+\.\d+(?:\.\d+)?(?:[-+][A-Za-z][\w.]*)?)")

# Copilot reports failures on stderr while still exiting 0, so these markers are
# the only reliable signal.
_ERROR_MARKERS = ("error:", "error ", "not supported", "not authenticated", "unauthor")


@dataclass(frozen=True)
class CliSpec:
    """How to detect and authenticate one CLI agent."""

    provider_id: ProviderId
    label: str

    executables: tuple[str, ...]
    """Names to try, in order of preference.

    ``kiro-cli`` comes before ``kiro`` deliberately: on this machine ``kiro``
    resolves to the **IDE** launcher (0.12.333) while ``kiro-cli`` is the actual
    agent (2.14.1). Detecting the wrong one would report a version that has nothing
    to do with the CLI being driven.
    """

    version_args: tuple[str, ...] = ("--version",)

    auth_args: tuple[str, ...] | None = None
    """Command that reports authentication state, when the CLI has one."""

    auth_is_json: bool = False
    """Whether ``auth_args`` emits JSON that can be inspected structurally."""

    install_hint: str = ""
    login_hint: str = ""

    notes: str = ""
    """Caveat surfaced in the UI — e.g. Kiro emits no structured output."""

    aliases: tuple[str, ...] = field(default_factory=tuple)
    """Executables that must NOT be mistaken for this CLI."""

    executable_env: str | None = None
    """Optional environment variable containing an explicit executable path."""


CLI_SPECS: tuple[CliSpec, ...] = (
    CliSpec(
        provider_id=ProviderId.CLAUDE_CODE,
        label="Claude Code",
        executables=("claude",),
        # The cleanest of the three: JSON output and a real exit code.
        auth_args=("auth", "status"),
        auth_is_json=True,
        install_hint="winget install Anthropic.ClaudeCode",
        login_hint="claude auth login",
        notes=(
            "Best structured output of the three CLIs: a full JSON envelope with "
            "cost and token counts."
        ),
    ),
    CliSpec(
        provider_id=ProviderId.COPILOT_CLI,
        label="GitHub Copilot CLI",
        executables=("copilot",),
        # No whoami, and exit codes are unreliable — see module docstring.
        auth_args=None,
        install_hint="npm install -g @github/copilot",
        login_hint="copilot auth login",
        notes=(
            "Ships no authentication-status command, and returns exit code 0 even for "
            "invalid input. RevAI reports its auth state as unknown rather than guessing."
        ),
    ),
    CliSpec(
        provider_id=ProviderId.KIRO_CLI,
        label="Kiro CLI",
        # kiro-cli first: `kiro` is the IDE launcher, not the agent.
        executables=("kiro-cli",),
        aliases=("kiro",),
        auth_args=("whoami", "--format", "json"),
        auth_is_json=True,
        install_hint="irm https://cli.kiro.dev/install.ps1 | iex",
        login_hint="kiro-cli login",
        notes=(
            "Emits plain text in headless mode, so findings have to be extracted from "
            "prose. Reviews produced this way are marked as lower fidelity."
        ),
        executable_env="REVAI_KIRO_CLI_PATH",
    ),
)


# ===========================================================================
# Process helpers
# ===========================================================================


@dataclass(frozen=True)
class CommandResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    launch_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and self.launch_error is None

    @property
    def combined(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()

    @property
    def looks_like_error(self) -> bool:
        """Whether the output reads like a failure despite the exit code.

        Needed because Copilot CLI exits 0 while printing an error to stderr.
        """
        lowered = self.stderr.lower()
        return any(marker in lowered for marker in _ERROR_MARKERS)


def _run_command_blocking(
    executable: str,
    args: tuple[str, ...] | list[str],
    timeout_s: float,
) -> CommandResult:
    """Synchronous half of :func:`run_command`. Runs on a worker thread."""
    try:
        # Safe by construction: an absolute path from `shutil.which`, a fixed argument
        # list, and `shell=False`, so nothing here is interpreted by a shell.
        command, environment = command_for_execution([executable, *args])
        completed = subprocess.run(
            command,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout_s,
            env=environment,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # `subprocess.run` already killed and reaped the child before raising, so
        # nothing leaks here. Copilot CLI hangs on an unrecognised flag, which is
        # exactly the case this covers.
        return CommandResult(None, "", "", timed_out=True)
    except (OSError, ValueError) as exc:
        # Reached when the path is stale or not executable. Not an exception the
        # caller should have to handle — it is a detection result.
        return CommandResult(None, "", "", launch_error=f"{type(exc).__name__}: {exc}")

    return CommandResult(
        exit_code=completed.returncode,
        stdout=completed.stdout.decode("utf-8", errors="replace"),
        stderr=completed.stderr.decode("utf-8", errors="replace"),
    )


async def run_command(
    executable: str,
    args: tuple[str, ...] | list[str],
    timeout_s: float = PROBE_TIMEOUT_S,
) -> CommandResult:
    """Run a command without a shell, with a hard timeout.

    ``executable`` must already be an absolute path from :func:`resolve_executable`.
    ``stdin`` is closed so a CLI that decides to prompt fails immediately instead of
    holding the event loop open.

    Uses ``subprocess.run`` on a worker thread rather than
    ``asyncio.create_subprocess_exec``. This is not a stylistic choice: uvicorn
    installs ``WindowsSelectorEventLoopPolicy``, and a selector loop cannot spawn
    subprocesses at all — it raises a bare ``NotImplementedError``. That failure was
    invisible under pytest, which runs on the proactor loop, and only appeared as a
    500 from the real server. Threading the blocking call keeps detection working on
    every loop implementation, and three short-lived threads is a trivial cost for a
    probe that runs on demand.
    """
    return await asyncio.to_thread(_run_command_blocking, executable, args, timeout_s)


def resolve_executable(spec: CliSpec) -> tuple[str, str] | None:
    """Find the CLI from an explicit override or PATH.

    Returns ``(name, absolute_path)`` for the first candidate that resolves, or
    ``None``. The absolute path is what makes the subsequent ``exec`` work on
    Windows shims.
    """
    if spec.executable_env and (configured := os.environ.get(spec.executable_env)):
        resolved = _resolve_command(configured)
        if resolved:
            return spec.executables[0], resolved

    for name in spec.executables:
        resolved = _resolve_command(name)
        if resolved:
            return name, resolved
    return None


def _resolve_command(name: str) -> str | None:
    """Keep the normal PATH lookup fast; delegate only when Git Bash is active."""
    return resolve_command(name) if git_bash_session() is not None else shutil.which(name)


def parse_version(output: str) -> str | None:
    """Extract a version from noisy CLI output.

    ``copilot --version`` emits an update notice on a second line and ``kiro
    --version`` emits a git hash and an architecture, so the whole of stdout is
    never the version.
    """
    match = _SEMVER.search(output)
    return match.group(1) if match else None


# ===========================================================================
# Detection
# ===========================================================================


async def detect_cli(spec: CliSpec) -> ProviderHealth:
    """Probe one CLI. Never raises."""
    base = {
        "provider_id": spec.provider_id,
        "kind": ProviderKind.CLI,
        "adapter_ready": True,
    }

    resolved = resolve_executable(spec)
    if resolved is None:
        return ProviderHealth(
            **base,
            state=HealthState.NOT_FOUND,
            detail=_not_found_detail(spec),
            remediation=spec.install_hint or None,
        )

    name, path = resolved

    version_result = await run_command(path, spec.version_args)
    if version_result.timed_out:
        return ProviderHealth(
            **base,
            executable=path,
            state=HealthState.ERROR,
            detail=(
                f"`{name} {' '.join(spec.version_args)}` did not respond within "
                f"{PROBE_TIMEOUT_S:g}s. The CLI may be waiting for input."
            ),
        )
    if version_result.launch_error:
        return ProviderHealth(
            **base,
            executable=path,
            state=HealthState.ERROR,
            detail=f"Could not launch {path}: {version_result.launch_error}",
        )

    version = parse_version(version_result.combined)

    # No auth command exists for this CLI — report unknown rather than assume.
    if spec.auth_args is None:
        return ProviderHealth(
            **base,
            executable=path,
            version=version,
            state=HealthState.UNKNOWN,
            detail=spec.notes or "Authentication state cannot be determined.",
            remediation=spec.login_hint or None,
        )

    auth_result = await run_command(path, spec.auth_args)
    state, detail = _interpret_auth(spec, auth_result)

    return ProviderHealth(
        **base,
        executable=path,
        version=version,
        state=state,
        detail=detail,
        remediation=spec.login_hint if state is HealthState.NEEDS_AUTH else None,
    )


def _not_found_detail(spec: CliSpec) -> str:
    """Explain a miss, including the near-miss case.

    Worth the extra sentence: finding ``kiro`` and reporting "Kiro CLI not
    installed" looks like a bug to anyone who has the IDE open.
    """
    detail = f"`{spec.executables[0]}` was not found on PATH."
    for alias in spec.aliases:
        if _resolve_command(alias):
            detail += (
                f" Note that `{alias}` *is* installed, but it is a different"
                f" executable — `{spec.executables[0]}` is the agent RevAI drives."
            )
            break
    return detail


def _interpret_auth(spec: CliSpec, result: CommandResult) -> tuple[HealthState, str | None]:
    """Turn an auth-probe result into a state.

    Ordering matters. Timeouts and launch failures are checked first, then the
    structured JSON path, and only then exit codes — because an exit code is the
    least trustworthy of the three.
    """
    if result.timed_out:
        return (
            HealthState.ERROR,
            f"`{' '.join(spec.auth_args or ())}` timed out after {PROBE_TIMEOUT_S:g}s.",
        )
    if result.launch_error:
        return HealthState.ERROR, result.launch_error

    if spec.auth_is_json:
        parsed = _try_json(result.stdout)
        if parsed is not None:
            return _interpret_auth_json(parsed, result)

    # Fall back to exit code plus stderr inspection.
    if result.ok and not result.looks_like_error:
        return HealthState.READY, None

    message = _first_line(result.stderr) or _first_line(result.stdout)
    return HealthState.NEEDS_AUTH, message or "Not signed in."


def _interpret_auth_json(parsed: dict, result: CommandResult) -> tuple[HealthState, str | None]:
    """Read a structured auth response.

    ``kiro-cli whoami --format json`` returns ``{"account": null}`` with exit 1 when
    signed out, and an account object when signed in. Checking the payload is more
    reliable than the exit code, and it also tells us *who* is signed in.
    """
    account = parsed.get("account")
    if account:
        who = _describe_account(account)
        return HealthState.READY, f"Signed in{f' as {who}' if who else ''}."

    for key in ("loggedIn", "authenticated", "isAuthenticated", "isLoggedIn"):
        value = parsed.get(key)
        if value is True:
            return HealthState.READY, "Signed in."
        if value is False:
            return HealthState.NEEDS_AUTH, "Not signed in."

    # An explicit null account is a definitive "signed out".
    if "account" in parsed:
        return HealthState.NEEDS_AUTH, "Not signed in."

    # Shape we do not recognise — defer to the exit code.
    if result.ok:
        return HealthState.READY, None
    return HealthState.NEEDS_AUTH, _first_line(result.stderr) or "Not signed in."


def _describe_account(account: object) -> str | None:
    if isinstance(account, str):
        return account
    if isinstance(account, dict):
        for key in ("email", "username", "login", "name", "id"):
            value = account.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _try_json(text: str) -> dict | None:
    """Parse JSON, tolerating leading noise some CLIs print before the payload."""
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _first_line(text: str) -> str | None:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return None


async def detect_all_clis() -> list[ProviderHealth]:
    """Probe every known CLI concurrently.

    Concurrent because three sequential probes with a 20s ceiling each could block a
    request for a minute; in parallel the worst case is one timeout.
    """
    return list(await asyncio.gather(*(detect_cli(spec) for spec in CLI_SPECS)))
