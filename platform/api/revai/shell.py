"""Safe Git Bash integration for Windows child processes.

Some Windows-only developer CLIs are deliberately installed in the Git Bash
profile rather than the Windows process PATH. When Git Bash is available,
RevAI runs child commands through that environment while still passing every
argument separately. No review content is ever interpolated into a shell
command string.
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_GIT_BASH_TIMEOUT_S = 8
_BASH_RESOLVE = 'type -P -- "$1"'


@dataclass(frozen=True)
class GitBashSession:
    """A resolved Git Bash executable plus the user's exported shell environment."""

    executable: str
    environment: dict[str, str]


def _is_windows() -> bool:
    return os.name == "nt"


@lru_cache(maxsize=1)
def git_bash_session() -> GitBashSession | None:
    """Return the cached interactive Git Bash environment on Windows, if present."""
    if not _is_windows():
        return None

    executable = _find_git_bash()
    if executable is None:
        return None

    try:
        completed = subprocess.run(
            [executable, "-lic", "env -0"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=_GIT_BASH_TIMEOUT_S,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.info("Git Bash environment was unavailable: %s", exc)
        return None
    if completed.returncode != 0:
        logger.info("Git Bash environment probe exited with code %s", completed.returncode)
        return None

    exported = _parse_environment(completed.stdout)
    if not exported:
        logger.info("Git Bash did not return a usable environment.")
        return None
    environment = dict(os.environ)
    environment.update(exported)
    return GitBashSession(executable=executable, environment=environment)


def command_for_execution(command: list[str]) -> tuple[list[str], dict[str, str] | None]:
    """Wrap a command in Git Bash when available, preserving exact argv boundaries.

    MSYS2's ``bash -c`` reassembles the trailing arguments into a command line it
    parses again, so bare positional arguments would be re-expanded (globs,
    ``{a,b}`` braces, ``$var``). Passing them quoted inside the script instead
    keeps every argument byte-for-byte identical to the caller's list.
    """
    session = git_bash_session()
    if session is None:
        return command, None
    quoted = " ".join(shlex.quote(argument) for argument in command)
    return (
        [
            session.executable,
            "--noprofile",
            "--norc",
            "-c",
            f"exec {quoted}",
        ],
        session.environment,
    )


def resolve_command(name: str) -> str | None:
    """Resolve a program from Git Bash's PATH, falling back to the process PATH."""
    session = git_bash_session()
    if session is not None:
        try:
            completed = subprocess.run(
                [
                    session.executable,
                    "--noprofile",
                    "--norc",
                    "-c",
                    _BASH_RESOLVE,
                    "revai-resolve",
                    name,
                ],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=_GIT_BASH_TIMEOUT_S,
                env=session.environment,
                shell=False,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.info("Git Bash could not resolve %s: %s", name, exc)
        else:
            resolved = completed.stdout.decode("utf-8", errors="replace").strip()
            if completed.returncode == 0 and resolved:
                return resolved.splitlines()[-1]
    return shutil.which(name)


def bash_exec_failure(completed: subprocess.CompletedProcess[bytes]) -> str | None:
    """Detect an ``exec`` failure reported by the Git Bash wrapper.

    When a command runs through the wrapper, a missing or unlaunchable binary
    never raises ``FileNotFoundError`` — bash itself launches fine and the
    failure surfaces as exit code 126/127 with a "not found" message on
    stderr. Such a result is a launch error, not a normal CLI exit code.
    """
    if completed.returncode not in (126, 127):
        return None
    stderr = completed.stderr.decode("utf-8", errors="replace")
    lowered = stderr.lower()
    if "not found" in lowered or "permission denied" in lowered:
        return stderr.strip() or f"exit code {completed.returncode}"
    return None


def _find_git_bash() -> str | None:
    """Locate the Git for Windows ``bash.exe``, never the WSL one.

    ``shutil.which("bash.exe")`` on a stock Windows box resolves to
    ``C:\\Windows\\system32\\bash.exe`` (WSL) or the ``WindowsApps`` stub, whose
    login environment has nothing to do with Git Bash and whose PATH hides the
    Windows-installed developer CLIs. Git's own install locations are therefore
    preferred, and those WSL shims are rejected outright.
    """
    configured = os.environ.get("REVAI_GIT_BASH_PATH")
    candidates = [configured] if configured else []
    candidates.extend(
        path
        for path in (
            _windows_path("ProgramFiles", "Git", "bin", "bash.exe"),
            _windows_path("ProgramFiles", "Git", "usr", "bin", "bash.exe"),
            _windows_path("LOCALAPPDATA", "Programs", "Git", "bin", "bash.exe"),
            shutil.which("bash.exe"),
            shutil.which("bash"),
        )
        if path
    )
    for candidate in candidates:
        lowered = candidate.lower()
        if not candidate or not Path(candidate).is_file():
            continue
        if lowered.endswith("system32\\bash.exe") or "\\microsoft\\windowsapps\\" in lowered:
            continue
        return str(Path(candidate))
    return None


def _windows_path(variable: str, *parts: str) -> str | None:
    root = os.environ.get(variable)
    return str(Path(root, *parts)) if root else None


def _parse_environment(payload: bytes) -> dict[str, str]:
    environment: dict[str, str] = {}
    for item in payload.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", maxsplit=1)
        decoded_key = key.decode("utf-8", errors="ignore")
        if decoded_key:
            environment[decoded_key] = value.decode("utf-8", errors="replace")
    return environment
