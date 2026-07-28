"""Provider contracts.

One protocol covers both hosted APIs and local CLI agents, so the pipeline can
consume either without branching.

The health model is deliberately more nuanced than a boolean. Probing these engines
on a real machine showed that "is it usable?" genuinely has more than two answers:
a CLI can be installed but not signed in, and — measured on Windows — GitHub Copilot
CLI returns **exit code 0 even for an invalid command**, so its authentication state
often cannot be determined without spending a request. Reporting ``UNKNOWN`` is the
honest answer there; claiming ``READY`` would be a lie the user pays for later.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from revai.domain.enums import ProviderId, ProviderKind


class ProviderError(RuntimeError):
    """A provider could not do what was asked.

    Carries ``provider_id`` so a message can name the engine that failed without the
    caller having to thread it through.
    """

    def __init__(self, message: str, provider_id: ProviderId | None = None) -> None:
        super().__init__(message)
        self.provider_id = provider_id


class HealthState(StrEnum):
    """How usable a provider is right now."""

    READY = "ready"
    """Installed (or reachable) and authenticated. Safe to run a review."""

    NEEDS_AUTH = "needs_auth"
    """Present but not signed in, or missing an API key."""

    UNKNOWN = "unknown"
    """Present, but its auth state cannot be determined without spending a request.

    This is not a placeholder for laziness — GitHub Copilot CLI ships no
    ``whoami`` equivalent and returns 0 for invalid input, so ``UNKNOWN`` is the
    only truthful answer short of billing the user for a probe.
    """

    NOT_FOUND = "not_found"
    """Not installed, or not on PATH."""

    ERROR = "error"
    """Present but misbehaving — a crash, a timeout, or unparseable output."""

    @property
    def is_usable(self) -> bool:
        """Whether a review may be attempted.

        ``UNKNOWN`` counts as usable: refusing to try would make Copilot CLI
        permanently unusable, which is worse than letting the attempt fail with a
        real error message.
        """
        return self in {HealthState.READY, HealthState.UNKNOWN}


class ProviderHealth(BaseModel):
    """The result of probing one provider."""

    model_config = ConfigDict(extra="forbid")

    provider_id: ProviderId
    kind: ProviderKind
    state: HealthState

    version: str | None = None
    """Parsed version string, when the engine reports one."""

    executable: str | None = None
    """Absolute path of the resolved binary. CLI providers only.

    Resolved with ``shutil.which`` because ``create_subprocess_exec`` cannot launch
    a bare ``.BAT``/``.CMD`` name on Windows — it fails with ``WinError 2``.
    """

    detail: str | None = None
    """Human-readable explanation. Always set for anything other than READY."""

    remediation: str | None = None
    """The command or action that would fix it, shown verbatim in the UI."""

    adapter_ready: bool = True
    """False when RevAI recognises the provider but has not implemented it yet."""

    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_usable(self) -> bool:
        return self.adapter_ready and self.state.is_usable


# ===========================================================================
# Analysis
# ===========================================================================


class AnalysisRequest(BaseModel):
    """One unit of work handed to a provider.

    Phase 2 only needs enough shape to verify connectivity; the pipeline fills in
    the rest from phase 5.
    """

    model_config = ConfigDict(extra="forbid")

    model: str
    system_prompt: str | None = None
    user_prompt: str

    max_output_tokens: int = Field(default=4096, gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    json_schema: dict | None = None
    """When set, ask the provider for output matching this schema."""

    timeout_s: int = Field(default=600, gt=0)
    """Enforced by RevAI regardless of provider support — Kiro CLI has no timeout."""


class UsageStats(BaseModel):
    """Token and cost accounting for one provider call."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0

    cost_usd: float | None = None
    """``None`` when the provider does not report cost, rather than a fabricated 0."""

    is_estimated: bool = False
    """True when cost was derived locally instead of reported by the provider."""


# --- events ---------------------------------------------------------------
# A discriminated union, so `match event.type` is exhaustive and adding a variant
# is a compile-time concern rather than a runtime surprise.


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartedEvent(_Event):
    type: Literal["started"] = "started"
    model: str
    session_id: str | None = None


class DeltaEvent(_Event):
    type: Literal["delta"] = "delta"
    text: str


class UsageEvent(_Event):
    type: Literal["usage"] = "usage"
    usage: UsageStats


class FinishedEvent(_Event):
    type: Literal["finished"] = "finished"
    text: str
    usage: UsageStats | None = None
    session_id: str | None = None


class FailedEvent(_Event):
    type: Literal["failed"] = "failed"
    message: str
    retryable: bool = False
    """Whether retrying the same provider could succeed.

    See docs/DEFERRED-FALLBACK-PROVIDER.md — the failure taxonomy that decides this
    is exactly why provider fallback was deferred rather than guessed at.
    """


ProviderEvent = StartedEvent | DeltaEvent | UsageEvent | FinishedEvent | FailedEvent


# ===========================================================================
# The protocol
# ===========================================================================


@runtime_checkable
class Provider(Protocol):
    """What every engine must offer.

    A ``Protocol`` rather than a base class: an adapter only has to match the shape,
    which keeps a CLI adapter from inheriting HTTP concerns and vice versa.
    """

    provider_id: ProviderId
    kind: ProviderKind

    async def health(self) -> ProviderHealth:
        """Probe without spending money.

        Must never raise — a broken provider is a reportable state, not an
        exception, because the UI has to render every provider including the failed
        ones.
        """
        ...

    def analyze(self, request: AnalysisRequest) -> AsyncIterator[ProviderEvent]:
        """Run one analysis, yielding events as they arrive.

        Not ``async def``: an async generator function is already awaitable at
        iteration time, and declaring it ``async`` would require callers to await
        before iterating.
        """
        ...
