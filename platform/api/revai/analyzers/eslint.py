"""ESLint output normalization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from revai.domain.enums import Category, FindingSource, Severity
from revai.domain.models import Finding


def parse_eslint_output(payload: str, repository: Path) -> list[Finding]:
    reports: list[dict[str, Any]] = json.loads(payload or "[]")
    findings: list[Finding] = []
    for report in reports:
        filename = _relative_path(str(report.get("filePath") or ""), repository)
        for message in report.get("messages") or []:
            rule_id = str(message.get("ruleId") or "eslint")
            description = str(message.get("message") or "ESLint reported a problem.")
            severity = Severity.MEDIUM if int(message.get("severity") or 1) >= 2 else Severity.LOW
            line_start = max(1, int(message.get("line") or 1))
            line_end = max(line_start, int(message.get("endLine") or line_start))
            findings.append(
                Finding(
                    severity=severity,
                    category=_category(rule_id),
                    title=f"{rule_id}: {description}"[:200],
                    description=description,
                    rationale="ESLint reported this issue during deterministic static analysis.",
                    file=filename,
                    line_start=line_start,
                    line_end=line_end,
                    source=FindingSource.ESLINT,
                    rule_id=rule_id,
                    confidence=0.96,
                )
            )
    return findings


def _relative_path(filename: str, repository: Path) -> str:
    try:
        return Path(filename).resolve().relative_to(repository.resolve()).as_posix()
    except ValueError:
        return Path(filename).as_posix()


def _category(rule_id: str) -> Category:
    if any(part in rule_id for part in ("security", "no-eval", "no-implied-eval")):
        return Category.SECURITY
    if any(part in rule_id for part in ("no-undef", "valid-typeof", "constructor-super")):
        return Category.BUG
    if "complexity" in rule_id:
        return Category.PERFORMANCE
    return Category.MAINTAINABILITY
