"""Git Bash command-environment contracts."""

from __future__ import annotations

import subprocess

from revai.shell import GitBashSession, command_for_execution, resolve_command


def test_git_bash_wraps_exact_argv_without_interpolating_review_content(monkeypatch) -> None:
    session = GitBashSession(
        executable=r"C:\Program Files\Git\bin\bash.exe",
        environment={"PATH": "/c/Users/dev/.local/bin:/usr/bin"},
    )
    monkeypatch.setattr("revai.shell.git_bash_session", lambda: session)
    command = ["kiro-cli", "chat", "$(must-not-run) Review app.py"]

    wrapped, environment = command_for_execution(command)

    # Every argument is quoted inside the `-c` script: MSYS bash re-parses the
    # trailing argv, so bare `$(...)`, globs and braces would be expanded.
    assert wrapped == [
        r"C:\Program Files\Git\bin\bash.exe",
        "--noprofile",
        "--norc",
        "-c",
        "exec kiro-cli chat '$(must-not-run) Review app.py'",
    ]
    assert environment == session.environment


def test_git_bash_wrapper_is_injection_safe(monkeypatch) -> None:
    """Quoted arguments must survive bash's second parse byte-for-byte."""
    session = GitBashSession(
        executable=r"C:\Program Files\Git\bin\bash.exe",
        environment={"PATH": "/usr/bin"},
    )
    monkeypatch.setattr("revai.shell.git_bash_session", lambda: session)
    tricky = ["echo", "a{b,c}d", "*", "with space"]
    wrapped, environment = command_for_execution(tricky)

    result = subprocess.run(wrapped, capture_output=True, text=True, env=environment)

    assert result.returncode == 0
    assert result.stdout == "a{b,c}d * with space\n"


def test_git_bash_resolves_kiro_cli_from_its_own_path(monkeypatch) -> None:
    session = GitBashSession(
        executable=r"C:\Program Files\Git\bin\bash.exe",
        environment={"PATH": "/c/Users/dev/.local/bin:/usr/bin"},
    )
    monkeypatch.setattr("revai.shell.git_bash_session", lambda: session)
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        return subprocess.CompletedProcess(command, 0, b"/c/Users/dev/.local/bin/kiro-cli\n", b"")

    monkeypatch.setattr("revai.shell.subprocess.run", fake_run)

    assert resolve_command("kiro-cli") == "/c/Users/dev/.local/bin/kiro-cli"
    assert captured["command"][-1] == "kiro-cli"
    assert captured["kwargs"]["env"] == session.environment


def test_process_path_is_used_when_git_bash_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("revai.shell.git_bash_session", lambda: None)
    monkeypatch.setattr("revai.shell.shutil.which", lambda name: "/tools/kiro-cli")

    command, environment = command_for_execution(["kiro-cli", "--version"])

    assert command == ["kiro-cli", "--version"]
    assert environment is None
    assert resolve_command("kiro-cli") == "/tools/kiro-cli"
