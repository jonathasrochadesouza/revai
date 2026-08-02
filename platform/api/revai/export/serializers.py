"""JSON, Markdown, standalone HTML, and archive exporters."""

from __future__ import annotations

import html
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from revai.config import Settings
from revai.domain.enums import Category, FindingSource, Severity
from revai.domain.models import Finding, Project, RevaiConfig, Review

_LEGACY_LINES = re.compile(r"^\s*(\d+)(?:\s*[-\u2013\u2014:]\s*(\d+))?\s*$")


class LegacyFinding(BaseModel):
    """The finding shape consumed by the original PowerShell HTML template."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    title: str = Field(min_length=1)
    priority: str = Field(min_length=1)
    description: str = ""
    copilotSummary: str = ""  # noqa: N815 - compatibility field is camelCase
    file: str = Field(min_length=1)
    lines: str = Field(min_length=1)

    @field_validator("lines")
    @classmethod
    def _valid_lines(cls, value: str) -> str:
        if _LEGACY_LINES.fullmatch(value) is None:
            raise ValueError("lines must be a line number or inclusive range")
        return value


def render_json(review: Review, project: Project | None) -> bytes:
    payload = {
        "format_version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "project": _project_payload(project),
        "review": review.model_dump(mode="json"),
    }
    return _json_bytes(payload)


def render_legacy_json(review: Review) -> bytes:
    """Write the legacy list exactly as the old report loader expects it."""
    return _json_bytes([_to_legacy(finding) for finding in review.sorted_findings])


def legacy_findings_to_domain(payload: list[dict[str, Any]]) -> list[Finding]:
    """Import the lossier legacy shape for compatibility and round-trip tests."""
    findings: list[Finding] = []
    for raw in payload:
        item = LegacyFinding.model_validate(raw)
        line_match = _LEGACY_LINES.fullmatch(item.lines)
        if line_match is None:  # Kept defensive for type checkers; validation handles it.
            continue
        line_start = int(line_match.group(1))
        line_end = int(line_match.group(2)) if line_match.group(2) else None
        findings.append(
            Finding(
                severity=_legacy_severity(item.priority),
                category=Category.MAINTAINABILITY,
                title=item.title,
                description=item.description or item.copilotSummary or item.title,
                rationale=item.copilotSummary,
                file=item.file.replace("\\", "/"),
                line_start=line_start,
                line_end=line_end,
                source=FindingSource.AI,
            )
        )
    return findings


def render_markdown(review: Review, project: Project | None) -> bytes:
    project_name = project.name if project else "Unknown project"
    branch = review.head_branch or "working tree"
    findings = review.sorted_findings
    lines = [
        f"# RevAI review — {_markdown_text(project_name)}",
        "",
        f"- **Review:** `{_markdown_code(review.id)}`",
        f"- **Branch:** `{_markdown_code(branch)}`",
        f"- **Status:** {review.status.value}",
        f"- **Created:** {review.created_at.isoformat()}",
        (
            "- **Provider:** "
            + _markdown_text(review.provider_id.value if review.provider_id else "deterministic")
        ),
        f"- **Model:** `{_markdown_code(review.model or 'none')}`",
        (
            f"- **Cost:** ${review.stats.cost_usd:.6f}"
            f"{' estimated' if review.stats.cost_is_estimated else ''}"
        ),
        "",
        "## Summary",
        "",
        "| Critical | Medium | Low | Total |",
        "|---:|---:|---:|---:|",
        (
            f"| {_severity_total(findings, Severity.CRITICAL)} "
            f"| {_severity_total(findings, Severity.MEDIUM)} "
            f"| {_severity_total(findings, Severity.LOW)} | {len(findings)} |"
        ),
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append("No findings were reported.")
    for index, finding in enumerate(findings, start=1):
        location = f"{finding.file}:{finding.lines}"
        lines.extend(
            [
                f"### {index}. {_markdown_text(finding.title)}",
                "",
                f"`{finding.severity.value}` · `{finding.category.value}` · "
                f"`{finding.source.value}` · `{_markdown_code(location)}`",
                "",
                _markdown_text(finding.description),
                "",
            ]
        )
        if finding.rationale:
            lines.extend(["**Why this matters:**", "", _markdown_text(finding.rationale), ""])
        if finding.rule_id:
            lines.extend([f"Rule: `{_markdown_code(finding.rule_id)}`", ""])
        if finding.suggested_patch:
            lines.extend(["```diff", finding.suggested_patch.rstrip(), "```", ""])
    return ("\n".join(lines).rstrip() + "\n").encode()


def render_html(review: Review, project: Project | None) -> bytes:
    """Render a self-contained, script-free offline report.

    Every dynamic value is escaped before insertion. The output intentionally has
    no JavaScript, remote font, image, stylesheet, or other network dependency.
    """
    project_name = project.name if project else "Unknown project"
    branch = review.head_branch or "working tree"
    finding_cards = "".join(
        _finding_html(index, finding) for index, finding in enumerate(review.sorted_findings, 1)
    )
    if not finding_cards:
        finding_cards = '<p class="empty">No findings were reported.</p>'
    estimated = " · estimated" if review.stats.cost_is_estimated else ""
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RevAI review — {html.escape(project_name)}</title>
<style>{_REPORT_CSS}</style>
</head>
<body>
<header><div class="wordmark">rev<span>AI</span></div><p>Local-first code review</p></header>
<main>
<section class="hero">
  <div>
    <p class="label">Review report</p>
    <h1>{html.escape(project_name)}</h1>
    <p class="branch">{html.escape(branch)}</p>
  </div>
  <div class="status">{html.escape(review.status.value)}</div>
</section>
<section class="metrics" aria-label="Review metrics">
  <div><b>{_severity_total(review.findings, Severity.CRITICAL)}</b><span>Critical</span></div>
  <div><b>{_severity_total(review.findings, Severity.MEDIUM)}</b><span>Medium</span></div>
  <div><b>{_severity_total(review.findings, Severity.LOW)}</b><span>Low</span></div>
  <div><b>${review.stats.cost_usd:.4f}</b><span>Cost{estimated}</span></div>
</section>
<section class="meta">
  <span>Review <code>{html.escape(review.id)}</code></span>
  <span>{html.escape(review.created_at.isoformat())}</span>
  <span>{html.escape(review.model or "deterministic")}</span>
</section>
<section class="findings"><h2>Findings</h2>{finding_cards}</section>
</main>
<footer>Generated by RevAI · repository contents remained local</footer>
</body>
</html>"""
    return document.encode()


def build_data_archive(
    settings: Settings,
    config: RevaiConfig,
    projects: list[Project],
    reviews: list[Review],
) -> bytes:
    """Build a portable ZIP without credentials, caches, or repository contents."""
    output = io.BytesIO()
    manifest = {
        "format_version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "projects": len(projects),
        "reviews": len(reviews),
        "credentials_included": False,
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _json_bytes(manifest))
        archive.writestr("config.json", _json_bytes(config.model_dump(mode="json")))
        for project in projects:
            archive.writestr(
                f"projects/{project.id}.json",
                _json_bytes(project.model_dump(mode="json")),
            )
        for review in reviews:
            archive.writestr(
                f"reviews/{review.project_id}/{review.id}.json",
                render_json(
                    review,
                    next(
                        (item for item in projects if item.id == review.project_id),
                        None,
                    ),
                ),
            )
        _add_rules(archive, settings.rules_dir)
    return output.getvalue()


def directory_size(path: Path) -> int:
    total = 0
    if not path.is_dir():
        return total
    for candidate in path.rglob("*"):
        try:
            if candidate.is_file() and not candidate.is_symlink():
                total += candidate.stat().st_size
        except OSError:
            continue
    return total


def safe_export_stem(review: Review, project: Project | None) -> str:
    raw = f"{project.name if project else review.project_id}-{review.head_branch or review.id}"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-.")
    return stem[:120] or f"review-{review.id}"


def _project_payload(project: Project | None) -> dict[str, Any] | None:
    if project is None:
        return None
    return project.model_dump(mode="json")


def _to_legacy(finding: Finding) -> dict[str, str]:
    return LegacyFinding(
        title=finding.title,
        priority=finding.severity.value.capitalize(),
        description=finding.description,
        copilotSummary=finding.rationale,
        file=finding.file,
        lines=finding.lines,
    ).model_dump()


def _legacy_severity(priority: str) -> Severity:
    normalized = priority.strip().lower()
    if normalized in {"critical", "high", "p0", "p1"}:
        return Severity.CRITICAL
    if normalized in {"medium", "moderate", "p2"}:
        return Severity.MEDIUM
    if normalized in {"low", "minor", "p3", "p4"}:
        return Severity.LOW
    raise ValueError(f"unknown legacy priority: {priority!r}")


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()


def _severity_total(findings: list[Finding], severity: Severity) -> int:
    return sum(finding.severity is severity for finding in findings)


def _markdown_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", "").strip()


def _markdown_code(value: str) -> str:
    return value.replace("`", "\\`")


def _finding_html(index: int, finding: Finding) -> str:
    rule = f"<span>{html.escape(finding.rule_id)}</span>" if finding.rule_id else ""
    rationale = (
        '<div class="rationale"><b>Why this matters</b><p>'
        f"{_html_paragraphs(finding.rationale)}</p></div>"
        if finding.rationale
        else ""
    )
    patch = (
        "<details><summary>Suggested patch</summary><pre>"
        f"{html.escape(finding.suggested_patch)}</pre></details>"
        if finding.suggested_patch
        else ""
    )
    return f"""<article class="finding {finding.severity.value}">
<div class="finding-head"><span class="number">{index:02}</span><div>
<h3>{html.escape(finding.title)}</h3>
<p class="location">{html.escape(finding.file)}:{html.escape(finding.lines)}</p></div></div>
<div class="tags">
<span>{html.escape(finding.severity.value)}</span>
<span>{html.escape(finding.category.value)}</span>
<span>{html.escape(finding.source.value)}</span>{rule}
</div>
<p>{_html_paragraphs(finding.description)}</p>{rationale}{patch}
</article>"""


def _html_paragraphs(value: str) -> str:
    return html.escape(value).replace("\n", "<br>")


def _add_rules(archive: zipfile.ZipFile, rules_dir: Path) -> None:
    if not rules_dir.is_dir():
        return
    for candidate in sorted(rules_dir.rglob("*")):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        relative = candidate.relative_to(rules_dir)
        archive.writestr(f"rules/{relative.as_posix()}", candidate.read_bytes())


_REPORT_CSS = """
:root {
  color-scheme: light;
  --canvas: #fafafa; --paper: #fff; --ink: #09090b; --muted: #52525b;
  --subtle: #a1a1aa; --line: #e4e4e7; --critical: #dc2626;
  --medium: #d97706; --low: #2563eb;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--canvas); color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
  font-size: 14px; line-height: 1.55;
}
header, main, footer { width: min(1040px, calc(100% - 40px)); margin: auto; }
header {
  height: 64px; display: flex; align-items: center; gap: 16px;
  border-bottom: 1px solid var(--line);
}
header p { color: var(--subtle); }
.wordmark { font-size: 18px; font-weight: 750; letter-spacing: -.04em; }
.wordmark span { color: #2563eb; }
.hero { display: flex; justify-content: space-between; gap: 24px; padding: 56px 0 36px; }
.label {
  text-transform: uppercase; letter-spacing: .1em; color: var(--subtle);
  font-size: 11px; font-weight: 700; margin: 0 0 8px;
}
.hero h1 { font-size: 36px; line-height: 1.1; letter-spacing: -.04em; margin: 0; }
.branch { font-family: ui-monospace, monospace; color: var(--muted); }
.status {
  align-self: flex-start; border: 1px solid #a7f3d0; background: #ecfdf5;
  color: #047857; border-radius: 6px; padding: 5px 10px; font-size: 11px;
  font-weight: 700; text-transform: uppercase;
}
.metrics {
  display: grid; grid-template-columns: repeat(4, 1fr); background: var(--paper);
  border: 1px solid var(--line); border-radius: 11px;
}
.metrics div { padding: 22px; border-right: 1px solid var(--line); }
.metrics div:last-child { border: 0; }
.metrics b { display: block; font: 700 24px ui-monospace, monospace; }
.metrics span { color: var(--subtle); font-size: 11px; text-transform: uppercase; }
.meta {
  display: flex; flex-wrap: wrap; gap: 20px; padding: 20px 0;
  color: var(--muted); font-size: 12px;
}
.findings { padding: 20px 0 60px; }
.findings > h2 { font-size: 20px; margin: 0 0 16px; }
.finding {
  background: var(--paper); border: 1px solid var(--line); border-left: 3px solid var(--low);
  border-radius: 10px; padding: 22px; margin-bottom: 14px;
}
.finding.critical { border-left-color: var(--critical); }
.finding.medium { border-left-color: var(--medium); }
.finding-head { display: flex; gap: 14px; }
.number { font: 600 11px ui-monospace, monospace; color: var(--subtle); }
h3 { font-size: 16px; margin: 0; }
.location { font: 12px ui-monospace, monospace; color: var(--muted); margin: 4px 0 0; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin: 14px 0; }
.tags span {
  border: 1px solid var(--line); border-radius: 5px; padding: 2px 7px;
  font-size: 10px; text-transform: uppercase;
}
.rationale {
  background: #fcfcfc; border: 1px solid var(--line); border-radius: 8px;
  padding: 14px; margin-top: 14px;
}
.rationale p { margin: 5px 0 0; }
details { margin-top: 14px; }
summary { cursor: pointer; font-weight: 600; }
pre {
  overflow: auto; background: #18181b; color: #f4f4f5; border-radius: 8px;
  padding: 16px; font-size: 12px;
}
.empty {
  background: var(--paper); border: 1px solid var(--line); border-radius: 10px;
  padding: 28px; color: var(--muted);
}
footer {
  padding: 20px 0 40px; border-top: 1px solid var(--line);
  color: var(--subtle); font-size: 12px;
}
@media (max-width: 640px) {
  header, main, footer { width: min(100% - 24px, 1040px); }
  .hero { padding-top: 36px; }
  .hero h1 { font-size: 28px; }
  .metrics { grid-template-columns: 1fr 1fr; }
  .metrics div:nth-child(2) { border-right: 0; }
  .metrics div:nth-child(-n+2) { border-bottom: 1px solid var(--line); }
}
""".strip()
