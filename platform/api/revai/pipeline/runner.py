"""Phase 4 deterministic pipeline orchestration."""

from __future__ import annotations

import hashlib
import time
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from revai.analyzers.runner import AnalyzerRun, run_analyzers
from revai.domain.enums import ReviewScope, ReviewStatus
from revai.domain.models import (
    AnalyzerRecord,
    Finding,
    PipelineStageRecord,
    Project,
    RevaiConfig,
    Review,
    ReviewStats,
)
from revai.git.repo import (
    current_branch,
    diff_preview,
    materialized_tree,
    review_identities,
    snapshot_preview,
)
from revai.pipeline.deterministic import (
    CodeChunk,
    ParsedHunk,
    build_chunks,
    filter_changed_files,
    parse_unified_diff,
)

StageStatus = Literal["completed", "degraded", "failed", "skipped"]


@dataclass(frozen=True)
class StageRun:
    name: str
    status: StageStatus
    duration_ms: int
    detail: str | None = None


@dataclass(frozen=True)
class DeterministicResult:
    review: Review
    stages: list[StageRun]
    analyzers: list[AnalyzerRun]
    chunks: list[CodeChunk]
    hunks: list[ParsedHunk]


async def run_deterministic_pipeline(
    project: Project,
    config: RevaiConfig,
    *,
    base: str,
    head: str,
    review: Review | None = None,
    include_static: bool = True,
    scope: ReviewScope = ReviewScope.BRANCH_DIFF,
    selected_files: list[str] | None = None,
    sonar_token: str | None = None,
) -> DeterministicResult:
    repository = Path(project.path)
    review = review or Review(
        project_id=project.id,
        scope=ReviewScope.BRANCH_DIFF,
        base_branch=base,
        head_branch=head,
    )
    review.status = ReviewStatus.RUNNING
    review.config_hash = hashlib.sha256(
        config.model_dump_json(exclude={"updated_at"}).encode()
    ).hexdigest()
    review.author, review.reviewer = review_identities(repository, head)
    started = time.perf_counter()
    stages: list[StageRun] = []

    stage_started = time.perf_counter()
    preview = (
        diff_preview(repository, base, head, patch_limit_bytes=None)
        if scope is ReviewScope.BRANCH_DIFF
        else snapshot_preview(
            repository,
            head,
            selected_files=selected_files if scope is ReviewScope.SELECTED_FILES else None,
        )
    )
    stages.append(
        StageRun(
            "collect",
            "completed",
            _duration_ms(stage_started),
            f"{len(preview.files)} changed files.",
        )
    )

    stage_started = time.perf_counter()
    if config.analyzers.skip_noise:
        kept_files, skipped_files = filter_changed_files(preview.files)
    else:
        kept_files, skipped_files = preview.files, []
    paths = [item.path for item in kept_files]
    stages.append(
        StageRun(
            "filter",
            "completed",
            _duration_ms(stage_started),
            f"{len(paths)} kept, {len(skipped_files)} skipped.",
        )
    )

    stage_started = time.perf_counter()
    hunks = parse_unified_diff(preview.patch, allowed_paths=set(paths))
    stages.append(
        StageRun(
            "parse",
            "completed",
            _duration_ms(stage_started),
            f"{len(hunks)} reviewable hunks.",
        )
    )

    analysis_tree = (
        materialized_tree(repository, head)
        if base != head and current_branch(repository) != head
        else nullcontext(repository)
    )
    with analysis_tree as analysis_repository:
        stage_started = time.perf_counter()
        analyzers = (
            await run_analyzers(
                analysis_repository,
                paths,
                config.analyzers,
                checkstyle_command=project.checkstyle_command,
                test_command=project.test_command,
                build_command=project.build_command,
                sonar_token=sonar_token,
            )
            if include_static
            else []
        )
        findings = [finding for run in analyzers for finding in run.findings]
        if config.analyzers.changed_lines_only:
            findings = _on_added_lines(findings, hunks)
        static_degraded = any(
            run.status in {"degraded", "unavailable", "failed"} for run in analyzers
        )
        stages.append(
            StageRun(
                "static",
                "degraded" if static_degraded else "completed",
                _duration_ms(stage_started),
                f"{len(findings)} findings from available analyzers."
                if include_static
                else "Skipped for AI-assisted review.",
            )
        )

        stage_started = time.perf_counter()
        chunks = build_chunks(
            analysis_repository,
            hunks,
            max_tokens=config.budget.max_context_tokens,
        )
        stages.append(
            StageRun(
                "chunk",
                "completed",
                _duration_ms(stage_started),
                f"{len(chunks)} context chunks prepared.",
            )
        )

    review.findings = sorted(
        findings,
        key=lambda finding: (
            finding.severity.rank,
            -finding.confidence,
            finding.file,
            finding.line_start,
        ),
    )
    review.scope = scope
    review.selected_files = paths
    analyzed_paths = {
        path for analyzer in analyzers for path in analyzer.files_analyzed
    }
    review.stats = ReviewStats(
        files_analysed=len(analyzed_paths),
        files_skipped=len(skipped_files),
        hunks_total=len(hunks),
        hunks_sent_to_ai=0,
        chunks_prepared=len(chunks),
        estimated_context_tokens=sum(chunk.estimated_tokens for chunk in chunks),
        tokens_input=0,
        tokens_output=0,
        cost_usd=0,
        duration_ms=_duration_ms(started),
    )
    review.stages = [
        PipelineStageRecord(
            name=stage.name,
            status=stage.status,
            duration_ms=stage.duration_ms,
            detail=stage.detail,
        )
        for stage in stages
    ]
    review.analyzers = [
        AnalyzerRecord(
            name=run.name,
            status=run.status,
            findings=len(run.findings),
            duration_ms=run.duration_ms,
            detail=run.detail,
            files_analyzed=list(run.files_analyzed),
            metadata=run.metadata or {},
        )
        for run in analyzers
    ]
    review.status = (
        ReviewStatus.DEGRADED
        if any(stage.status == "degraded" for stage in stages)
        else ReviewStatus.COMPLETED
    )
    review.finished_at = datetime.now(UTC)
    return DeterministicResult(review, stages, analyzers, chunks, hunks)


def _on_added_lines(findings: list[Finding], hunks) -> list[Finding]:
    changed: dict[str, set[int]] = {}
    for hunk in hunks:
        changed.setdefault(hunk.path, set()).update(hunk.added_lines)
    return [
        finding
        for finding in findings
        if any(
            line in changed.get(finding.file, set())
            for line in range(finding.line_start, (finding.line_end or finding.line_start) + 1)
        )
    ]


def _duration_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
