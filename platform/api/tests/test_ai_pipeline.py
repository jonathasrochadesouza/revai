"""Phase 5 AI review orchestration contracts."""

from __future__ import annotations

import json

import pytest

from revai.domain.enums import Category, FindingSource, Severity
from revai.domain.models import Finding, RevaiConfig
from revai.pipeline.ai import (
    BudgetExceededError,
    FindingExtractionError,
    estimate_input_cost,
    extract_findings,
    merge_findings,
    preflight_ai_stage,
    run_ai_stage,
)
from revai.pipeline.deterministic import CodeChunk
from revai.providers.base import (
    AnalysisRequest,
    DeltaEvent,
    FailedEvent,
    FinishedEvent,
    StartedEvent,
    UsageStats,
)


def _chunk(tokens: int = 120) -> CodeChunk:
    return CodeChunk(
        path="src/auth.py",
        symbol="authenticate",
        line_start=10,
        line_end=14,
        content="def authenticate(token):\n    return eval(token)",
        estimated_tokens=tokens,
    )


def _finding(*, source: FindingSource, confidence: float = 0.9) -> Finding:
    return Finding(
        severity=Severity.CRITICAL,
        category=Category.SECURITY,
        title="Dynamic code execution",
        description="Untrusted input reaches eval.",
        rationale="The token can execute arbitrary Python.",
        file="src/auth.py",
        line_start=11,
        source=source,
        rule_id="eval-detected",
        confidence=confidence,
    )


def test_extract_findings_accepts_fenced_structured_json() -> None:
    payload = {
        "findings": [
            {
                "severity": "critical",
                "category": "security",
                "title": "Dynamic code execution",
                "description": "Untrusted input reaches eval.",
                "rationale": "The token can execute arbitrary Python.",
                "file": "src/auth.py",
                "line_start": 11,
                "line_end": 11,
                "rule_id": "eval-detected",
                "confidence": 0.96,
                "suggested_patch": None,
            }
        ]
    }

    findings = extract_findings(f"```json\n{json.dumps(payload)}\n```")

    assert len(findings) == 1
    assert findings[0].source is FindingSource.AI
    assert findings[0].severity is Severity.CRITICAL
    assert findings[0].file == "src/auth.py"


def test_extract_findings_rejects_an_invalid_schema() -> None:
    with pytest.raises(FindingExtractionError, match=r"ai_pipeline\.invalid_findings"):
        extract_findings('{"findings":[{"severity":"urgent"}]}')


def test_extract_findings_repairs_trailing_commas_and_keeps_valid_items() -> None:
    valid = {
        "severity": "low",
        "category": "maintainability",
        "title": "Repeated branch",
        "description": "The same branch is evaluated twice.",
        "file": "src/app.py",
        "line_start": 12,
    }
    payload = json.dumps({"findings": [valid, {"severity": "urgent"}]})
    payload = payload.replace("]}", ",]}")

    findings = extract_findings(payload)

    assert len(findings) == 1
    assert findings[0].title == "Repeated branch"


def test_merge_findings_keeps_the_higher_confidence_duplicate() -> None:
    deterministic = _finding(source=FindingSource.SEMGREP, confidence=0.99)
    ai = _finding(source=FindingSource.AI, confidence=0.85)

    merged = merge_findings([deterministic], [ai], dedupe=True)

    assert merged == [deterministic]


def test_estimated_cost_enforces_the_configured_spend_cap() -> None:
    config = RevaiConfig()
    config.budget.warn_above_usd = 0
    config.budget.max_spend_usd = 0.001

    assert estimate_input_cost([_chunk(tokens=1_000)]) == pytest.approx(0.003)
    with pytest.raises(BudgetExceededError, match=r"budget\.estimated_cost_exceeds_max"):
        preflight_ai_stage(config, [_chunk(tokens=1_000)])


class _StreamingProvider:
    async def analyze(self, request: AnalysisRequest):
        assert request.json_schema is not None
        assert "src/auth.py" in request.user_prompt
        text = json.dumps(
            {
                "findings": [
                    {
                        "severity": "critical",
                        "category": "security",
                        "title": "Dynamic code execution",
                        "description": "Untrusted input reaches eval.",
                        "rationale": "The token can execute arbitrary Python.",
                        "file": "src/auth.py",
                        "line_start": 11,
                        "line_end": 11,
                        "rule_id": "eval-detected",
                        "confidence": 0.96,
                        "suggested_patch": None,
                    }
                ]
            }
        )
        yield StartedEvent(model=request.model)
        yield DeltaEvent(text=text[:20])
        yield FinishedEvent(
            text=text,
            usage=UsageStats(
                input_tokens=140,
                output_tokens=80,
                cached_tokens=40,
                cost_usd=0.0042,
            ),
        )


async def test_ai_stage_streams_progress_and_returns_usage() -> None:
    config = RevaiConfig()
    events: list[dict] = []

    result = await run_ai_stage(
        _StreamingProvider(),
        config,
        [_chunk()],
        on_event=events.append,
    )

    assert [event["type"] for event in events] == ["provider", "delta", "usage"]
    assert len(result.findings) == 1
    assert result.usage.input_tokens == 140
    assert result.usage.cached_tokens == 40
    assert result.usage.cost_usd == pytest.approx(0.0042)


class _TransientProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, request: AnalysisRequest):
        self.calls += 1
        if self.calls == 1:
            yield FailedEvent(message="rate limited", retryable=True)
            return
        yield StartedEvent(model=request.model)
        yield FinishedEvent(text='{"findings": []}', usage=UsageStats())


async def test_ai_stage_retries_a_transient_provider_failure() -> None:
    config = RevaiConfig()
    config.budget.max_retry_attempts = 1
    provider = _TransientProvider()
    events: list[dict] = []

    result = await run_ai_stage(provider, config, [_chunk()], on_event=events.append)

    assert result.findings == []
    assert provider.calls == 2
    assert events[0] == {
        "type": "retry",
        "attempt": 1,
        "error_key": "ai_pipeline.provider_failed",
        "params": {"detail": "rate limited"},
    }
