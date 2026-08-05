"""CLI detection tests.

Every case here corresponds to behaviour measured on a real machine rather than to
documentation. The awkward ones are the point:

* Copilot CLI exits **0** for invalid input, so exit codes cannot decide health.
* An unrecognised flag can hang forever, so timeouts are mandatory.
* ``kiro`` resolves to the Kiro **IDE**; ``kiro-cli`` is the agent.
"""

from __future__ import annotations

import asyncio
import sys

import pytest

from revai.domain.enums import ProviderId, ProviderKind
from revai.providers.base import HealthState
from revai.providers.detection import (
    CLI_SPECS,
    CommandResult,
    detect_cli,
    parse_version,
    resolve_executable,
    run_command,
)

# ---------------------------------------------------------------------------
# Version parsing — driven by real output
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        # Exact strings captured from this machine.
        ("GitHub Copilot CLI 1.0.69.\nRun 'copilot update' to check for updates.", "1.0.69"),
        ("kiro-cli-chat 2.14.1", "2.14.1"),
        ("0.12.333\nc7e35289ee989c7c61a1e9440d48b51361d95a10\nx64", "0.12.333"),
        ("git version 2.54.0.windows.1", "2.54.0"),
        # Documented shapes for CLIs not installed here.
        ("2.1.211 (Claude Code)", "2.1.211"),
        ("v3.4", "3.4"),
        ("1.2.3-beta.1", "1.2.3-beta.1"),
        # No version present.
        ("command not found", None),
        ("", None),
        # A version glued to a word is not a version. `\b` would wrongly extract
        # "2.3" here, which is how the original pattern was found to be too loose.
        ("abc1.2.3", None),
    ],
)
def test_parse_version_handles_real_cli_output(output: str, expected: str | None) -> None:
    assert parse_version(output) == expected


def test_parse_version_does_not_swallow_a_platform_suffix() -> None:
    """`git version 2.54.0.windows.1` is 2.54.0, not 2.54.0.windows.1.

    The prerelease branch requires a letter after the separator, which is what keeps
    `-beta.1` while rejecting `.windows.1`.
    """
    assert parse_version("git version 2.54.0.windows.1") == "2.54.0"


def test_parse_version_accepts_a_leading_v() -> None:
    """`\\b` cannot be used here: `v` and `3` are both word characters."""
    assert parse_version("v3.4") == "3.4"
    assert parse_version("version v10.2.1") == "10.2.1"


def test_parse_version_ignores_the_update_notice() -> None:
    """Copilot appends a second line; the whole of stdout is never the version."""
    noisy = "GitHub Copilot CLI 1.0.69.\nRun 'copilot update' to check for updates."

    assert parse_version(noisy) == "1.0.69"


def test_parse_version_ignores_a_git_hash() -> None:
    """A 40-char hex hash must not be mistaken for a version."""
    assert parse_version("0.12.333\nc7e35289ee989c7c61a1e9440d48b51361d95a10") == "0.12.333"


# ---------------------------------------------------------------------------
# CommandResult semantics
# ---------------------------------------------------------------------------


def test_ok_requires_a_zero_exit_and_no_failure() -> None:
    assert CommandResult(0, "fine", "").ok is True
    assert CommandResult(1, "", "boom").ok is False
    assert CommandResult(None, "", "", timed_out=True).ok is False
    assert CommandResult(None, "", "", launch_error="WinError 2").ok is False


def test_looks_like_error_catches_copilots_zero_exit_failure() -> None:
    """The exact case that makes exit codes untrustworthy for Copilot.

    Measured: `copilot whoami` exits 0 and puts the error only on stderr.
    """
    result = CommandResult(
        exit_code=0,
        stdout="",
        stderr='error: Invalid command format.\n\nDid you mean: copilot -i "whoami"?',
    )

    assert result.ok is True  # the exit code says success...
    assert result.looks_like_error is True  # ...but the output says otherwise


def test_looks_like_error_catches_the_classic_pat_rejection() -> None:
    """Also measured on this machine: a classic PAT in GITHUB_TOKEN, exit 0."""
    result = CommandResult(
        exit_code=0,
        stdout="",
        stderr="Error: Classic Personal Access Tokens (ghp_) are not supported by Copilot.",
    )

    assert result.looks_like_error is True


def test_clean_output_is_not_flagged_as_an_error() -> None:
    result = CommandResult(0, "GitHub Copilot CLI 1.0.69.", "")

    assert result.looks_like_error is False


# ---------------------------------------------------------------------------
# Process execution
# ---------------------------------------------------------------------------


async def test_run_command_reports_a_launch_failure_instead_of_raising() -> None:
    """A missing binary is a detection result, not an exception."""
    result = await run_command("this-binary-does-not-exist-anywhere", ["--version"])

    assert result.launch_error is not None
    assert result.ok is False


async def test_run_command_enforces_its_timeout() -> None:
    """Mandatory because `copilot --definitely-not-a-flag` never returned.

    A hung CLI must fail fast rather than hold the event loop open.
    """
    import sys

    result = await run_command(
        sys.executable,
        ["-c", "import time; time.sleep(30)"],
        timeout_s=0.5,
    )

    assert result.timed_out is True
    assert result.ok is False


async def test_run_command_captures_both_streams() -> None:
    import sys

    result = await run_command(
        sys.executable,
        ["-c", "import sys; print('to stdout'); print('to stderr', file=sys.stderr)"],
    )

    assert "to stdout" in result.stdout
    assert "to stderr" in result.stderr
    assert result.exit_code == 0


async def test_run_command_closes_stdin() -> None:
    """With stdin closed, a CLI that prompts fails instead of blocking forever."""
    import sys

    result = await run_command(
        sys.executable,
        ["-c", "import sys; print(len(sys.stdin.read()))"],
        timeout_s=5.0,
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "0"


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------


def test_kiro_cli_is_detected_not_the_kiro_ide() -> None:
    """`kiro` is the IDE launcher; `kiro-cli` is the agent RevAI drives.

    Detecting the wrong one would report a version unrelated to the CLI, which on
    this machine differs by two major versions (IDE 0.12.x vs CLI 2.14.x).
    """
    spec = next(s for s in CLI_SPECS if s.provider_id is ProviderId.KIRO_CLI)

    assert spec.executables == ("kiro-cli",)
    assert "kiro" in spec.aliases


def test_copilot_declares_no_auth_command() -> None:
    """It genuinely has none, so the spec must not invent one."""
    spec = next(s for s in CLI_SPECS if s.provider_id is ProviderId.COPILOT_CLI)

    assert spec.auth_args is None


def test_claude_code_uses_its_json_auth_check() -> None:
    spec = next(s for s in CLI_SPECS if s.provider_id is ProviderId.CLAUDE_CODE)

    assert spec.auth_args == ("auth", "status")
    assert spec.auth_is_json is True


def test_every_spec_offers_remediation() -> None:
    """A "not installed" message with no fix is a dead end for the user."""
    for spec in CLI_SPECS:
        assert spec.install_hint, f"{spec.provider_id} has no install hint"
        assert spec.login_hint, f"{spec.provider_id} has no login hint"


def test_resolve_executable_returns_none_when_absent() -> None:
    from revai.providers.detection import CliSpec

    spec = CliSpec(
        provider_id=ProviderId.CLAUDE_CODE,
        label="nope",
        executables=("definitely-not-installed-xyz",),
    )

    assert resolve_executable(spec) is None

def test_resolve_executable_prefers_an_explicit_path(monkeypatch) -> None:
    from revai.providers.detection import CliSpec

    spec = CliSpec(
        provider_id=ProviderId.KIRO_CLI,
        label="Kiro CLI",
        executables=("kiro-cli",),
        executable_env="REVAI_KIRO_CLI_PATH",
    )
    monkeypatch.setenv("REVAI_KIRO_CLI_PATH", r"C:\Tools\kiro-cli.exe")
    monkeypatch.setattr(
        "revai.providers.detection.shutil.which",
        lambda candidate: r"C:\Tools\kiro-cli.exe"
        if candidate == r"C:\Tools\kiro-cli.exe"
        else None,
    )

    assert resolve_executable(spec) == ("kiro-cli", r"C:\Tools\kiro-cli.exe")



# ---------------------------------------------------------------------------
# Detection contract
# ---------------------------------------------------------------------------


async def test_detect_cli_never_raises_for_a_missing_binary() -> None:
    from revai.providers.detection import CliSpec

    spec = CliSpec(
        provider_id=ProviderId.CLAUDE_CODE,
        label="Ghost",
        executables=("definitely-not-installed-xyz",),
        install_hint="install it somehow",
    )

    health = await detect_cli(spec)

    assert health.state is HealthState.NOT_FOUND
    assert health.kind is ProviderKind.CLI
    assert health.remediation == "install it somehow"
    assert health.is_usable is False


async def test_detect_cli_explains_a_near_miss() -> None:
    """If `kiro` is installed but `kiro-cli` is not, say so.

    Otherwise "Kiro CLI not installed" looks like a bug to someone with the IDE open.
    No subprocess runs here: the lookup misses, so detection returns immediately.
    """
    import shutil

    from revai.providers.detection import CliSpec

    if shutil.which("kiro") is None:
        pytest.skip("the Kiro IDE is not installed on this machine")

    spec = CliSpec(
        provider_id=ProviderId.KIRO_CLI,
        label="Kiro CLI",
        executables=("kiro-cli-not-real",),
        aliases=("kiro",),
    )

    health = await detect_cli(spec)

    assert health.state is HealthState.NOT_FOUND
    assert health.detail is not None
    assert "different executable" in health.detail


async def test_detect_cli_uses_python_as_a_stand_in_cli(monkeypatch) -> None:
    """Exercise the whole happy path without depending on a vendor CLI.

    `sys.executable` is a real binary that reports a version, so this covers
    resolution, execution and parsing in well under a second — where probing
    `copilot` alone can take several.
    """
    import sys

    from revai.providers.detection import CliSpec

    spec = CliSpec(
        provider_id=ProviderId.CLAUDE_CODE,
        label="Stand-in",
        executables=("python-stand-in",),
        version_args=("--version",),
        auth_args=None,
        install_hint="n/a",
        login_hint="n/a",
        notes="stand-in",
    )
    monkeypatch.setattr(
        "revai.providers.detection.shutil.which",
        lambda name: sys.executable if name == "python-stand-in" else None,
    )

    health = await detect_cli(spec)

    # No auth command declared, so the honest answer is UNKNOWN.
    assert health.state is HealthState.UNKNOWN
    assert health.executable == sys.executable
    assert health.version is not None  # `python --version` prints "Python 3.12.x"


async def test_detect_cli_reads_a_json_auth_response(monkeypatch) -> None:
    """The kiro-cli shape: `{"account": null}` with a non-zero exit.

    Faked rather than measured live, because the real answer depends on whether the
    developer happens to be signed in.
    """
    from revai.providers.detection import CliSpec, CommandResult

    spec = CliSpec(
        provider_id=ProviderId.KIRO_CLI,
        label="Kiro CLI",
        executables=("fake-kiro",),
        auth_args=("whoami", "--format", "json"),
        auth_is_json=True,
        install_hint="n/a",
        login_hint="kiro-cli login",
    )
    monkeypatch.setattr("revai.providers.detection.shutil.which", lambda _: r"C:\fake\kiro-cli.exe")

    async def fake_run(_executable, args, timeout_s=None):
        if "whoami" in args:
            # Exactly what the real CLI returned when signed out.
            return CommandResult(1, '{"account":null}', "")
        return CommandResult(0, "kiro-cli-chat 2.14.1", "")

    monkeypatch.setattr("revai.providers.detection.run_command", fake_run)

    health = await detect_cli(spec)

    assert health.state is HealthState.NEEDS_AUTH
    assert health.version == "2.14.1"
    assert health.remediation == "kiro-cli login"


async def test_detect_cli_reports_a_signed_in_account(monkeypatch) -> None:
    """A populated account object means READY, and the user is named."""
    from revai.providers.detection import CliSpec, CommandResult

    spec = CliSpec(
        provider_id=ProviderId.KIRO_CLI,
        label="Kiro CLI",
        executables=("fake-kiro",),
        auth_args=("whoami", "--format", "json"),
        auth_is_json=True,
    )
    monkeypatch.setattr("revai.providers.detection.shutil.which", lambda _: r"C:\fake.exe")

    async def fake_run(_executable, args, timeout_s=None):
        if "whoami" in args:
            return CommandResult(0, '{"account":{"email":"dev@example.com"}}', "")
        return CommandResult(0, "kiro-cli-chat 2.14.1", "")

    monkeypatch.setattr("revai.providers.detection.run_command", fake_run)

    health = await detect_cli(spec)

    assert health.state is HealthState.READY
    assert health.detail is not None
    assert "dev@example.com" in health.detail


async def test_detect_cli_reports_a_hung_cli_as_an_error(monkeypatch) -> None:
    """The `copilot --definitely-not-a-flag` case, faked.

    A timeout must surface as ERROR with an actionable message, not as a stall.
    """
    from revai.providers.detection import CliSpec, CommandResult

    spec = CliSpec(
        provider_id=ProviderId.COPILOT_CLI,
        label="Copilot",
        executables=("fake-copilot",),
    )
    monkeypatch.setattr("revai.providers.detection.shutil.which", lambda _: r"C:\fake.exe")

    async def fake_run(_executable, _args, timeout_s=None):
        return CommandResult(None, "", "", timed_out=True)

    monkeypatch.setattr("revai.providers.detection.run_command", fake_run)

    health = await detect_cli(spec)

    assert health.state is HealthState.ERROR
    assert health.detail is not None
    assert "waiting for input" in health.detail


@pytest.mark.cli
async def test_detect_all_clis_against_the_real_machine() -> None:
    """Integration check. Excluded by default — see `addopts` in pyproject.toml.

    Asserts the shape rather than specific states, since what is installed varies
    from machine to machine.
    """
    from revai.providers.detection import detect_all_clis

    healths = await detect_all_clis()

    assert len(healths) == len(CLI_SPECS)
    for health in healths:
        assert health.kind is ProviderKind.CLI
        assert health.adapter_ready is True
        if health.state is not HealthState.NOT_FOUND:
            assert health.executable is not None


# ---------------------------------------------------------------------------
# Event loop compatibility
# ---------------------------------------------------------------------------


def test_run_command_works_on_a_selector_event_loop() -> None:
    """Regression: uvicorn's loop on Windows cannot spawn subprocesses.

    uvicorn installs ``WindowsSelectorEventLoopPolicy``, whose loop raises a bare
    ``NotImplementedError`` from ``create_subprocess_exec``. The original
    implementation used exactly that call, so ``GET /api/providers`` returned 500 on
    the real server while the whole suite stayed green — pytest-asyncio runs on the
    proactor loop.

    Written with an explicit selector loop rather than a marker so it reproduces the
    production loop on every platform, and is deliberately synchronous so the
    ambient pytest-asyncio loop cannot be substituted for it.
    """
    loop = asyncio.SelectorEventLoop()
    try:
        result = loop.run_until_complete(
            run_command(sys.executable, ("-c", "print('selector loop ok')"))
        )
    finally:
        loop.close()

    assert result.ok, f"launch_error={result.launch_error} timed_out={result.timed_out}"
    assert "selector loop ok" in result.stdout


# ---------------------------------------------------------------------------
# Health state semantics
# ---------------------------------------------------------------------------


def test_unknown_counts_as_usable() -> None:
    """Otherwise Copilot CLI would be permanently unusable.

    It has no way to report its auth state, so refusing to try would be worse than
    attempting and surfacing a real error.
    """
    assert HealthState.UNKNOWN.is_usable is True
    assert HealthState.READY.is_usable is True
    assert HealthState.NEEDS_AUTH.is_usable is False
    assert HealthState.NOT_FOUND.is_usable is False
    assert HealthState.ERROR.is_usable is False
