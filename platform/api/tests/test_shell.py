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

    assert wrapped == [
        r"C:\Program Files\Git\bin\bash.exe",
        "--noprofile",
        "--norc",
        "-c",
        'exec "$@"',
        "revai-command",
        *command,
    ]
    assert environment == session.environment


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
