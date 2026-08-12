"""Regression coverage for dependency-free security findings."""

from pathlib import Path

import pytest

from revai.analyzers.security import find_security_issues
from revai.domain.enums import Category, FindingSource, Severity


def test_security_analyzer_finds_python_eval_without_semgrep(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("def calculate(value):\n    return eval(value)\n", encoding="utf-8")

    findings = find_security_issues(tmp_path, ["app.py"])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.source is FindingSource.SECURITY
    assert finding.category is Category.SECURITY
    assert finding.severity is Severity.CRITICAL
    assert finding.rule_id == "dynamic-execution"
    assert finding.line_start == 2


def test_security_analyzer_finds_javascript_eval_without_semgrep(tmp_path: Path) -> None:
    source = tmp_path / "app.ts"
    source.write_text(
        "export const calculate = (value: string) => eval(value);\n",
        encoding="utf-8",
    )

    findings = find_security_issues(tmp_path, ["app.ts"])

    assert [finding.rule_id for finding in findings] == ["dynamic-execution"]
    assert findings[0].line_start == 1


@pytest.mark.parametrize(
    ("source", "expected_rule"),
    [
        ("exec(payload)\n", "dynamic-execution"),
        ("from os import system as run\nrun(command)\n", "shell-execution"),
        ("import pickle as serial\nserial.loads(payload)\n", "unsafe-deserialization"),
        ("from subprocess import run\nrun(command, shell=True)\n", "shell-true"),
    ],
)
def test_security_analyzer_covers_each_python_dangerous_api(
    tmp_path: Path, source: str, expected_rule: str
) -> None:
    file = tmp_path / "dangerous.py"
    file.write_text(source, encoding="utf-8")

    findings = find_security_issues(tmp_path, [file.name])

    assert [finding.rule_id for finding in findings] == [expected_rule]


def test_security_analyzer_finds_javascript_function_constructor(tmp_path: Path) -> None:
    source = tmp_path / "app.js"
    source.write_text("const run = Function('value', 'return value');\n", encoding="utf-8")

    findings = find_security_issues(tmp_path, [source.name])

    assert [finding.rule_id for finding in findings] == ["dynamic-execution"]
