"""SonarQube Server / Community Build issue normalization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from revai.domain.enums import Category, FindingSource, Severity
from revai.domain.models import Finding


def parse_sonarqube_issues(payload: dict[str, Any], repository: Path) -> list[Finding]:
    """Convert SonarQube's ``api/issues/search`` response into RevAI findings."""
    findings: list[Finding] = []
    for issue in payload.get("issues") or []:
        component = str(issue.get("component") or "")
        # Sonar emits ``project-key:path/to/file``; retain only a repo-relative path.
        file = component.split(":", 1)[-1].replace("\\", "/") or "unknown"
        line = max(1, int(issue.get("line") or 1))
        rule = str(issue.get("rule") or "sonarqube")
        message = str(issue.get("message") or "SonarQube reported an issue.")
        findings.append(
            Finding(
                severity=_severity(str(issue.get("severity") or "MAJOR")),
                category=_category(str(issue.get("type") or "CODE_SMELL")),
                title=f"{rule}: {message}"[:200],
                description=message,
                rationale="SonarQube reported this issue during static analysis.",
                file=file,
                line_start=line,
                source=FindingSource.SONARQUBE,
                rule_id=rule,
                confidence=0.96,
            )
        )
    return findings


def _severity(value: str) -> Severity:
    if value.upper() in {"BLOCKER", "CRITICAL"}:
        return Severity.CRITICAL
    if value.upper() in {"MAJOR"}:
        return Severity.MEDIUM
    return Severity.LOW


def _category(value: str) -> Category:
    return {
        "VULNERABILITY": Category.SECURITY,
        "SECURITY_HOTSPOT": Category.SECURITY,
        "BUG": Category.BUG,
        "CODE_SMELL": Category.MAINTAINABILITY,
    }.get(value.upper(), Category.MAINTAINABILITY)
