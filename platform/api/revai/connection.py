"""Aggregated connection status: "can RevAI run a review right now?".

One question, asked from every screen, answered from one cached place.

Three properties define this module:

* **Probing is expensive, so it is cached.** Determining AI readiness calls
  ``ProviderRegistry.health_all()``, which spawns three CLI subprocesses. A banner
  present on every screen cannot pay that per navigation, so each section is held
  in a short-lived in-process cache and an explicit refresh is the only way to
  force a re-probe.
* **The verdict follows the *configured* provider.** A review runs with
  ``engine.provider_id``; "some provider somewhere is ready" would report green
  while every review fails. The readiness of the others is still reported, as a
  scoreboard, because it lets the interface name a working alternative.
* **No interface copy lives here.** The response carries enumerated states and
  verdicts only. Sentences are composed in the web catalog, where the locale is
  known — the same split the provider endpoints already follow.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from revai.config import Settings
from revai.domain.enums import ProviderId
from revai.domain.models import Credentials, RevaiConfig
from revai.providers.base import HealthState, ProviderHealth
from revai.providers.registry import build_registry

AI_TTL_S = 30.0
"""Long enough to cover a burst of navigations, short enough that fixing a key feels
immediate — and any config-changing action refreshes explicitly anyway."""


class AiVerdict(StrEnum):
    """How usable the AI half of the product is, in four distinguishable ways."""

    OK = "ok"
    """The configured provider is ready. A review can run."""

    ACTIVE_BROKEN = "active_broken"
    """The configured provider is not usable, but another one is ready."""

    NONE_READY = "none_ready"
    """The configured provider is not usable and no other provider is ready."""

    UNKNOWN = "unknown"
    """The configured provider's state cannot be determined without spending a
    request — GitHub Copilot CLI ships no auth-status command. Worth warning about,
    but never as a claimed failure."""


class ApiSection(BaseModel):
    """The backend answering at all is the proof; the fields are its identity."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    app: str
    version: str
    environment: str


class AiSection(BaseModel):
    """The configured provider, plus the scoreboard across every known provider."""

    model_config = ConfigDict(extra="forbid")

    active_provider_id: ProviderId
    active_state: HealthState
    active_usable: bool
    active_version: str | None = None
    active_detail: str | None = None
    active_remediation: str | None = Field(
        default=None,
        description="Passed through from the provider probe, shown verbatim.",
    )
    ready_provider_ids: list[ProviderId] = Field(
        default_factory=list,
        description="Providers that probed READY and have an implemented adapter.",
    )
    unknown_provider_ids: list[ProviderId] = Field(
        default_factory=list,
        description="Providers whose state could not be determined.",
    )
    total: int = Field(description="How many providers RevAI knows about.")
    verdict: AiVerdict


class StatusResponse(BaseModel):
    """One round trip, two sections, plus the freshness of the answer."""

    model_config = ConfigDict(extra="forbid")

    api: ApiSection
    ai: AiSection
    checked_at: datetime = Field(
        description="When the oldest section in this response was collected."
    )
    from_cache: bool = Field(description="True only when no section was probed again.")
    ttl_s: float = Field(description="Shortest TTL among the cached sections.")


def classify_ai(healths: list[ProviderHealth], active_provider_id: ProviderId) -> AiSection:
    """Turn a provider sweep into the AI section.

    Adapter readiness is kept separate from health: a provider RevAI recognises but
    has not implemented can never count as ready, and the user cannot fix it either,
    so it never drives the verdict.
    """
    usable = [health for health in healths if health.adapter_ready]
    ready = [h.provider_id for h in usable if h.state is HealthState.READY]
    unknown = [h.provider_id for h in usable if h.state is HealthState.UNKNOWN]
    active = next((h for h in healths if h.provider_id is active_provider_id), None)

    if active is not None and active.adapter_ready and active.state is HealthState.READY:
        verdict = AiVerdict.OK
    elif active is not None and active.adapter_ready and active.state is HealthState.UNKNOWN:
        verdict = AiVerdict.UNKNOWN
    elif ready:
        verdict = AiVerdict.ACTIVE_BROKEN
    else:
        verdict = AiVerdict.NONE_READY

    return AiSection(
        active_provider_id=active_provider_id,
        # A missing entry would mean the sweep skipped a known provider; reporting
        # ERROR is truthful and keeps the response shape total.
        active_state=active.state if active is not None else HealthState.ERROR,
        active_usable=active.is_usable if active is not None else False,
        active_version=active.version if active is not None else None,
        active_detail=active.detail if active is not None else None,
        active_remediation=active.remediation if active is not None else None,
        ready_provider_ids=ready,
        unknown_provider_ids=unknown,
        total=len(healths),
        verdict=verdict,
    )


@dataclass
class _Cached[T]:
    """A value with both a wall-clock collection time and a monotonic expiry.

    Two clocks on purpose: the timestamp is reported to the user, while expiry must
    not be affected by the system clock being adjusted.
    """

    value: T
    collected_at: datetime
    expires_at: float

    @property
    def fresh(self) -> bool:
        return time.monotonic() < self.expires_at


class StatusService:
    """Collects and caches the status sections.

    One instance per application (held on ``app.state``) rather than a module
    global, so each test app starts with an empty cache.
    """

    def __init__(self, ai_ttl_s: float = AI_TTL_S) -> None:
        self._ai_ttl_s = ai_ttl_s
        self._ai: _Cached[AiSection] | None = None

    async def collect(
        self,
        settings: Settings,
        config: RevaiConfig,
        credentials: Credentials,
        *,
        refresh: bool = False,
    ) -> StatusResponse:
        ai, ai_cached = await self._ai_section(config, credentials, refresh=refresh)

        return StatusResponse(
            api=ApiSection(
                app=settings.app_name,
                version=settings.version,
                environment=settings.environment,
            ),
            ai=ai.value,
            checked_at=ai.collected_at,
            from_cache=ai_cached,
            ttl_s=self._ai_ttl_s,
        )

    async def _ai_section(
        self, config: RevaiConfig, credentials: Credentials, *, refresh: bool
    ) -> tuple[_Cached[AiSection], bool]:
        if not refresh and self._ai is not None and self._ai.fresh:
            return self._ai, True
        registry = build_registry(config, credentials)
        section = classify_ai(await registry.health_all(), config.engine.provider_id)
        self._ai = _Cached(section, datetime.now(UTC), time.monotonic() + self._ai_ttl_s)
        return self._ai, False
