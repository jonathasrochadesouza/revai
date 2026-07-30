"""Gitleaks output normalization with secret-safe persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from revai.domain.enums import Category, FindingSource, Severity
from revai.domain.models import Finding


def parse_gitleaks_output(payload: str, repository: Path) -> list[Finding]:
    reports: list[dict[str, Any]] = json.loads(payload or "[]")
    findings: list[Finding] = []
    for report in reports:
        rule_id = str(report.get("RuleID") or "gitleaks")
        description = str(report.get("Description") or "Potential secret detected.")
        line_start = max(1, int(report.get("StartLine") or 1))
        line_end = max(line_start, int(report.get("EndLine") or line_start))
        findings.append(
            Finding(
                severity=Severity.CRITICAL,
                category=Category.SECURITY,
                title=f"{rule_id}: {description}"[:200],
                description=description,
                rationale=(
                    "Gitleaks detected a credential-like value. The matched value "
                    "is deliberately omitted from RevAI's persisted results."
                ),
                file=_relative_path(str(report.get("File") or ""), repository),
                line_start=line_start,
                line_end=line_end,
                source=FindingSource.GITLEAKS,
                rule_id=rule_id,
                confidence=0.99,
            )
        )
    return findings


def _relative_path(filename: str, repository: Path) -> str:
    path = Path(filename)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(repository.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
