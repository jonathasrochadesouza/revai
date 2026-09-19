"""Model-generated fixes as search/replace blocks.

Design decisions (and why they are not the obvious ones):

* **Search/replace, not full-file rewrites.** A targeted block is a fraction
  of the output tokens of a rewritten file, and it is content-addressed: no
  line numbers to hallucinate or drift. The block is converted to a unified
  diff before it ever touches Git, so the apply path is identical to the one
  used for stored patches.
* **Narrow context.** The model sees the finding's neighbourhood (~40 lines)
  plus the finding record — never the whole file. The window is chosen to
  make the call cheap; a fix that genuinely needs the whole file is beyond
  what one-shot generation should attempt anyway.
* **Secret redaction first.** The excerpt passes through the same redaction
  used by the review pipeline. If the finding sits inside redacted content,
  the generated search block will not match and the call fails with a stable
  error — an acceptable, honest outcome.
* **No retry on invalid output.** A malformed model response is re-rolled at
  the user's request, not behind their back; retries are reserved for
  provider transport failures, where a second attempt has a real chance.
"""

from __future__ import annotations

import difflib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from revai.domain.models import Finding, Project, RevaiConfig
from revai.domain.prompts import PAYLOAD_SENTINEL, PROMPT_INJECTION_GUARD
from revai.errors import RevaiError
from revai.pipeline.safety import redact_secrets
from revai.providers.base import (
    AnalysisRequest,
    FailedEvent,
    FinishedEvent,
    Provider,
    UsageEvent,
    UsageStats,
)

_SYSTEM_PROMPT = (
    "You repair a single code finding and nothing else. "
    "Reply with one JSON object with exactly two keys: "
    '"search" — the exact source text to replace, copied verbatim from the '
    "excerpt including its indentation; "
    '"replace" — the corrected text that must take its place. '
    "Rules: make the minimal edit that resolves the finding; never rewrite "
    "unrelated code; never reformat; keep the surrounding style; if the fix "
    "needs imports added, include the affected line in the block. "
    "No prose, no markdown fence, only the JSON object."
)

_USER_INSTRUCTIONS = (
    "Produce the minimal search/replace block that resolves the finding below. "
    "The excerpt lines are numbered for reference; the search text must match "
    "the file content exactly, without the line-number prefixes."
)

_EXCERPT_CONTEXT_LINES = 20
_MAX_PATCH_BYTES = 512_000


class _PatchBlockEnvelope(BaseModel):
    """The strict response contract sent to (and parsed from) providers."""

    model_config = ConfigDict(extra="forbid")

    search: str
    replace: str


@dataclass(frozen=True)
class GeneratedFix:
    patch: str
    usage: UsageStats
    duration_ms: int


async def generate_fix_patch(
    provider: Provider,
    config: RevaiConfig,
    project: Project,
    finding: Finding,
) -> GeneratedFix:
    """Ask the model for a search/replace fix and convert it to a unified diff.

    Raises ``RevaiError`` with stable ``fix.*`` keys for every dead end; the
    caller either previews or applies the returned patch unchanged.
    """
    target = Path(project.path) / finding.file
    if not target.is_file():
        raise RevaiError(422, "fix.file_missing", {"file": finding.file})
    content = target.read_text(encoding="utf-8", errors="replace")
    excerpt, line_offset = _excerpt(content, finding.line_start, finding.line_end)
    excerpt, _redactions = redact_secrets(excerpt)

    request = AnalysisRequest(
        model=config.engine.model,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=_compose_user_prompt(project, finding, excerpt, line_offset),
        json_schema=_PatchBlockEnvelope.model_json_schema(),
        timeout_s=config.budget.request_timeout_s,
    )

    started = time.perf_counter()
    finished: FinishedEvent | None = None
    latest_usage: UsageStats | None = None
    for attempt in range(config.budget.max_retry_attempts + 1):
        retryable_failure = False
        async for event in provider.analyze(request):
            if isinstance(event, FailedEvent):
                retryable_failure = event.retryable
                if not retryable_failure or attempt >= config.budget.max_retry_attempts:
                    raise RevaiError(422, "fix.generation_failed", {"detail": event.message})
                break
            if isinstance(event, UsageEvent):
                latest_usage = event.usage
            elif isinstance(event, FinishedEvent):
                finished = event
                latest_usage = event.usage or latest_usage
        if finished is not None:
            break
        if not retryable_failure and attempt >= config.budget.max_retry_attempts:
            raise RevaiError(422, "fix.generation_failed", {"detail": "empty response"})

    if finished is None:  # Defensive: the loop above either breaks or raises.
        raise RevaiError(422, "fix.generation_failed", {"detail": "empty response"})

    block = _extract_block(finished.text)
    patch = search_replace_to_diff(finding.file, content, block.search, block.replace)
    duration_ms = max(0, round((time.perf_counter() - started) * 1000))
    return GeneratedFix(
        patch=patch,
        usage=latest_usage or UsageStats(is_estimated=True),
        duration_ms=duration_ms,
    )


def _excerpt(content: str, line_start: int, line_end: int | None) -> tuple[str, int]:
    """Numbered lines around the finding, plus the line the numbering starts at."""
    lines = content.splitlines()
    first = max(1, (line_start or 1) - _EXCERPT_CONTEXT_LINES)
    last = min(len(lines), (line_end or line_start or 1) + _EXCERPT_CONTEXT_LINES)
    window = lines[first - 1 : last]
    numbered = "\n".join(f"{number}: {line}" for number, line in enumerate(window, start=first))
    return numbered, first


def _compose_user_prompt(project: Project, finding: Finding, excerpt: str, line_offset: int) -> str:
    payload = {
        "file": finding.file,
        "finding": {
            "title": finding.title,
            "description": finding.description,
            "rule_id": finding.rule_id,
            "lines": [finding.line_start, finding.line_end or finding.line_start],
            "severity": str(finding.severity),
        },
        "excerpt_starts_at_line": line_offset,
        "excerpt": excerpt,
    }
    rendered = json.dumps(payload, ensure_ascii=False)
    return (
        f"{PROMPT_INJECTION_GUARD}{_USER_INSTRUCTIONS} {PAYLOAD_SENTINEL}\n\n"
        f"Repository: {project.name}. File: {finding.file}.\n{rendered}"
    )


def _extract_block(text: str) -> _PatchBlockEnvelope:
    """Parse the model's JSON with the same narrow repairs the review uses."""
    candidate = text.strip()
    if candidate.startswith("```"):
        first_newline = candidate.find("\n")
        if first_newline >= 0:
            candidate = candidate[first_newline + 1 :]
        if candidate.rstrip().endswith("```"):
            candidate = candidate.rstrip()[:-3]

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end < start:
        raise RevaiError(422, "fix.invalid_generation", {"detail": "no JSON object in response"})
    payload = candidate[start : end + 1]
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError:
        try:
            raw = json.loads(re.sub(r",(?=\s*[}\]])", "", payload))
        except json.JSONDecodeError as exc:
            raise RevaiError(422, "fix.invalid_generation", {"detail": str(exc)}) from exc
    try:
        return _PatchBlockEnvelope.model_validate(raw)
    except ValidationError as exc:
        raise RevaiError(422, "fix.invalid_generation", {"detail": str(exc)}) from exc


def search_replace_to_diff(file: str, content: str, search: str, replace: str) -> str:
    """Convert a content-addressed block into a real unified diff.

    The search text must match the working tree exactly (after CRLF
    normalisation); anything else is an error, never a fuzzy match — a
    fuzzy match here would apply a patch to a region the model never saw.
    """
    if not search.strip():
        raise RevaiError(422, "fix.invalid_generation", {"detail": "empty search block"})
    if search == replace:
        raise RevaiError(422, "fix.no_change_generated", {"file": file})

    haystack = content
    index = haystack.find(search)
    if index < 0:
        normalised = haystack.replace("\r\n", "\n")
        index = normalised.find(search.replace("\r\n", "\n"))
        if index >= 0:
            haystack = normalised
    if index < 0:
        raise RevaiError(422, "fix.search_block_not_found", {"file": file})

    updated = haystack[:index] + replace + haystack[index + len(search) :]
    diff = "".join(
        difflib.unified_diff(
            haystack.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{file}",
            tofile=f"b/{file}",
        )
    )
    if not diff:
        raise RevaiError(422, "fix.no_change_generated", {"file": file})
    if len(diff.encode("utf-8")) > _MAX_PATCH_BYTES:
        raise RevaiError(422, "fix.patch_too_large", {"file": file})
    return diff
