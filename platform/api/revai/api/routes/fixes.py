"""Fix-application endpoints for individual review findings."""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel

from revai.api.deps import ConfigRepo, CredentialsRepo, ProjectRepo, ReviewRepo
from revai.errors import RevaiError
from revai.fixes.generator import generate_fix_patch
from revai.fixes.service import FixPreview, FixResult, apply_finding_fix
from revai.git.repo import GitError
from revai.providers.registry import build_registry

router = APIRouter(prefix="/projects/{project_id}/reviews", tags=["fixes"])


class ApplyFixRequest(BaseModel):
    dry_run: bool = False


class ApplyFixResponse(BaseModel):
    applied: bool
    dry_run: bool
    patch: str
    files: list[str]
    validation: str | None = None


async def _load_finding(
    project_id: str,
    review_id: str,
    finding_id: str,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
):
    project = project_repo.get(project_id)
    if project is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "project.not_found", {"project_id": project_id})
    review = review_repo.get(review_id, project_id)
    if review is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "review.not_found", {"review_id": review_id})
    finding = next((item for item in review.findings if item.id == finding_id), None)
    if finding is None:
        raise RevaiError(
            status.HTTP_404_NOT_FOUND, "review.finding_not_found", {"finding_id": finding_id}
        )
    return project, review, finding


def _apply_response(result: FixPreview | FixResult) -> ApplyFixResponse:
    return ApplyFixResponse(
        applied=isinstance(result, FixResult),
        dry_run=result.dry_run,
        patch=result.patch,
        files=result.files,
        validation=result.validation if isinstance(result, FixResult) else None,
    )


def _as_revai_error(exc: GitError) -> RevaiError:
    return RevaiError(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.error_key, exc.params)


@router.post(
    "/{review_id}/findings/{finding_id}/apply-fix",
    response_model=ApplyFixResponse,
)
async def apply_fix(
    project_id: str,
    review_id: str,
    finding_id: str,
    request: ApplyFixRequest,
    config_repo: ConfigRepo,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> ApplyFixResponse:
    """Apply a finding's suggested patch to the working tree (or preview it)."""
    project, review, finding = await _load_finding(
        project_id, review_id, finding_id, project_repo, review_repo
    )
    try:
        result = await apply_finding_fix(
            project,
            review,
            finding,
            dry_run=request.dry_run,
        )
    except GitError as exc:
        raise _as_revai_error(exc) from exc
    if isinstance(result, FixResult):
        review_repo.save(review)
    return _apply_response(result)


@router.post(
    "/{review_id}/findings/{finding_id}/generate-fix",
    response_model=ApplyFixResponse,
)
async def generate_fix(
    project_id: str,
    review_id: str,
    finding_id: str,
    request: ApplyFixRequest,
    config_repo: ConfigRepo,
    credentials_repo: CredentialsRepo,
    project_repo: ProjectRepo,
    review_repo: ReviewRepo,
) -> ApplyFixResponse:
    """Generate a fix with the configured model, then apply it like any other."""
    project, review, finding = await _load_finding(
        project_id, review_id, finding_id, project_repo, review_repo
    )
    config = config_repo.load()
    provider = build_registry(config, credentials_repo.load()).active()
    if provider is None:
        raise RevaiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "provider.unavailable")
    health = await provider.health()
    if not health.is_usable:
        raise RevaiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "provider.not_ready",
            {"provider_id": provider.provider_id.value},
        )

    generated = await generate_fix_patch(provider, config, project, finding)
    # Persist the generated patch immediately, including on dry runs: the
    # preview-then-confirm UI must apply exactly the patch it showed, not a
    # second (expensive, possibly different) model response.
    finding.suggested_patch = generated.patch
    review_repo.save(review)
    try:
        result = await apply_finding_fix(
            project,
            review,
            finding,
            dry_run=request.dry_run,
            patch=generated.patch,
        )
    except GitError as exc:
        raise _as_revai_error(exc) from exc
    if isinstance(result, FixResult):
        review_repo.save(review)
    return _apply_response(result)
