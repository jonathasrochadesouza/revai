"""Agent template rendering: copy the template, inject the review JSON.

The report is a single self-contained HTML page. The template is fixed (see
``revai/templates/agent-report.html``); rendering an agent review means
replacing the ``__REVAI_DATA__`` placeholder with the findings payload. That
keeps the agent's token cost at the JSON alone — the markup never travels
through a model.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from revai.pipeline.ai import _FindingEnvelope

PLACEHOLDER = "__REVAI_DATA__"
DATA_NODE_ID = "revai-data"
TEMPLATE_NAME = "agent-report.html"
REPORT_SUFFIX = "-revai.html"


class AgentReportError(ValueError):
    """The injected payload does not match the review finding contract."""


class _CompactFinding(BaseModel):
    """The subset the agent owes; tolerant on optional decorations."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    severity: str = "low"
    category: str = "maintainability"
    title: str
    description: str = ""
    rationale: str = ""
    file: str
    line_start: int
    line_end: int | None = None
    rule_id: str | None = None
    confidence: float | None = None
    suggested_patch: str | None = None


class _CompactEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    findings: list[_CompactFinding]


def load_template() -> str:
    """Read the packaged ``agent-report.html`` template."""
    return resources.files("revai.templates").joinpath(TEMPLATE_NAME).read_text(encoding="utf-8")


def inject_data(template: str, payload: dict[str, Any]) -> str:
    """Replace the placeholder with ``payload`` as JSON.

    ``</`` is escaped to ``<\\/`` inside the emitted JSON so a finding body can
    never terminate the ``application/json`` script node; ``\\/`` parses back
    to ``/`` unchanged.
    """
    if template.count(PLACEHOLDER) != 1:
        raise AgentReportError(
            f"the agent report template must contain exactly one {PLACEHOLDER} placeholder"
        )
    serialized = json.dumps(payload, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return template.replace(PLACEHOLDER, serialized)


def slugify_name(name: str) -> str:
    """A branch or label turned into the ``feat-user`` part of the report file."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-.")
    return slug[:120] or "review"


def report_filename(name: str) -> str:
    """``feat-user`` → ``feat-user-revai.html``."""
    return f"{slugify_name(name)}{REPORT_SUFFIX}"


def validate_payload(raw: str | bytes) -> dict[str, Any]:
    """Accept either the canonical export envelope or the compact agent shape.

    The canonical export is ``{format_version, project, review}`` where the
    review carries ``findings``. The compact shape the agent is instructed to
    emit is ``{"findings": [...]}``. Both reach the template as-is; validation
    only guarantees the template's renderer will find what it needs.
    """
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AgentReportError(f"invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise AgentReportError("payload must be a JSON object")

    review = payload.get("review") if isinstance(payload.get("review"), dict) else payload
    findings = review.get("findings")
    if not isinstance(findings, list):
        raise AgentReportError('payload must contain a "findings" array')
    try:
        # The strict AI contract first: every field present and well-typed.
        _FindingEnvelope.model_validate(review)
    except ValidationError:
        # The compact agent shape: only what the template really needs, so an
        # agent that omits optional decorations still renders a faithful page.
        try:
            _CompactEnvelope.model_validate(review)
        except ValidationError as exc:
            raise AgentReportError(f"findings do not match the review contract: {exc}") from exc
    return payload


def render_report(
    payload: str | bytes,
    *,
    name: str,
    out_dir: Path,
    template: str | None = None,
) -> Path:
    """Write ``<name>-revai.html`` with the payload injected.

    Raises :class:`AgentReportError` when the payload does not validate, so a
    broken report is never written.
    """
    data = validate_payload(payload)
    document = inject_data(template or load_template(), data)
    out_dir.mkdir(parents=True, exist_ok=True)
    destination = out_dir / report_filename(name)
    destination.write_text(document, encoding="utf-8")
    return destination
