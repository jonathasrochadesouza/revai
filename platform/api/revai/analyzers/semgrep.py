"""Semgrep output normalization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from revai.domain.enums import Category, FindingSource, Severity
from revai.domain.models import Finding


def parse_semgrep_output(payload: str, repository: Path) -> list[Finding]:
    document: dict[str, Any] = json.loads(payload or "{}")
    findings: list[Finding] = []
    for result in document.get("results") or []:
        extra = result.get("extra") or {}
        metadata = extra.get("metadata") or {}
        rule_id = str(result.get("check_id") or "semgrep")
        description = str(extra.get("message") or "Semgrep reported a problem.")
        line_start = max(1, int((result.get("start") or {}).get("line") or 1))
        line_end = max(
            line_start,
            int((result.get("end") or {}).get("line") or line_start),
        )
        findings.append(
            Finding(
                severity=_severity(str(extra.get("severity") or "WARNING")),
                category=_category(metadata, rule_id),
                title=f"{rule_id}: {description}"[:200],
                description=description,
                rationale="Semgrep matched a deterministic static-analysis rule.",
                file=_relative_path(str(result.get("path") or ""), repository),
                line_start=line_start,
                line_end=line_end,
                source=FindingSource.SEMGREP,
                rule_id=rule_id,
                confidence=0.97,
            )
        )
    return findings


def _severity(value: str) -> Severity:
    return {
        "ERROR": Severity.CRITICAL,
        "WARNING": Severity.MEDIUM,
        "INFO": Severity.LOW,
    }.get(value.upper(), Severity.MEDIUM)


def _category(metadata: dict[str, Any], rule_id: str) -> Category:
    category = str(metadata.get("category") or "").lower()
    if category == "security" or "security" in rule_id:
        return Category.SECURITY
    if category in {"correctness", "bug"}:
        return Category.BUG
    if category == "performance":
        return Category.PERFORMANCE
    return Category.MAINTAINABILITY


def _relative_path(filename: str, repository: Path) -> str:
    path = Path(filename)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(repository.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
