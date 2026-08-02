"""Deterministic and streamed AI review endpoints."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from revai.api.deps import ConfigRepo, CredentialsRepo, ProjectRepo, ReviewRepo
from revai.domain.enums import ReviewStatus
from revai.domain.models import Review, ReviewStats
from revai.git.repo import GitError
from revai.pipeline.ai import estimate_input_cost, merge_findings, run_ai_stage
from revai.pipeline.runner import DeterministicResult, StageRun, run_deterministic_pipeline
from revai.providers.base import UsageStats
from revai.providers.registry import build_registry

router = APIRouter(prefix="/projects/{project_id}/reviews", tags=["reviews"])


class DeterministicReviewRequest(BaseModel):
    base: str = Field(min_length=1)
    head: str = Field(min_length=1)


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


@router.post(
    "/deterministic",
    response_model=DeterministicReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deterministic_review(
    project_id: str,
    request: DeterministicReviewRequest,
    config_repo: ConfigRepo,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> DeterministicReviewResponse:
    project = project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    try:
        result = await run_deterministic_pipeline(
            project,
            config_repo.load(),
            base=request.base,
            head=request.head,
        )
    except GitError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    review_repo.save(result.review)
    project.last_reviewed_at = datetime.now(UTC)
    project_repo.save(project)
    return _response(result)


@router.post("/stream")
async def create_ai_review(
    project_id: str,
    request: DeterministicReviewRequest,
    config_repo: ConfigRepo,
    credentials_repo: CredentialsRepo,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> StreamingResponse:
    project = project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    config = config_repo.load()
    provider = build_registry(config, credentials_repo.load()).active()
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The configured AI provider is not available.",
        )

    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def run() -> None:
        result: DeterministicResult | None = None
        started = time.perf_counter()
        try:
            await queue.put({"type": "review_started"})
            result = await run_deterministic_pipeline(
                project,
                config,
                base=request.base,
                head=request.head,
            )
            result.review.status = ReviewStatus.RUNNING
            result.review.finished_at = None
            result.review.provider_id = config.engine.provider_id
            result.review.model = config.engine.model
            for stage in result.stages:
                await queue.put(_stage_payload(stage))
            for analyzer in result.analyzers:
                await queue.put(
                    {
                        "type": "analyzer",
                        "name": analyzer.name,
                        "status": analyzer.status,
                        "findings": len(analyzer.findings),
                        "duration_ms": analyzer.duration_ms,
                        "detail": analyzer.detail,
                    }
                )

            if result.chunks:
                ai_result = await run_ai_stage(
                    provider,
                    config,
                    result.chunks,
                    on_event=queue.put,
                )
                ai_findings = ai_result.findings
                usage = ai_result.usage
                ai_duration = ai_result.duration_ms
            else:
                ai_findings = []
                usage = UsageStats(is_estimated=True)
                ai_duration = 0

            ai_stage = StageRun(
                "ai",
                "completed",
                ai_duration,
                f"{len(ai_findings)} validated AI findings.",
            )
            result.stages.append(ai_stage)
            await queue.put(_stage_payload(ai_stage))

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
            await queue.put(_stage_payload(merge_stage))

            estimated_cost = estimate_input_cost(
                result.chunks, provider_id=config.engine.provider_id
            )
            result.review.stats = ReviewStats(
                **result.review.stats.model_dump(
                    exclude={
                        "hunks_sent_to_ai",
                        "tokens_input",
                        "tokens_output",
                        "tokens_cached",
                        "cost_usd",
                        "cost_is_estimated",
                        "duration_ms",
                    }
                ),
                hunks_sent_to_ai=len(result.chunks),
                tokens_input=usage.input_tokens,
                tokens_output=usage.output_tokens,
                tokens_cached=usage.cached_tokens,
                cost_usd=usage.cost_usd if usage.cost_usd is not None else estimated_cost,
                cost_is_estimated=usage.cost_usd is None or usage.is_estimated,
                duration_ms=_duration_ms(started),
            )
            result.review.status = ReviewStatus.COMPLETED
            result.review.finished_at = datetime.now(UTC)
            review_repo.save(result.review)
            project.last_reviewed_at = datetime.now(UTC)
            project_repo.save(project)
            await queue.put(
                {
                    "type": "completed",
                    "result": _response(result).model_dump(mode="json"),
                }
            )
        except asyncio.CancelledError:
            if result is not None:
                result.review.status = ReviewStatus.ABORTED
                result.review.finished_at = datetime.now(UTC)
                review_repo.save(result.review)
            raise
        except Exception as exc:
            if result is not None:
                result.review.status = ReviewStatus.FAILED
                result.review.error = str(exc)
                result.review.finished_at = datetime.now(UTC)
                result.review.stats.duration_ms = _duration_ms(started)
                review_repo.save(result.review)
            await queue.put({"type": "failed", "message": str(exc)})
        finally:
            await queue.put(None)

    async def events():
        task = asyncio.create_task(run())
        try:
            while (event := await queue.get()) is not None:
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", response_model=ReviewsResponse)
async def list_reviews(project_id: str, project_repo: ProjectRepo, review_repo: ReviewRepo):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return ReviewsResponse(reviews=review_repo.list(project_id))


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
