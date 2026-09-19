"""Deterministic and streamed AI review endpoints."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError
from starlette.responses import StreamingResponse

from revai.api.deps import (
    ConfigRepo,
    CredentialsRepo,
    ProjectRepo,
    PromptRepo,
    ReviewLimiterDep,
    ReviewRepo,
)
from revai.domain.enums import FindingStatus, ReviewMode, ReviewScope, ReviewStatus
from revai.domain.models import (
    AnalyzerRecord,
    FindingDecision,
    PipelineStageRecord,
    PromptOverride,
    Review,
    ReviewStats,
)
from revai.errors import RevaiError
from revai.git.repo import GitError
from revai.pipeline.ai import BudgetExceededError, estimate_input_cost, merge_findings, run_ai_stage
from revai.pipeline.runner import DeterministicResult, StageRun, run_deterministic_pipeline
from revai.pipeline.safety import redact_secrets
from revai.providers.base import UsageStats
from revai.providers.registry import build_registry
from revai.sonarqube.local import resolve_sonar_token
from revai.storage.base import StorageError

router = APIRouter(prefix="/projects/{project_id}/reviews", tags=["reviews"])


class DeterministicReviewRequest(BaseModel):
    base: str = Field(min_length=1)
    head: str = Field(min_length=1)
    mode: ReviewMode = ReviewMode.BOTH
    scope: ReviewScope = ReviewScope.BRANCH_DIFF
    selected_files: list[str] = Field(default_factory=list)
    # None reviews with the default prompts; otherwise it must name an existing
    # prompt scenario.
    scenario_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope is ReviewScope.SELECTED_FILES and not self.selected_files:
            raise PydanticCustomError(
                "review.selected_files_required",
                "selected_files is required for selected_files scope",
                {},
            )
        return self


class StageResponse(BaseModel):
    name: str
    status: str
    duration_ms: int
    detail: str | None


class AnalyzerResponse(BaseModel):
    name: str
    status: str
    findings: int
    duration_ms: int
    detail: str | None
    files_analyzed: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ChunkResponse(BaseModel):
    file: str
    symbol: str | None
    line_start: int
    line_end: int
    estimated_tokens: int


class DeterministicReviewResponse(BaseModel):
    review: Review
    stages: list[StageResponse]
    analyzers: list[AnalyzerResponse]
    chunks: list[ChunkResponse]


class ReviewsResponse(BaseModel):
    reviews: list[Review]


class ReviewComparisonResponse(BaseModel):
    left_review_id: str
    right_review_id: str
    new_findings: list[str]
    resolved_findings: list[str]
    persisting_findings: list[str]
    cost_delta_usd: float
    duration_delta_ms: int


class FindingStatusRequest(BaseModel):
    status: FindingStatus
    reason: str | None = Field(default=None, max_length=1_000)


def _resolve_prompt_override(
    config, prompt_repo: PromptRepo, scenario_id: str | None
) -> tuple[PromptOverride, str | None]:
    """Resolve the prompt pair a review runs with, and the scenario behind it.

    A scenario carries its own prompt snapshot; without one the effective
    defaults of the configured UI locale apply (custom override or built-in).
    Resolving here — before the job is queued — makes an unknown scenario an
    immediate HTTP 404 instead of a mid-stream failure.
    """
    try:
        if scenario_id:
            settings = prompt_repo.load()
            scenario = settings.scenario(scenario_id)
            if scenario is None:
                raise RevaiError(
                    status.HTTP_404_NOT_FOUND,
                    "prompt_scenario.not_found",
                    {"scenario_id": scenario_id},
                )
            override = PromptOverride(
                system_prompt=scenario.system_prompt,
                user_prompt=scenario.user_prompt,
            )
        else:
            override = prompt_repo.effective(config.ui.locale)
    except StorageError as exc:
        raise RevaiError(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.error_key, exc.params) from exc
    return override, scenario_id


@router.post(
    "/deterministic",
    response_model=DeterministicReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deterministic_review(
    project_id: str,
    request: DeterministicReviewRequest,
    config_repo: ConfigRepo,
    credentials_repo: CredentialsRepo,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> DeterministicReviewResponse:
    project = project_repo.get(project_id)
    if project is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "project.not_found", {"project_id": project_id})
    try:
        result = await run_deterministic_pipeline(
            project,
            config_repo.load(),
            base=request.base,
            head=request.head,
            review=Review(
                project_id=project.id,
                base_branch=request.base,
                head_branch=request.head,
                mode=ReviewMode.STATIC,
                scope=request.scope,
                selected_files=request.selected_files,
            ),
            include_static=True,
            scope=request.scope,
            selected_files=request.selected_files,
            sonar_token=resolve_sonar_token(credentials_repo.load()),
        )
    except GitError as exc:
        raise _git_unprocessable(exc) from exc

    review_repo.save(result.review)
    project.last_reviewed_at = datetime.now(UTC)
    project_repo.save(project)
    return _response(result)


@router.post("/stream")
async def create_ai_review(
    project_id: str,
    payload: DeterministicReviewRequest,
    http_request: Request,
    config_repo: ConfigRepo,
    credentials_repo: CredentialsRepo,
    project_repo: ProjectRepo,
    prompt_repo: PromptRepo,
    review_repo: ReviewRepo,
    limiter: ReviewLimiterDep,
) -> StreamingResponse:
    project = project_repo.get(project_id)
    if project is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "project.not_found", {"project_id": project_id})
    if payload.mode is ReviewMode.STATIC:
        raise RevaiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "review.static_only_endpoint")

    config = config_repo.load()
    prompt_override, scenario_id = _resolve_prompt_override(
        config, prompt_repo, payload.scenario_id
    )
    provider = build_registry(config, credentials_repo.load()).active()
    health = None
    if payload.mode is not ReviewMode.STATIC:
        if provider is None:
            raise RevaiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "provider.unavailable")
        health = await provider.health()
        if not health.is_usable:
            raise RevaiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "provider.not_ready",
                {
                    "provider_id": health.provider_id.value,
                    "detail": health.detail,
                    "remediation": health.remediation,
                },
            )

    # A disconnected browser must not cancel the job, but it also must not turn
    # streamed model deltas into an unbounded in-memory backlog.
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=256)
    review = Review(
        project_id=project.id,
        scope=payload.scope,
        status=ReviewStatus.QUEUED,
        base_branch=payload.base,
        head_branch=payload.head,
        mode=payload.mode,
        provider_id=config.engine.provider_id,
        model=config.engine.model,
        provider_version=health.version if health else None,
        scenario_id=scenario_id,
        selected_files=payload.selected_files,
    )
    # Persist before work starts. A browser can close while this job is waiting
    # for a slot and the review history still explains what happened.
    review_repo.save(review)

    async def run() -> None:
        nonlocal review
        result: DeterministicResult | None = None
        started = time.perf_counter()
        acquired_slot = False

        async def emit(event: dict[str, Any]) -> None:
            """Stream live and persist a bounded, secret-safe replay envelope."""
            _enqueue_latest(queue, event)
            if event.get("type") == "delta":
                return
            persisted = result.review if result is not None else review
            replay = _replay_event(event, persisted.id)
            persisted.events = [*persisted.events, replay][-200:]
            review_repo.save(persisted)

        try:
            await emit({"type": "review_queued", "review_id": review.id})
            await limiter.acquire(config.budget.max_concurrent_reviews)
            acquired_slot = True
            review.status = ReviewStatus.RUNNING
            review_repo.save(review)
            await emit({"type": "review_started", "review_id": review.id})
            result = await run_deterministic_pipeline(
                project,
                config,
                base=payload.base,
                head=payload.head,
                review=review,
                include_static=payload.mode is ReviewMode.BOTH,
                scope=payload.scope,
                selected_files=payload.selected_files,
                sonar_token=resolve_sonar_token(credentials_repo.load()),
            )
            result.review.finished_at = None
            result.review.status = ReviewStatus.RUNNING
            result.review.provider_id = config.engine.provider_id
            result.review.model = config.engine.model
            result.review.provider_version = health.version if health else None
            review_repo.save(result.review)
            for stage in result.stages:
                await emit(_stage_payload(stage))
            for analyzer in result.analyzers:
                await emit(
                    {
                        "type": "analyzer",
                        "name": analyzer.name,
                        "status": analyzer.status,
                        "findings": len(analyzer.findings),
                        "duration_ms": analyzer.duration_ms,
                        "detail": analyzer.detail,
                        "files_analyzed": list(analyzer.files_analyzed),
                        "metadata": analyzer.metadata or {},
                    }
                )

            if result.chunks and payload.mode is not ReviewMode.STATIC:
                estimated_cost = estimate_input_cost(result.chunks)
                if (
                    config.budget.max_spend_usd is not None
                    and estimated_cost > config.budget.max_spend_usd
                ):
                    raise BudgetExceededError(
                        "budget.estimated_cost_exceeds_max",
                        {
                            "estimated_cost_usd": round(estimated_cost, 4),
                            "max_spend_usd": config.budget.max_spend_usd,
                        },
                    )
                ai_result = await run_ai_stage(
                    provider,
                    config,
                    result.chunks,
                    prompt_override=prompt_override,
                    on_event=emit,
                )
                ai_findings = ai_result.findings
                usage = ai_result.usage
                ai_duration = ai_result.duration_ms
                result.review.effective_model = ai_result.effective_model
                result.review.prompt_hash = ai_result.prompt_hash
                secrets_redacted = ai_result.secrets_redacted
            else:
                ai_findings = []
                usage = UsageStats(is_estimated=True)
                ai_duration = 0
                secrets_redacted = 0

            ai_stage = StageRun(
                "ai",
                "completed",
                ai_duration,
                f"{len(ai_findings)} validated AI findings.",
            )
            result.stages.append(ai_stage)
            await emit(_stage_payload(ai_stage))

            merge_started = time.perf_counter()
            result.review.findings = merge_findings(
                result.review.findings,
                ai_findings,
                dedupe=config.analyzers.dedupe_across_sources,
            )
            merge_stage = StageRun(
                "merge",
                "completed",
                _duration_ms(merge_started),
                f"{len(result.review.findings)} combined findings.",
            )
            result.stages.append(merge_stage)
            await emit(_stage_payload(merge_stage))

            estimated_cost = estimate_input_cost(
                result.chunks, provider_id=config.engine.provider_id
            )
            result.review.stats = ReviewStats(
                **result.review.stats.model_dump(
                    exclude={
                        "files_analysed",
                        "hunks_sent_to_ai",
                        "chunks_sent_to_ai",
                        "files_sent_to_ai",
                        "secrets_redacted",
                        "tokens_input",
                        "tokens_output",
                        "tokens_cached",
                        "cost_usd",
                        "cost_is_estimated",
                        "duration_ms",
                    }
                ),
                hunks_sent_to_ai=_hunks_sent_to_ai(result),
                chunks_sent_to_ai=len(result.chunks),
                files_sent_to_ai=len({chunk.path for chunk in result.chunks}),
                secrets_redacted=secrets_redacted,
                files_analysed=len(
                    {
                        *(
                            path
                            for analyzer in result.analyzers
                            for path in analyzer.files_analyzed
                        ),
                        *(chunk.path for chunk in result.chunks),
                    }
                ),
                tokens_input=usage.input_tokens,
                tokens_output=usage.output_tokens,
                tokens_cached=usage.cached_tokens,
                cost_usd=usage.cost_usd if usage.cost_usd is not None else estimated_cost,
                cost_is_estimated=usage.cost_usd is None or usage.is_estimated,
                duration_ms=_duration_ms(started),
            )
            _persist_result_records(result)
            result.review.status = (
                ReviewStatus.DEGRADED
                if any(
                    analyzer.status in {"degraded", "unavailable", "failed"}
                    for analyzer in result.analyzers
                )
                else ReviewStatus.COMPLETED
            )
            result.review.finished_at = datetime.now(UTC)
            review_repo.save(result.review)
            project.last_reviewed_at = datetime.now(UTC)
            project_repo.save(project)
            await emit(
                {
                    "type": "completed",
                    "result": _response(result).model_dump(mode="json"),
                }
            )
        except asyncio.CancelledError:
            persisted = result.review if result is not None else review
            persisted.status = ReviewStatus.ABORTED
            persisted.finished_at = datetime.now(UTC)
            persisted.stats.duration_ms = _duration_ms(started)
            review_repo.save(persisted)
            await emit({"type": "aborted", "review_id": persisted.id})
            raise
        except Exception as exc:
            persisted = result.review if result is not None else review
            persisted.status = ReviewStatus.FAILED
            error_key, params = _error_key_and_params(exc)
            persisted.error = error_key
            persisted.finished_at = datetime.now(UTC)
            persisted.stats.duration_ms = _duration_ms(started)
            review_repo.save(persisted)
            await emit({"type": "failed", "error_key": error_key, "params": params})
        finally:
            if acquired_slot:
                await limiter.release()
            _enqueue_latest(queue, None)

    task = asyncio.create_task(run(), name=f"revai-review-{review.id}")
    tasks: dict[str, asyncio.Task[None]] = http_request.app.state.review_tasks
    tasks[review.id] = task

    def forget(completed: asyncio.Task[None]) -> None:
        if tasks.get(review.id) is completed:
            tasks.pop(review.id, None)

    task.add_done_callback(forget)

    async def events():
        # Client disconnect is intentionally not cancellation. The persisted job
        # continues and can be replayed from the history/events endpoint.
        while (event := await queue.get()) is not None:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{review_id}", response_model=DeterministicReviewResponse)
async def get_review(
    project_id: str,
    review_id: str,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> DeterministicReviewResponse:
    if project_repo.get(project_id) is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "project.not_found", {"project_id": project_id})
    review = review_repo.get(review_id, project_id)
    if review is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "review.not_found", {"review_id": review_id})
    return _stored_response(review)


@router.get("/{review_id}/events")
async def replay_review_events(
    project_id: str,
    review_id: str,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> StreamingResponse:
    if project_repo.get(project_id) is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "project.not_found", {"project_id": project_id})
    if review_repo.get(review_id, project_id) is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "review.not_found", {"review_id": review_id})

    async def events():
        seen = 0
        while True:
            current = review_repo.get(review_id, project_id)
            if current is None:
                return
            for event in current.events[seen:]:
                yield f"data: {json.dumps(event)}\n\n"
            seen = len(current.events)
            if current.status.is_terminal:
                return
            await asyncio.sleep(0.25)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post("/{review_id}/cancel", response_model=Review)
async def cancel_review(
    project_id: str,
    review_id: str,
    http_request: Request,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> Review:
    if project_repo.get(project_id) is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "project.not_found", {"project_id": project_id})
    review = review_repo.get(review_id, project_id)
    if review is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "review.not_found", {"review_id": review_id})
    task = http_request.app.state.review_tasks.get(review_id)
    if task is None or task.done():
        if review.status.is_terminal:
            return review
        raise RevaiError(status.HTTP_409_CONFLICT, "review.not_active", {"review_id": review_id})
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    return review_repo.get(review_id, project_id) or review


@router.post("/{review_id}/retry")
async def retry_review(
    project_id: str,
    review_id: str,
    http_request: Request,
    config_repo: ConfigRepo,
    credentials_repo: CredentialsRepo,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
    limiter: ReviewLimiterDep,
) -> StreamingResponse:
    previous = review_repo.get(review_id, project_id)
    if previous is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "review.not_found", {"review_id": review_id})
    if previous.mode is ReviewMode.STATIC:
        raise RevaiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "review.retry_static_endpoint")
    return await create_ai_review(
        project_id,
        DeterministicReviewRequest(
            base=previous.base_branch or "main",
            head=previous.head_branch or "HEAD",
            mode=previous.mode,
            scope=previous.scope,
            selected_files=previous.selected_files,
            scenario_id=previous.scenario_id,
        ),
        http_request,
        config_repo,
        credentials_repo,
        project_repo,
        review_repo,
        limiter,
    )


@router.get("", response_model=ReviewsResponse)
async def list_reviews(project_id: str, project_repo: ProjectRepo, review_repo: ReviewRepo):
    if project_repo.get(project_id) is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "project.not_found", {"project_id": project_id})
    return ReviewsResponse(reviews=review_repo.list(project_id))


@router.get("/compare/{left_review_id}/{right_review_id}", response_model=ReviewComparisonResponse)
async def compare_reviews(
    project_id: str,
    left_review_id: str,
    right_review_id: str,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> ReviewComparisonResponse:
    if project_repo.get(project_id) is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "project.not_found", {"project_id": project_id})
    left = review_repo.get(left_review_id, project_id)
    right = review_repo.get(right_review_id, project_id)
    if left is None or right is None:
        raise RevaiError(
            status.HTTP_404_NOT_FOUND,
            "review.not_found",
            {"review_id": left_review_id if left is None else right_review_id},
        )
    left_ids = {finding.fingerprint for finding in left.findings}
    right_ids = {finding.fingerprint for finding in right.findings}
    return ReviewComparisonResponse(
        left_review_id=left.id,
        right_review_id=right.id,
        new_findings=sorted(right_ids - left_ids),
        resolved_findings=sorted(left_ids - right_ids),
        persisting_findings=sorted(left_ids & right_ids),
        cost_delta_usd=right.stats.cost_usd - left.stats.cost_usd,
        duration_delta_ms=right.stats.duration_ms - left.stats.duration_ms,
    )


@router.patch("/{review_id}/findings/{finding_id}", response_model=Review)
async def update_finding_status(
    project_id: str,
    review_id: str,
    finding_id: str,
    request: FindingStatusRequest,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> Review:
    if project_repo.get(project_id) is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "project.not_found", {"project_id": project_id})
    review = review_repo.get(review_id, project_id)
    if review is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "review.not_found", {"review_id": review_id})
    finding = next((item for item in review.findings if item.id == finding_id), None)
    if finding is None:
        raise RevaiError(
            status.HTTP_404_NOT_FOUND, "review.finding_not_found", {"finding_id": finding_id}
        )
    previous = finding.status
    finding.status = request.status
    review.decisions.append(
        FindingDecision(
            finding_id=finding.id,
            from_status=previous,
            to_status=request.status,
            reason=request.reason,
        )
    )
    return review_repo.save(review)


def _response(result: DeterministicResult) -> DeterministicReviewResponse:
    return DeterministicReviewResponse(
        review=result.review,
        stages=[
            StageResponse(
                name=stage.name,
                status=stage.status,
                duration_ms=stage.duration_ms,
                detail=stage.detail,
            )
            for stage in result.stages
        ],
        analyzers=[
            AnalyzerResponse(
                name=run.name,
                status=run.status,
                findings=len(run.findings),
                duration_ms=run.duration_ms,
                detail=run.detail,
                files_analyzed=list(run.files_analyzed),
                metadata=run.metadata or {},
            )
            for run in result.analyzers
        ],
        chunks=[
            ChunkResponse(
                file=chunk.path,
                symbol=chunk.symbol,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                estimated_tokens=chunk.estimated_tokens,
            )
            for chunk in result.chunks
        ],
    )


def _stored_response(review: Review) -> DeterministicReviewResponse:
    return DeterministicReviewResponse(
        review=review,
        stages=[StageResponse(**stage.model_dump()) for stage in review.stages],
        analyzers=[AnalyzerResponse(**analyzer.model_dump()) for analyzer in review.analyzers],
        chunks=[],
    )


def _persist_result_records(result: DeterministicResult) -> None:
    result.review.stages = [
        PipelineStageRecord(
            name=stage.name,
            status=stage.status,
            duration_ms=stage.duration_ms,
            detail=stage.detail,
        )
        for stage in result.stages
    ]
    result.review.analyzers = [
        AnalyzerRecord(
            name=analyzer.name,
            status=analyzer.status,
            findings=len(analyzer.findings),
            duration_ms=analyzer.duration_ms,
            detail=analyzer.detail,
            files_analyzed=list(analyzer.files_analyzed),
            metadata=analyzer.metadata or {},
        )
        for analyzer in result.analyzers
    ]


def _hunks_sent_to_ai(result: DeterministicResult) -> int:
    chunk_paths = {chunk.path for chunk in result.chunks}
    return sum(hunk.path in chunk_paths for hunk in result.hunks)


def _replay_event(
    event: dict[str, Any], review_id: str
) -> dict[str, str | int | float | bool | None]:
    replay: dict[str, str | int | float | bool | None] = {
        "type": str(event.get("type") or "event"),
        "review_id": review_id,
        "at": datetime.now(UTC).isoformat(),
    }
    for key, value in event.items():
        if key == "result":
            continue
        if isinstance(value, str):
            replay[key] = redact_secrets(value)[0]
        elif value is None or isinstance(value, int | float | bool):
            replay[key] = value
        elif key == "metadata":
            replay[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return replay


def _stage_payload(stage: StageRun) -> dict[str, Any]:
    return {
        "type": "stage",
        "name": stage.name,
        "status": stage.status,
        "duration_ms": stage.duration_ms,
        "detail": stage.detail,
    }


def _duration_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def _git_unprocessable(exc: GitError) -> RevaiError:
    return RevaiError(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.error_key, exc.params)


def _error_key_and_params(exc: Exception) -> tuple[str, dict[str, Any]]:
    """Resolve any exception raised mid-review into `(error_key, params)`.

    Covers the internal exception types that carry their own key (AIReviewError,
    GitError, StorageError) and falls back to a generic key for anything else,
    so a review's persisted `error` field and its SSE `failed` event are always
    resolvable through the frontend's translation catalog rather than raw text.
    String params are passed through `redact_secrets` — a provider failure
    message could otherwise leak a credential fragment into review history.
    """
    error_key = getattr(exc, "error_key", None)
    params = getattr(exc, "params", None)
    if error_key is None:
        return "internal.unexpected_error", {}
    safe_params = {
        key: redact_secrets(value)[0] if isinstance(value, str) else value
        for key, value in (params or {}).items()
    }
    return error_key, safe_params


def _enqueue_latest(
    queue: asyncio.Queue[dict[str, Any] | None], event: dict[str, Any] | None
) -> None:
    """Keep SSE memory bounded while retaining the newest progress/terminal event."""
    if queue.full():
        with suppress(asyncio.QueueEmpty):
            queue.get_nowait()
    queue.put_nowait(event)
