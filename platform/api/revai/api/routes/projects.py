"""Project persistence and read-only Git workspace endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from revai.api.deps import ProjectRepo
from revai.domain.models import Project
from revai.git.repo import (
    GitError,
    branches,
    clone_repository,
    current_branch,
    diff_preview,
    inspect_project,
    tracked_files,
)
from revai.system.folder_picker import FolderPickerError, pick_directory

router = APIRouter(prefix="/projects", tags=["projects"])


class OpenProjectRequest(BaseModel):
    path: str = Field(min_length=1)


class CloneProjectRequest(BaseModel):
    remote_url: str = Field(min_length=1, max_length=2_048)
    destination_path: str = Field(min_length=1)


class ProjectView(BaseModel):
    id: str
    name: str
    path: str
    remote_url: str | None
    base_branch: str
    current_branch: str | None
    branches: list[str]
    languages: list[str]
    archived: bool
    created_at: str
    last_reviewed_at: str | None


class ProjectsResponse(BaseModel):
    projects: list[ProjectView]


class FolderPickerResponse(BaseModel):
    path: str | None


class TreeResponse(BaseModel):
    ref: str
    files: list[str]


class DiffFileResponse(BaseModel):
    path: str
    additions: int
    deletions: int
    binary: bool


class DiffResponse(BaseModel):
    base: str
    head: str
    files: list[DiffFileResponse]
    additions: int
    deletions: int
    estimated_tokens: int
    estimated_cost_usd: float
    patch: str
    truncated: bool


def _project(project_repo: ProjectRepo, project_id: str) -> Project:
    project = project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def _view(project: Project) -> ProjectView:
    path = Path(project.path)
    try:
        active = current_branch(path)
        known_branches = branches(path)
    except GitError:
        active = None
        known_branches = []

    return ProjectView(
        **project.model_dump(mode="json"),
        current_branch=active,
        branches=known_branches,
    )


def _unprocessable(exc: GitError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))


@router.get("", response_model=ProjectsResponse)
def list_projects(project_repo: ProjectRepo) -> ProjectsResponse:
    return ProjectsResponse(projects=[_view(project) for project in project_repo.list()])


@router.post("/open", response_model=ProjectView, status_code=status.HTTP_201_CREATED)
def open_project(
    request: OpenProjectRequest,
    response: Response,
    project_repo: ProjectRepo,
) -> ProjectView:
    try:
        inspected = inspect_project(Path(request.path).expanduser())
    except GitError as exc:
        raise _unprocessable(exc) from exc

    existing = next(
        (
            project
            for project in project_repo.list()
            if Path(project.path).resolve() == Path(inspected.path).resolve()
        ),
        None,
    )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return _view(existing)

    return _view(project_repo.save(inspected))


@router.post("/clone", response_model=ProjectView, status_code=status.HTTP_201_CREATED)
def clone_project(
    request: CloneProjectRequest,
    project_repo: ProjectRepo,
) -> ProjectView:
    try:
        project = clone_repository(
            request.remote_url,
            Path(request.destination_path).expanduser(),
        )
    except GitError as exc:
        raise _unprocessable(exc) from exc
    return _view(project_repo.save(project))


@router.post("/pick-folder", response_model=FolderPickerResponse)
def pick_project_folder() -> FolderPickerResponse:
    try:
        selected = pick_directory()
    except FolderPickerError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return FolderPickerResponse(path=str(selected) if selected is not None else None)


@router.get("/{project_id}", response_model=ProjectView)
def get_project(project_id: str, project_repo: ProjectRepo) -> ProjectView:
    return _view(_project(project_repo, project_id))


@router.get("/{project_id}/tree", response_model=TreeResponse)
def get_tree(
    project_id: str,
    project_repo: ProjectRepo,
    ref: Annotated[str, Query(min_length=1)] = "HEAD",
) -> TreeResponse:
    project = _project(project_repo, project_id)
    try:
        files = tracked_files(Path(project.path), ref)
    except GitError as exc:
        raise _unprocessable(exc) from exc
    return TreeResponse(ref=ref, files=files)


@router.get("/{project_id}/diff", response_model=DiffResponse)
def get_diff(
    project_id: str,
    project_repo: ProjectRepo,
    base: Annotated[str, Query(min_length=1)],
    head: Annotated[str, Query(min_length=1)],
) -> DiffResponse:
    project = _project(project_repo, project_id)
    try:
        preview = diff_preview(Path(project.path), base, head)
    except GitError as exc:
        raise _unprocessable(exc) from exc

    payload = preview.__dict__.copy()
    payload["files"] = [DiffFileResponse(**item.__dict__) for item in preview.files]
    return DiffResponse(**payload)
