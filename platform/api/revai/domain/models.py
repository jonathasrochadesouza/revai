"""Persisted and transported shapes.

Design rules applied throughout:

* Every persisted document carries ``schema_version`` so migrations are possible.
* Timestamps are timezone-aware UTC. Naive datetimes are a bug waiting to happen
  once anyone exports a review.
* Defaults are chosen so an empty file deserialises into something usable — a
  fresh install has no config, and that must not be an error path.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from revai.domain.enums import (
    SCHEMA_VERSION,
    Category,
    EngineMode,
    FindingSource,
    FindingStatus,
    ProviderId,
    ReviewMode,
    ReviewScope,
    ReviewStatus,
    Severity,
)
from revai.domain.prompts import PromptLocale


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    """A short, URL-safe, filename-safe identifier.

    12 hex characters — collision-safe for a single-user local tool and short
    enough to read out loud when debugging.
    """
    return uuid.uuid4().hex[:12]


class _Base(BaseModel):
    """Shared configuration for every domain model."""

    model_config = ConfigDict(
        extra="forbid",  # catch typos in hand-edited YAML instead of ignoring them
        validate_assignment=True,
        use_enum_values=False,
        str_strip_whitespace=True,
    )


class _Document(_Base):
    """A model that gets written to its own file."""

    schema_version: int = SCHEMA_VERSION


# ===========================================================================
# Findings
# ===========================================================================


class Finding(_Base):
    """A single reviewable problem.

    Five fields here do not exist in the legacy JSON, and their absence is why the
    current report cannot deduplicate, rank, or render a stable identifier:

    * ``id``               — stable reference for the UI and for status changes
    * ``category``         — orthogonal to severity, drives the metrics breakdown
    * ``source``           — which stage found it, so merge can rank by confidence
    * ``confidence``       — used for ordering and for filtering noise
    * ``suggested_patch``  — a unified diff, never applied automatically
    """

    id: str = Field(default_factory=_new_id)
    fingerprint: str = ""
    severity: Severity
    category: Category
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)

    # Markdown. This is the "why this matters" block in the UI.
    rationale: str = ""

    file: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int | None = Field(default=None, ge=1)

    source: FindingSource
    rule_id: str | None = None  # CWE-347, S1192, no-unused-vars, ...
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0

    suggested_patch: str | None = None
    status: FindingStatus = FindingStatus.OPEN

    @model_validator(mode="after")
    def _check_line_range(self) -> Self:
        """A range that ends before it starts silently breaks the diff viewer."""
        if self.line_end is not None and self.line_end < self.line_start:
            raise PydanticCustomError(
                "finding.line_end_precedes_line_start",
                "line_end ({line_end}) precedes line_start ({line_start})",
                {"line_end": self.line_end, "line_start": self.line_start},
            )
        if not self.fingerprint:
            identity = "\0".join(
                (
                    self.file.replace("\\", "/"),
                    str(self.line_start),
                    self.rule_id or self.title.lower(),
                )
            )
            object.__setattr__(
                self,
                "fingerprint",
                hashlib.sha256(identity.encode()).hexdigest()[:16],
            )
        if self.suggested_patch and not _looks_like_unified_diff(self.suggested_patch):
            # Provider prose is a suggestion, not an applicable patch. Never let
            # the UI represent unvalidated output as something Git can apply.
            object.__setattr__(self, "suggested_patch", None)
        return self

    @property
    def lines(self) -> str:
        """Legacy display format: ``45-120`` or ``45``."""
        if self.line_end is None or self.line_end == self.line_start:
            return str(self.line_start)
        return f"{self.line_start}-{self.line_end}"

    @property
    def is_actionable(self) -> bool:
        """Still needs a decision from the user."""
        return self.status == FindingStatus.OPEN

    @property
    def dedupe_key(self) -> tuple[str, int, str]:
        """Identity for cross-source deduplication.

        Two sources reporting the same line of the same file about the same rule
        are the same problem, even when the wording differs.
        """
        return (self.file, self.line_start, (self.rule_id or self.title).lower())


# ===========================================================================
# Reviews
# ===========================================================================


class ReviewStats(_Base):
    """Cost and volume accounting for one run.

    Cost is separated from token counts because CLI providers report tokens
    unreliably and some report no cost at all — ``cost_is_estimated`` keeps the UI
    honest rather than presenting a guess as a fact.
    """

    files_analysed: int = 0
    files_skipped: int = 0
    hunks_total: int = 0
    hunks_sent_to_ai: int = 0
    chunks_prepared: int = 0
    chunks_sent_to_ai: int = 0
    files_sent_to_ai: int = 0
    secrets_redacted: int = 0
    estimated_context_tokens: int = 0

    tokens_input: int = 0
    tokens_output: int = 0
    tokens_cached: int = 0

    cost_usd: float = 0.0
    cost_is_estimated: bool = False

    duration_ms: int = 0

    @property
    def tokens_total(self) -> int:
        return self.tokens_input + self.tokens_output

    @property
    def filter_ratio(self) -> float:
        """Share of hunks the deterministic stage kept out of the model.

        This is the number that justifies the hybrid pipeline, so it is computed
        rather than stored.
        """
        if self.hunks_total == 0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - (self.hunks_sent_to_ai / self.hunks_total)))


class PipelineStageRecord(_Base):
    """Persisted pipeline stage, used both live and when replaying history."""

    name: str
    status: Literal["completed", "degraded", "failed", "skipped"]
    duration_ms: int = Field(ge=0)
    detail: str | None = None


class AnalyzerRecord(_Base):
    """Persisted analyzer outcome and its real coverage."""

    name: str
    status: Literal["completed", "degraded", "unavailable", "failed", "skipped"]
    findings: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    detail: str | None = None
    files_analyzed: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class FindingDecision(_Base):
    finding_id: str
    from_status: FindingStatus
    to_status: FindingStatus
    reason: str | None = None
    decided_at: datetime = Field(default_factory=_now)


class Review(_Document):
    """One review run and its results."""

    id: str = Field(default_factory=_new_id)
    project_id: str

    scope: ReviewScope
    mode: ReviewMode = ReviewMode.BOTH
    status: ReviewStatus = ReviewStatus.QUEUED

    base_branch: str | None = None
    head_branch: str | None = None
    selected_files: list[str] = Field(default_factory=list)

    provider_id: ProviderId | None = None
    model: str | None = None
    effective_model: str | None = None
    provider_version: str | None = None
    config_hash: str | None = None
    prompt_hash: str | None = None
    # Prompt scenario chosen for this run (None = the default prompts). Stored
    # so retry re-runs with the same prompt pair the user selected.
    scenario_id: str | None = None

    findings: list[Finding] = Field(default_factory=list)
    stats: ReviewStats = Field(default_factory=ReviewStats)
    stages: list[PipelineStageRecord] = Field(default_factory=list)
    analyzers: list[AnalyzerRecord] = Field(default_factory=list)
    # Capped, sanitized event envelopes; model deltas and source content are never
    # persisted. They make completed reviews faithfully replayable after restart.
    events: list[dict[str, str | int | float | bool | None]] = Field(default_factory=list)
    decisions: list[FindingDecision] = Field(default_factory=list)

    # Populated from git, mirroring the legacy aditional-data.json.
    author: str = "Undefined"
    reviewer: str = "Undefined"

    error: str | None = None

    created_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None

    def count(self, severity: Severity) -> int:
        """Open findings at a given severity."""
        return sum(1 for f in self.findings if f.severity == severity and f.is_actionable)

    @property
    def sorted_findings(self) -> list[Finding]:
        """Critical first, then by descending confidence within each level."""
        return sorted(
            self.findings,
            key=lambda f: (f.severity.rank, -f.confidence, f.file, f.line_start),
        )


# ===========================================================================
# Projects
# ===========================================================================


class Project(_Document):
    """A repository RevAI knows about."""

    id: str = Field(default_factory=_new_id)
    name: str = Field(min_length=1, max_length=120)

    # Kept as a string rather than Path: it round-trips cleanly through YAML and
    # JSON, and Windows paths survive without escaping surprises.
    path: str = Field(min_length=1)
    remote_url: str | None = None

    # Replaces the hardcoded `develop` in the PowerShell scripts. Detected on
    # first open, overridable per project.
    base_branch: str = "main"

    languages: list[str] = Field(default_factory=list)
    checkstyle_command: list[str] = Field(default_factory=list)
    test_command: list[str] = Field(default_factory=list)
    build_command: list[str] = Field(default_factory=list)
    archived: bool = False

    created_at: datetime = Field(default_factory=_now)
    last_reviewed_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def _no_path_separators(cls, value: str) -> str:
        """The name is used in filenames, so separators would escape the directory."""
        if "/" in value or "\\" in value:
            raise PydanticCustomError(
                "project.name_contains_path_separators",
                "project name must not contain path separators",
                {"name": value},
            )
        return value


# ===========================================================================
# Configuration
# ===========================================================================


class BudgetConfig(_Base):
    """Hard limits so a runaway review cannot surprise the user.

    ``None`` means *unlimited* for the two spend and size caps. It is modelled as
    ``None`` rather than a sentinel like ``0`` or ``-1`` because those would be
    indistinguishable from a mistake, and a mistake in a spend cap is expensive.
    Unlimited is a deliberate, explicit choice — the UI surfaces it with a warning.
    """

    max_spend_usd: float | None = Field(default=0.50, gt=0)
    max_context_tokens: int | None = Field(default=60_000, gt=0)
    warn_above_usd: float = Field(default=0.25, ge=0)
    request_timeout_s: int = Field(default=600, gt=0)
    max_concurrent_reviews: int = Field(default=1, ge=1, le=8)
    max_retry_attempts: int = Field(default=1, ge=0, le=3)

    @model_validator(mode="after")
    def _warn_below_max(self) -> Self:
        """A warning threshold above the hard cap would never fire.

        Skipped when spending is unlimited: with no cap there is nothing for the
        threshold to exceed, so any warning value is meaningful.
        """
        if self.max_spend_usd is not None and self.warn_above_usd > self.max_spend_usd:
            raise PydanticCustomError(
                "budget.warn_above_exceeds_max",
                "warn_above_usd ({warn_above_usd}) must not exceed max_spend_usd ({max_spend_usd})",
                {"warn_above_usd": self.warn_above_usd, "max_spend_usd": self.max_spend_usd},
            )
        return self

    @property
    def spend_is_unlimited(self) -> bool:
        return self.max_spend_usd is None

    @property
    def context_is_unlimited(self) -> bool:
        return self.max_context_tokens is None


class SonarQubeConfig(_Base):
    """Connection metadata for a self-hosted SonarQube Server / Community Build.

    ``project_key`` defaults to ``revai-local`` so the one-screen local setup
    works without editing anything: the local provisioning flow creates that
    project in a fresh server.

    The token lives in ``credentials.yaml`` (written by the local provisioning
    flow) with ``SONAR_TOKEN`` as the external-server fallback; that keeps an
    external service credential out of ordinary review preferences.
    """

    enabled: bool = False
    server_url: str = "http://127.0.0.1:9000"
    project_key: str | None = "revai-local"
    timeout_s: int = Field(default=300, ge=10, le=3600)
    wait_for_quality_gate: bool = True
    quality_gate_timeout_s: int = Field(default=300, ge=10, le=3600)
    new_code_only: bool = True
    scanner: Literal["auto", "maven", "gradle", "cli"] = "auto"
    wsl: bool = False


class AnalyzerConfig(_Base):
    """The deterministic stage. Every analyzer is optional and costs no tokens."""

    security: bool = True
    semgrep: bool = True
    ruff: bool = True
    eslint: bool = True
    gitleaks: bool = True
    checkstyle: bool = False
    project_tests: bool = False
    project_build: bool = False
    treesitter: bool = True
    sonarqube: SonarQubeConfig = Field(default_factory=SonarQubeConfig)

    skip_noise: bool = True  # lockfiles, generated, minified, binaries
    changed_lines_only: bool = True  # the +/- rule from the legacy prompt
    dedupe_across_sources: bool = True

    @property
    def enabled(self) -> list[str]:
        flags = (
            "security",
            "semgrep",
            "ruff",
            "eslint",
            "gitleaks",
            "checkstyle",
            "project_tests",
            "project_build",
            "treesitter",
        )
        enabled = [name for name in flags if getattr(self, name)]
        if self.sonarqube.enabled:
            enabled.append("sonarqube")
        return enabled


class EngineConfig(_Base):
    """Which engine runs reviews.

    Provider fallback was specified and then deliberately deferred — a fallback that
    silently changes model mid-review makes cost and quality unattributable, and it
    needs a failure taxonomy to be useful at all. The full design is preserved in
    ``platform/docs/DEFERRED-FALLBACK-PROVIDER.md``.

    ``model_config`` relaxes ``extra`` to ``ignore`` for this one model so a
    ``config.yaml`` written by an earlier build — which contains
    ``fallback_provider_id`` and ``fallback_model`` — still loads. Dropping those keys
    on the next save is the migration.
    """

    model_config = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    mode: EngineMode = EngineMode.API
    provider_id: ProviderId = ProviderId.OPENROUTER
    model: str = "anthropic/claude-sonnet-5"

    # For a provider proxy or a self-hosted endpoint such as Ollama.
    base_url: str | None = None

    @model_validator(mode="after")
    def _migrate_kiro_default(self) -> Self:
        if self.provider_id is ProviderId.KIRO_CLI and self.model == "kiro-default":
            object.__setattr__(self, "model", "claude-haiku-4.5")
        return self


class UiConfig(_Base):
    """Presentation preferences."""

    # ``en`` was used by alpha config files. Normalize it while loading so a
    # user upgrade never silently drops their preferred language.
    locale: Literal["en-US", "pt-BR"] = "en-US"
    theme: Literal["light", "dark", "system"] = "system"
    confirm_expensive_reviews: bool = True

    # Three states on purpose. ``None`` means the user has not answered the
    # auto-save offer yet, so the web UI keeps asking while changes are pending.
    # ``True`` enables automatic saves; ``False`` is both "off" and "stop asking",
    # which keeps the answer re-visitable in Settings without a second field.
    auto_save: bool | None = None

    @field_validator("locale", mode="before")
    @classmethod
    def _migrate_legacy_locale(cls, value: object) -> object:
        return "en-US" if value == "en" else value


class RevaiConfig(_Document):
    """``~/.revai/config.yaml``.

    Every field has a default, so a missing file is a valid empty configuration
    rather than a startup failure.
    """

    engine: EngineConfig = Field(default_factory=EngineConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    analyzers: AnalyzerConfig = Field(default_factory=AnalyzerConfig)
    ui: UiConfig = Field(default_factory=UiConfig)

    updated_at: datetime = Field(default_factory=_now)


def _looks_like_unified_diff(value: str) -> bool:
    """Accept only a real file patch, never a fenced snippet or instructions."""
    lines = value.replace("\r\n", "\n").splitlines()
    return (
        len(lines) >= 3
        and lines[0].startswith("--- ")
        and lines[1].startswith("+++ ")
        and any(line.startswith("@@ ") for line in lines[2:])
    )


# ===========================================================================
# Credentials — separate file, separate permissions
# ===========================================================================


class ProviderCredential(_Base):
    """One provider's secret.

    ``api_key`` is never included in an API response; routes return
    :meth:`masked` instead.
    """

    provider_id: ProviderId
    api_key: str = Field(min_length=1)
    label: str | None = None
    created_at: datetime = Field(default_factory=_now)

    def masked(self) -> str:
        """Enough to recognise the key, not enough to use it."""
        if len(self.api_key) <= 12:
            return "•" * len(self.api_key)
        return f"{self.api_key[:8]}{'•' * 16}{self.api_key[-4:]}"


class SonarQubeCredential(_Base):
    """Secrets for a locally provisioned SonarQube Community Build.

    Written by the provisioning flow (see ``revai.sonarqube.local``) and never
    included in an API response — routes return :meth:`masked`.
    """

    token: str = Field(min_length=1, repr=False)
    admin_password: str = Field(min_length=1, repr=False)
    created_at: datetime = Field(default_factory=_now)

    def masked(self) -> str:
        """Enough to recognise the token, not enough to use it."""
        if len(self.token) <= 12:
            return "•" * len(self.token)
        return f"{self.token[:8]}{'•' * 16}{self.token[-4:]}"


class Credentials(_Document):
    """``~/.revai/credentials.yaml`` — chmod 600, never inside a project folder."""

    providers: dict[ProviderId, ProviderCredential] = Field(default_factory=dict)
    sonarqube: SonarQubeCredential | None = None

    def get(self, provider_id: ProviderId) -> ProviderCredential | None:
        return self.providers.get(provider_id)

    def put(self, credential: ProviderCredential) -> None:
        self.providers[credential.provider_id] = credential

    def remove(self, provider_id: ProviderId) -> bool:
        return self.providers.pop(provider_id, None) is not None

    @property
    def configured(self) -> list[ProviderId]:
        return sorted(self.providers, key=lambda p: p.value)


# ===========================================================================
# Prompt templates — separate file, follows the selected interface language
# ===========================================================================


class PromptOverride(_Base):
    """A customised default prompt pair for one interface locale.

    ``user_prompt`` holds only the editable review instructions. The
    anti-injection guard and the JSON payload sentinel are fixed server-side
    scaffolding (see ``revai.domain.prompts``), so no edit — however careless —
    can remove the untrusted-data boundary from a model request.
    """

    system_prompt: str = Field(min_length=1, max_length=20_000)
    user_prompt: str = Field(min_length=1, max_length=20_000)
    updated_at: datetime = Field(default_factory=_now)


class PromptScenario(_Document):
    """A named prompt pair — e.g. "Backend - Java" — chosen per review.

    The prompts are an independent snapshot, copied from the effective defaults
    of the interface language at creation time: later edits to the defaults
    never silently rewrite a scenario the user curated on purpose.
    """

    id: str = Field(default_factory=_new_id)
    name: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(min_length=1, max_length=20_000)
    user_prompt: str = Field(min_length=1, max_length=20_000)

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class PromptSettings(_Document):
    """``~/.revai/prompts.yaml``.

    Every field has a default, so a missing file means "built-in prompts, no
    scenarios" rather than a startup failure. Overrides are keyed by locale so
    each language keeps its own customisation — the two defaults are code
    constants and are therefore never deletable entities.
    """

    overrides: dict[PromptLocale, PromptOverride] = Field(default_factory=dict)
    scenarios: list[PromptScenario] = Field(default_factory=list)

    def scenario(self, scenario_id: str) -> PromptScenario | None:
        return next((item for item in self.scenarios if item.id == scenario_id), None)

    def remove_scenario(self, scenario_id: str) -> bool:
        before = len(self.scenarios)
        self.scenarios = [item for item in self.scenarios if item.id != scenario_id]
        return len(self.scenarios) < before
