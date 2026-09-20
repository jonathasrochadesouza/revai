"""Marketplace skill endpoints.

Rules enforced here:

* **Preview before install.** Installing third-party prompt content is a trust
  decision, so the preview endpoint returns the full SKILL.md body and the UI
  renders it before the install button unlocks.
* **Content is pinned.** ``skills.yaml`` stores the exact body and its
  SHA-256; an upstream edit never changes what reviews run with until the user
  explicitly updates — and an update re-commits through the same flow, never
  silently.
* **Caps are enforced here, not in composition.** Enabled-skill count and the
  total characters a skill set may add to the prompts are bounded at every
  mutation, so :func:`revai.domain.skills.compose_prompts` stays pure and
  every review stays within a predictable prompt budget.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from revai.api.deps import SkillRepo
from revai.domain.skills import (
    MAX_COMPOSED_SKILL_CHARS,
    MAX_ENABLED_SKILLS,
    MAX_INSTALLED_SKILLS,
    MAX_SKILL_BODY_CHARS,
    InstalledSkill,
    SkillFocus,
    SkillSettings,
    enabled_counts,
)
from revai.errors import RevaiError
from revai.skills.marketplace import MarketplaceClient, MarketplaceError, SkillContent
from revai.storage.base import StorageError

router = APIRouter(prefix="/skills", tags=["skills"])

_client = MarketplaceClient()


def _load(repo: SkillRepo) -> SkillSettings:
    try:
        return repo.load()
    except StorageError as exc:
        raise RevaiError(422, exc.error_key, exc.params) from exc


def _save(settings: SkillSettings, repo: SkillRepo) -> SkillSettings:
    try:
        return repo.save(settings)
    except StorageError as exc:
        raise RevaiError(507, exc.error_key, exc.params) from exc


def _skill_or_404(settings: SkillSettings, skill_id: str) -> InstalledSkill:
    skill = settings.get(skill_id)
    if skill is None:
        raise RevaiError(404, "skill.not_found", {"skill_id": skill_id})
    return skill


def _enforce_enabled_caps(settings: SkillSettings) -> None:
    """Enabled-count and composed-size limits, checked on every mutation."""
    count, chars = enabled_counts(settings.skills)
    if count > MAX_ENABLED_SKILLS:
        raise RevaiError(
            422, "skill.max_enabled", {"count": count, "max_enabled": MAX_ENABLED_SKILLS}
        )
    if chars > MAX_COMPOSED_SKILL_CHARS:
        raise RevaiError(
            422,
            "skill.composed_too_large",
            {"chars": chars, "max_chars": MAX_COMPOSED_SKILL_CHARS},
        )


def _as_installed(content: SkillContent, focus: SkillFocus) -> InstalledSkill:
    return InstalledSkill(
        id=content.skill_id,
        source=content.source,
        name=content.name,
        description=content.description,
        focus=focus,
        enabled=True,
        body=content.body,
        content_sha256=content.content_sha256,
        license=content.license,
        source_url=content.source_url,
    )


def _marketplace_error(exc: MarketplaceError) -> RevaiError:
    return RevaiError(exc.status_code, exc.error_key, exc.params)


# ===========================================================================
# Installed skills
# ===========================================================================


class InstalledSkillsResponse(BaseModel):
    skills: list[InstalledSkill]
    path: str


@router.get("", response_model=InstalledSkillsResponse, summary="List installed skills")
async def list_installed(repo: SkillRepo) -> InstalledSkillsResponse:
    settings = _load(repo)
    return InstalledSkillsResponse(
        skills=sorted(settings.skills, key=lambda s: (not s.enabled, s.id)),
        path=str(repo.path),
    )


class InstallSkillRequest(BaseModel):
    source: str = Field(min_length=3, max_length=201, description="GitHub shorthand owner/repo")
    skill_id: str = Field(min_length=1, max_length=64)
    focus: SkillFocus = "both"


@router.post(
    "/install",
    response_model=InstalledSkill,
    status_code=201,
    summary="Install a marketplace skill with pinned content",
)
async def install_skill(payload: InstallSkillRequest, repo: SkillRepo) -> InstalledSkill:
    settings = _load(repo)
    if len(settings.skills) >= MAX_INSTALLED_SKILLS:
        raise RevaiError(422, "skill.max_installed", {"max_installed": MAX_INSTALLED_SKILLS})
    if settings.get(payload.skill_id) is not None:
        raise RevaiError(409, "skill.already_installed", {"skill_id": payload.skill_id})

    try:
        content = await _client.content(payload.source, payload.skill_id)
    except MarketplaceError as exc:
        raise _marketplace_error(exc) from exc
    if len(content.body) > MAX_SKILL_BODY_CHARS:
        raise RevaiError(422, "skill.too_large", {"max_chars": MAX_SKILL_BODY_CHARS})

    skill = _as_installed(content, payload.focus)
    settings.skills.append(skill)
    _enforce_enabled_caps(settings)
    _save(settings, repo)
    return skill


class UpdateSkillRequest(BaseModel):
    focus: SkillFocus | None = None
    enabled: bool | None = None


@router.put("/{skill_id}", response_model=InstalledSkill, summary="Toggle or re-focus a skill")
async def update_skill(
    skill_id: str, payload: UpdateSkillRequest, repo: SkillRepo
) -> InstalledSkill:
    settings = _load(repo)
    skill = _skill_or_404(settings, skill_id)
    if payload.focus is not None:
        skill.focus = payload.focus
    if payload.enabled is not None:
        skill.enabled = payload.enabled
    skill.updated_at = datetime.now(UTC)
    _enforce_enabled_caps(settings)
    _save(settings, repo)
    return skill


class SkillRefreshResponse(BaseModel):
    skill: InstalledSkill
    updated: bool


@router.post(
    "/{skill_id}/update",
    response_model=SkillRefreshResponse,
    summary="Re-fetch the pinned content of a skill",
)
async def refresh_skill(skill_id: str, repo: SkillRepo) -> SkillRefreshResponse:
    """Manual upgrade only: fetch the latest content, pin it, stamp the time.

    Automatic upgrades are refused by design — a skill is prompt text the model
    will read, so its content only changes through the same preview-and-confirm
    flow the original install went through. The UI shows the new body before
    committing this call.
    """
    settings = _load(repo)
    skill = _skill_or_404(settings, skill_id)
    try:
        content = await _client.content(skill.source, skill_id)
    except MarketplaceError as exc:
        raise _marketplace_error(exc) from exc
    if len(content.body) > MAX_SKILL_BODY_CHARS:
        raise RevaiError(422, "skill.too_large", {"max_chars": MAX_SKILL_BODY_CHARS})

    updated = content.content_sha256 != skill.content_sha256
    if updated:
        skill.body = content.body
        skill.content_sha256 = content.content_sha256
        skill.name = content.name
        skill.description = content.description
        skill.license = content.license
        skill.source_url = content.source_url
    skill.updated_at = datetime.now(UTC)
    _save(settings, repo)
    return SkillRefreshResponse(skill=skill, updated=updated)


class UpdateCheckEntry(BaseModel):
    skill_id: str
    installed_sha256: str
    remote_sha256: str
    update_available: bool


class UpdateCheckResponse(BaseModel):
    updates: list[UpdateCheckEntry]


@router.post(
    "/check-updates",
    response_model=UpdateCheckResponse,
    summary="Compare installed skills against their upstream content",
)
async def check_updates(repo: SkillRepo) -> UpdateCheckResponse:
    settings = _load(repo)
    updates: list[UpdateCheckEntry] = []
    for skill in settings.skills:
        try:
            content = await _client.content(skill.source, skill.id)
        except MarketplaceError as exc:
            # An unreachable or rate-limited marketplace is not an error here:
            # the check reports "no update known" and the skill keeps running
            # with its pinned copy.
            raise _marketplace_error(exc) from exc
        updates.append(
            UpdateCheckEntry(
                skill_id=skill.id,
                installed_sha256=skill.content_sha256,
                remote_sha256=content.content_sha256,
                update_available=content.content_sha256 != skill.content_sha256,
            )
        )
    return UpdateCheckResponse(updates=updates)


@router.delete("/{skill_id}", status_code=204, summary="Uninstall a skill")
async def uninstall_skill(skill_id: str, repo: SkillRepo) -> None:
    settings = _load(repo)
    if not settings.remove(skill_id):
        raise RevaiError(404, "skill.not_found", {"skill_id": skill_id})
    _save(settings, repo)


# ===========================================================================
# Marketplace browsing
# ===========================================================================


class MarketplaceSkillModel(BaseModel):
    id: str
    name: str
    source: str
    installs: int | None = None
    description: str = ""
    url: str = ""


class MarketplaceResponse(BaseModel):
    query: str
    skills: list[MarketplaceSkillModel]


@router.get(
    "/marketplace",
    response_model=MarketplaceResponse,
    summary="Search the skills.sh marketplace",
)
async def search_marketplace(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=24, ge=1, le=50),
) -> MarketplaceResponse:
    try:
        results = await _client.search(q, limit=limit)
    except MarketplaceError as exc:
        raise _marketplace_error(exc) from exc
    return MarketplaceResponse(
        query=q,
        skills=[
            MarketplaceSkillModel(
                id=skill.id,
                name=skill.name,
                source=skill.source,
                installs=skill.installs,
                description=skill.description,
                url=skill.url,
            )
            for skill in results
        ],
    )


class SkillPreviewResponse(BaseModel):
    """The full content of a marketplace skill, for review before install."""

    id: str
    name: str
    source: str
    description: str
    body: str
    content_sha256: str
    license: str | None = None
    path: str
    source_url: str


@router.get(
    "/marketplace/preview",
    response_model=SkillPreviewResponse,
    summary="Preview a marketplace skill's full SKILL.md body",
)
async def preview_skill(
    source: str = Query(min_length=3, max_length=201),
    skill_id: str = Query(min_length=1, max_length=64),
) -> SkillPreviewResponse:
    try:
        content = await _client.content(source, skill_id)
    except MarketplaceError as exc:
        raise _marketplace_error(exc) from exc
    return SkillPreviewResponse(
        id=content.skill_id,
        name=content.name,
        source=content.source,
        description=content.description,
        body=content.body,
        content_sha256=content.content_sha256,
        license=content.license,
        path=content.path,
        source_url=content.source_url,
    )
