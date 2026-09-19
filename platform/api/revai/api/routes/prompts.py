"""Prompt template endpoints.

Rules enforced here:

* **The defaults are constants, not entities.** The two built-in prompt pairs
  (en-US / pt-BR) live in code. The file only stores user customisation, so
  "the default" always exists — editing customises it, resetting removes the
  customisation, and there is nothing to delete.
* **Language follows the interface.** Every read and write names a locale; a
  user running the app in pt-BR never sees or overwrites the en-US texts.
* **Scenarios are snapshots.** Creation copies the effective defaults of the
  requested locale; afterwards each scenario is fully independent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from revai.api.deps import ConfigRepo, PromptRepo
from revai.domain.models import PromptLocale, PromptOverride, PromptScenario, PromptSettings
from revai.domain.prompts import builtin_prompts, normalise_locale
from revai.errors import RevaiError
from revai.storage.base import StorageError

router = APIRouter(tags=["prompts"])


def _load(repo: PromptRepo) -> PromptSettings:
    try:
        return repo.load()
    except StorageError as exc:
        raise RevaiError(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.error_key, exc.params) from exc


def _save(settings: PromptSettings, repo: PromptRepo) -> PromptSettings:
    try:
        return repo.save(settings)
    except StorageError as exc:
        raise RevaiError(status.HTTP_507_INSUFFICIENT_STORAGE, exc.error_key, exc.params) from exc


def _effective_defaults(settings: PromptSettings, locale: PromptLocale) -> PromptOverride:
    override = settings.overrides.get(locale)
    if override is not None:
        return override
    system_prompt, user_prompt = builtin_prompts(locale)
    return PromptOverride(system_prompt=system_prompt, user_prompt=user_prompt)


def _scenario_or_404(settings: PromptSettings, scenario_id: str) -> PromptScenario:
    scenario = settings.scenario(scenario_id)
    if scenario is None:
        raise RevaiError(
            status.HTTP_404_NOT_FOUND,
            "prompt_scenario.not_found",
            {"scenario_id": scenario_id},
        )
    return scenario


# ===========================================================================
# Defaults (system + user prompt)
# ===========================================================================


class PromptPair(BaseModel):
    system_prompt: str
    user_prompt: str


class PromptDefaults(BaseModel):
    """The default prompts for one locale, as currently in effect."""

    locale: PromptLocale
    system_prompt: str
    user_prompt: str
    customized: bool
    updated_at: datetime | None = None


class BuiltinDefaults(BaseModel):
    """The code constants for one locale — used by "restore to default"."""

    system_prompt: str
    user_prompt: str


class PromptsResponse(BaseModel):
    locale: PromptLocale
    builtin: BuiltinDefaults
    defaults: PromptDefaults
    scenarios: list[PromptScenario]
    path: str


class SaveDefaultsRequest(BaseModel):
    locale: PromptLocale
    system_prompt: str = Field(min_length=1, max_length=20_000)
    user_prompt: str = Field(min_length=1, max_length=20_000)


class ResetDefaultsRequest(BaseModel):
    locale: PromptLocale


@router.get("/prompts", response_model=PromptsResponse, summary="Read prompt templates")
async def read_prompts(
    repo: PromptRepo,
    config_repo: ConfigRepo,
    locale: Literal["en-US", "pt-BR"] | None = Query(
        default=None, description="Defaults to the configured UI locale."
    ),
) -> PromptsResponse:
    resolved: PromptLocale = normalise_locale(locale or config_repo.load().ui.locale)
    settings = _load(repo)
    builtin = builtin_prompts(resolved)
    effective = _effective_defaults(settings, resolved)
    return PromptsResponse(
        locale=resolved,
        builtin=BuiltinDefaults(system_prompt=builtin[0], user_prompt=builtin[1]),
        defaults=PromptDefaults(
            locale=resolved,
            system_prompt=effective.system_prompt,
            user_prompt=effective.user_prompt,
            customized=resolved in settings.overrides,
            updated_at=settings.overrides[resolved].updated_at
            if resolved in settings.overrides
            else None,
        ),
        scenarios=sorted(settings.scenarios, key=lambda s: (s.name.casefold(), s.id)),
        path=str(repo.path),
    )


@router.put(
    "/prompts/defaults",
    response_model=PromptDefaults,
    summary="Customise the default prompts for one locale",
)
async def save_defaults(payload: SaveDefaultsRequest, repo: PromptRepo) -> PromptDefaults:
    """Store the customisation for ``payload.locale`` only.

    Other languages keep their own defaults — saving a pt-BR text while the app
    runs in en-US cannot leak it into the en-US prompts.
    """
    settings = _load(repo)
    override = PromptOverride(
        system_prompt=payload.system_prompt,
        user_prompt=payload.user_prompt,
        updated_at=datetime.now(UTC),
    )
    settings.overrides[payload.locale] = override
    _save(settings, repo)
    return PromptDefaults(
        locale=payload.locale,
        system_prompt=override.system_prompt,
        user_prompt=override.user_prompt,
        customized=True,
        updated_at=override.updated_at,
    )


@router.post(
    "/prompts/defaults/reset",
    response_model=PromptDefaults,
    summary="Restore the built-in prompts for one locale",
)
async def reset_defaults(payload: ResetDefaultsRequest, repo: PromptRepo) -> PromptDefaults:
    settings = _load(repo)
    removed = settings.overrides.pop(payload.locale, None)
    _save(settings, repo)
    system_prompt, user_prompt = builtin_prompts(payload.locale)
    return PromptDefaults(
        locale=payload.locale,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        customized=False,
        updated_at=removed.updated_at if removed else None,
    )


# ===========================================================================
# Scenarios
# ===========================================================================


class CreateScenarioRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    locale: PromptLocale | None = None
    # Omitted prompts copy the effective defaults of `locale`.
    system_prompt: str | None = Field(default=None, max_length=20_000)
    user_prompt: str | None = Field(default=None, max_length=20_000)


class UpdateScenarioRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(min_length=1, max_length=20_000)
    user_prompt: str = Field(min_length=1, max_length=20_000)


def _ensure_unique_name(
    settings: PromptSettings, name: str, *, exclude_id: str | None = None
) -> None:
    normalised = name.casefold()
    if any(
        scenario.name.casefold() == normalised and scenario.id != exclude_id
        for scenario in settings.scenarios
    ):
        raise RevaiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "prompt_scenario.duplicate_name",
            {"name": name},
        )


@router.post(
    "/prompts/scenarios",
    response_model=PromptScenario,
    status_code=status.HTTP_201_CREATED,
    summary="Create a prompt scenario",
)
async def create_scenario(
    payload: CreateScenarioRequest, repo: PromptRepo, config_repo: ConfigRepo
) -> PromptScenario:
    settings = _load(repo)
    _ensure_unique_name(settings, payload.name)

    locale = normalise_locale(payload.locale or config_repo.load().ui.locale)
    if payload.system_prompt is not None and payload.user_prompt is not None:
        system_prompt, user_prompt = payload.system_prompt, payload.user_prompt
    else:
        effective = _effective_defaults(settings, locale)
        system_prompt = payload.system_prompt or effective.system_prompt
        user_prompt = payload.user_prompt or effective.user_prompt

    scenario = PromptScenario(
        name=payload.name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    settings.scenarios.append(scenario)
    _save(settings, repo)
    return scenario


@router.put("/prompts/scenarios/{scenario_id}", response_model=PromptScenario)
async def update_scenario(
    scenario_id: str, payload: UpdateScenarioRequest, repo: PromptRepo
) -> PromptScenario:
    settings = _load(repo)
    scenario = _scenario_or_404(settings, scenario_id)
    _ensure_unique_name(settings, payload.name, exclude_id=scenario_id)

    scenario.name = payload.name
    scenario.system_prompt = payload.system_prompt
    scenario.user_prompt = payload.user_prompt
    scenario.updated_at = datetime.now(UTC)
    _save(settings, repo)
    return scenario


@router.delete(
    "/prompts/scenarios/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a prompt scenario",
)
async def delete_scenario(scenario_id: str, repo: PromptRepo) -> None:
    settings = _load(repo)
    if not settings.remove_scenario(scenario_id):
        raise RevaiError(
            status.HTTP_404_NOT_FOUND,
            "prompt_scenario.not_found",
            {"scenario_id": scenario_id},
        )
    _save(settings, repo)
