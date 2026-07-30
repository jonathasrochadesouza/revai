"""Ruff output normalization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from revai.domain.enums import Category, FindingSource, Severity
from revai.domain.models import Finding


def parse_ruff_output(payload: str, repository: Path) -> list[Finding]:
    diagnostics: list[dict[str, Any]] = json.loads(payload or "[]")
    return [_finding(item, repository) for item in diagnostics]


def _finding(item: dict[str, Any], repository: Path) -> Finding:
    code = str(item.get("code") or "ruff")
    message = str(item.get("message") or "Ruff reported a problem.")
    location = item.get("location") or {}
    end_location = item.get("end_location") or {}
    line_start = max(1, int(location.get("row") or 1))
    line_end = max(line_start, int(end_location.get("row") or line_start))
    return Finding(
        severity=_severity(code),
        category=_category(code),
        title=f"{code}: {message}"[:200],
        description=message,
        rationale="Ruff reported this issue during deterministic static analysis.",
        file=_relative_path(str(item.get("filename") or ""), repository),
        line_start=line_start,
        line_end=line_end,
        source=FindingSource.RUFF,
        rule_id=code,
        confidence=0.98,
    )


def _relative_path(filename: str, repository: Path) -> str:
    try:
        return Path(filename).resolve().relative_to(repository.resolve()).as_posix()
    except ValueError:
        return Path(filename).as_posix()


def _severity(code: str) -> Severity:
    if code.startswith("S"):
        return Severity.CRITICAL
    if code.startswith(("B", "F")):
        return Severity.MEDIUM
    return Severity.LOW


def _category(code: str) -> Category:
    if code.startswith("S"):
        return Category.SECURITY
    if code.startswith("B"):
        return Category.BUG
    if code.startswith("PERF"):
        return Category.PERFORMANCE
    if code.startswith(("E", "W")):
        return Category.STYLE
    return Category.MAINTAINABILITY
