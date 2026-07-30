"""Deterministic review endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from revai.api.deps import ConfigRepo, ProjectRepo, ReviewRepo
from revai.domain.models import Review
from revai.git.repo import GitError
from revai.pipeline.runner import DeterministicResult, run_deterministic_pipeline

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
