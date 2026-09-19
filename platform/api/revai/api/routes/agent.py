"""RevAI review agent endpoints: AGENTS.md preview, apply, and report demo."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import Response

from revai.agents.generator import collect_rules, compose_block, provider_line
from revai.agents.installer import install, preview_document
from revai.agents.renderer import inject_data, load_template
from revai.api.deps import ConfigRepo, ProjectRepo, SettingsDep
from revai.errors import RevaiError

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)


class AgentPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    project_name: str
    project_path: str
    agents_md_path: str
    agents_md_exists: bool
    agents_md: str
    engine: str


class AgentApplyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    agents_md: str
    template: str
    agents_md_created: bool
    backup_created: bool
    block_replaced: bool


def _block(config_repo: ConfigRepo, settings) -> str:
    return compose_block(config_repo.load(), rules=collect_rules(settings.rules_dir))


def _project_path(project_repo: ProjectRepo, project_id: str) -> Path:
    project = project_repo.get(project_id)
    if project is None:
        raise RevaiError(
            status.HTTP_404_NOT_FOUND,
            "agent.project_not_found",
            {"project_id": project_id},
        )
    path = Path(project.path).expanduser().resolve()
    if not path.is_dir():
        raise RevaiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "agent.project_path_missing",
            {"path": str(path)},
        )
    return path


@router.get("/preview", response_model=AgentPreviewResponse)
def preview(
    project_id: str,
    project_repo: ProjectRepo,
    config_repo: ConfigRepo,
    settings: SettingsDep,
) -> AgentPreviewResponse:
    project = project_repo.get(project_id)
    if project is None:
        raise RevaiError(
            status.HTTP_404_NOT_FOUND, "agent.project_not_found", {"project_id": project_id}
        )
    block = _block(config_repo, settings)
    document, exists = preview_document(Path(project.path), block)
    return AgentPreviewResponse(
        project_id=project_id,
        project_name=project.name,
        project_path=project.path,
        agents_md_path=str(Path(project.path) / "AGENTS.md"),
        agents_md_exists=exists,
        agents_md=document,
        engine=provider_line(config_repo.load()),
    )


@router.post("/apply", response_model=AgentApplyResponse)
def apply(
    request: AgentApplyRequest,
    project_repo: ProjectRepo,
    config_repo: ConfigRepo,
    settings: SettingsDep,
) -> AgentApplyResponse:
    path = _project_path(project_repo, request.project_id)
    try:
        result = install(path, _block(config_repo, settings))
    except OSError as exc:
        raise RevaiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "agent.write_failed",
            {"detail": str(exc)},
        ) from exc
    return AgentApplyResponse(
        project_id=request.project_id,
        agents_md=str(result.agents_md),
        template=str(result.template),
        agents_md_created=result.agents_md_created,
        backup_created=result.backup_created,
        block_replaced=result.block_replaced,
    )


@router.get("/report-demo")
def report_demo() -> Response:
    """A rendered sample report so Settings can preview the agent output."""
    payload = {
        "format_version": 1,
        "project": {"name": "Sample project"},
        "review": {
            "id": "demo00000000",
            "status": "completed",
            "head_branch": "feat-demo",
            "effective_model": "anthropic/claude-sonnet-5",
            "created_at": "2026-01-01T12:00:00+00:00",
            "findings": [
                {
                    "id": "f1",
                    "severity": "critical",
                    "category": "security",
                    "title": "SQL built with string concatenation",
                    "description": "The query concatenates user input directly into SQL.",
                    "rationale": "An attacker can break out of the literal and run arbitrary SQL.",
                    "file": "src/api/users.py",
                    "line_start": 42,
                    "line_end": 48,
                    "source": "ai",
                    "confidence": 0.9,
                },
                {
                    "id": "f2",
                    "severity": "medium",
                    "category": "bug",
                    "title": "Missing await on an async call",
                    "description": "The coroutine is never awaited; the write may not happen.",
                    "file": "src/store/queue.py",
                    "line_start": 17,
                    "source": "ai",
                    "confidence": 0.85,
                },
                {
                    "id": "f3",
                    "severity": "low",
                    "category": "maintainability",
                    "title": "Duplicated validation in three call sites",
                    "description": "The same shape check is repeated; extract a helper.",
                    "file": "src/handlers/upload.py",
                    "line_start": 91,
                    "source": "ai",
                    "confidence": 0.7,
                },
            ],
            "stats": {"cost_usd": 0.0123, "cost_is_estimated": False},
        },
    }
    document = inject_data(load_template(), payload)
    return Response(content=document, media_type="text/html; charset=utf-8")
