"""Closed vocabularies.

Every one of these is a `str` enum so it serialises to a readable YAML scalar and
still validates on the way back in. Adding a member is a schema change — bump
``SCHEMA_VERSION`` when that happens.
"""

from __future__ import annotations

from enum import StrEnum

# Bumped whenever a persisted shape changes. Documents carry this so a future
# release can migrate instead of failing to parse.
SCHEMA_VERSION = 4


class Severity(StrEnum):
    """How much a finding matters.

    Deliberately three levels, matching the existing PowerShell prompt so legacy
    reports import without translation.
    """

    CRITICAL = "critical"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        """Sort weight — lower sorts first."""
        return {"critical": 0, "medium": 1, "low": 2}[self.value]


class Category(StrEnum):
    """What kind of problem a finding is, independent of severity."""

    SECURITY = "security"
    BUG = "bug"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    STYLE = "style"


class FindingSource(StrEnum):
    """Which stage produced a finding.

    Kept as an enum rather than a free string so the merge stage can rank by
    source confidence without guessing at spellings.
    """

    AI = "ai"
    SEMGREP = "semgrep"
    RUFF = "ruff"
    ESLINT = "eslint"
    GITLEAKS = "gitleaks"
    CHECKSTYLE = "checkstyle"
    TREESITTER = "treesitter"
    SECURITY = "security"
    SONARQUBE = "sonarqube"


class FindingStatus(StrEnum):
    """What the user decided about a finding."""

    OPEN = "open"
    FIXED = "fixed"
    DISMISSED = "dismissed"
    FALSE_POSITIVE = "false_positive"


class ReviewScope(StrEnum):
    """What a review looked at."""

    BRANCH_DIFF = "branch_diff"
    SELECTED_FILES = "selected_files"
    WHOLE_PROJECT = "whole_project"


class ReviewMode(StrEnum):
    """How a review combines deterministic and AI analysis."""

    STATIC = "static"
    AI_ASSISTED = "ai_assisted"
    BOTH = "both"


class ReviewStatus(StrEnum):
    """Lifecycle of a review run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    DEGRADED = "degraded"
    FAILED = "failed"
    ABORTED = "aborted"

    @property
    def is_terminal(self) -> bool:
        return self in {
            ReviewStatus.COMPLETED,
            ReviewStatus.DEGRADED,
            ReviewStatus.FAILED,
            ReviewStatus.ABORTED,
        }


class EngineMode(StrEnum):
    """How RevAI reaches a model.

    The two options the user picks between on the onboarding screen.
    """

    API = "api"
    CLI = "cli"


class ProviderKind(StrEnum):
    """Transport used by a provider adapter."""

    API = "api"
    CLI = "cli"


class ProviderId(StrEnum):
    """Known providers.

    ``OPENROUTER`` is the one implemented in phase 2; the rest are declared now so
    config files written today stay valid when their adapters land in phase 10.
    """

    # --- API ---
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    # --- CLI ---
    CLAUDE_CODE = "claude_code"
    COPILOT_CLI = "copilot_cli"
    KIRO_CLI = "kiro_cli"

    @property
    def kind(self) -> ProviderKind:
        return (
            ProviderKind.CLI
            if self
            in {
                ProviderId.CLAUDE_CODE,
                ProviderId.COPILOT_CLI,
                ProviderId.KIRO_CLI,
            }
            else ProviderKind.API
        )
