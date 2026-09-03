"""Review exports, data archive, and aggregate insights."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict
from starlette.responses import Response

from revai.api.deps import ConfigRepo, ProjectRepo, ReviewRepo, SettingsDep
from revai.errors import RevaiError
from revai.export.insights import InsightRange, InsightsResponse, build_insights
from revai.export.serializers import (
    build_data_archive,
    directory_size,
    render_html,
    render_json,
    render_legacy_json,
    render_markdown,
    render_sarif,
    safe_export_stem,
)
from revai.storage.base import StorageError

router = APIRouter(tags=["exports"])

ExportFormat = Literal["json", "md", "html", "sarif"]


class DataSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_dir: str
    reviews_dir: str
    projects: int
    reviews: int
    storage_bytes: int
    credentials_included_in_archive: bool = False


@router.get("/reviews/{review_id}/export")
async def export_review(
    review_id: str,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
    format: ExportFormat = "json",
    legacy: bool = False,
) -> Response:
    review = _find_review(review_repo, review_id)
    project = project_repo.get(review.project_id)
    stem = safe_export_stem(review, project)

    if format == "json":
        content = render_legacy_json(review) if legacy else render_json(review, project)
        suffix = "-review-data.json" if legacy else ".json"
        media_type = "application/json"
    elif format == "md":
        if legacy:
            raise RevaiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "export.legacy_json_only",
                {"format": "md"},
            )
        content = render_markdown(review, project)
        suffix = ".md"
        media_type = "text/markdown; charset=utf-8"
    elif format == "html":
        if legacy:
            raise RevaiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "export.legacy_json_only",
                {"format": "html"},
            )
        content = render_html(review, project)
        suffix = ".html"
        media_type = "text/html; charset=utf-8"
    else:
        if legacy:
            raise RevaiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "export.legacy_json_only",
                {"format": "sarif"},
            )
        content = render_sarif(review, project)
        suffix = ".sarif"
        media_type = "application/sarif+json"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{stem}{suffix}"'},
    )


@router.get("/insights", response_model=InsightsResponse)
async def insights(
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
    range: InsightRange = "30d",
) -> InsightsResponse:
    return build_insights(review_repo.list(), project_repo.list(), range)


@router.get("/data", response_model=DataSummaryResponse)
async def data_summary(
    settings: SettingsDep,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> DataSummaryResponse:
    return DataSummaryResponse(
        data_dir=str(settings.data_dir),
        reviews_dir=str(settings.reviews_dir),
        projects=len(project_repo.list()),
        reviews=len(review_repo.list()),
        storage_bytes=directory_size(settings.data_dir),
    )


@router.post("/export/all")
async def export_all(
    settings: SettingsDep,
    config_repo: ConfigRepo,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> Response:
    content = build_data_archive(
        settings,
        config_repo.load(),
        project_repo.list(),
        review_repo.list(),
    )
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="revai-data.zip"'},
    )


def _find_review(review_repo: ReviewRepo, review_id: str):
    try:
        review = review_repo.get(review_id)
    except StorageError as exc:
        raise RevaiError(
            status.HTTP_404_NOT_FOUND,
            "review.not_found",
            {"review_id": review_id},
        ) from exc
    if review is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "review.not_found", {"review_id": review_id})
    return review
