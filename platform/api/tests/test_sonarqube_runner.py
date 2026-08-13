"""SonarQube orchestration security and correctness contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from revai.analyzers.runner import (
    _sonar_command,
    _sonar_report,
    _wait_for_sonar_analysis,
)
from revai.domain.models import SonarQubeConfig


def test_maven_sonar_compiles_before_analysis(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pom.xml").write_text("<project />", encoding="utf-8")
    monkeypatch.setattr("revai.analyzers.runner.resolve_command", lambda name: "/bin/mvn")
    config = SonarQubeConfig(enabled=True, project_key="demo", scanner="maven")

    selected = _sonar_command(tmp_path, config)

    assert selected is not None
    scanner, command = selected
    assert scanner == "maven"
    assert command.index("verify") < command.index(
        "org.sonarsource.scanner.maven:sonar-maven-plugin:sonar"
    )
    assert all("token" not in argument.lower() for argument in command)


def test_sonar_report_must_be_fresh(tmp_path: Path) -> None:
    report = tmp_path / ".scannerwork" / "report-task.txt"
    report.parent.mkdir()
    report.write_text("ceTaskId=old", encoding="utf-8")
    previous = {report: (report.stat().st_mtime_ns, report.stat().st_size)}

    with pytest.raises(ValueError, match="fresh"):
        _sonar_report(tmp_path, previous=previous)

    report.write_text("ceTaskId=new-task", encoding="utf-8")
    assert _sonar_report(tmp_path, previous=previous)["ceTaskId"] == "new-task"


async def test_sonar_task_url_cannot_exfiltrate_the_token() -> None:
    class NeverCalledClient:
        async def get(self, *_args, **_kwargs):
            raise AssertionError("a cross-origin task URL must not be requested")

    with pytest.raises(ValueError, match="configured server"):
        await _wait_for_sonar_analysis(
            NeverCalledClient(),
            "https://sonar.example.test",
            {"ceTaskUrl": "https://attacker.example.test/api/ce/task?id=1"},
            10,
        )
