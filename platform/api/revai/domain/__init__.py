"""Domain models — the single source of truth for every shape in the product.

Everything that crosses a boundary (HTTP, YAML, provider adapter) is defined here,
so a field can never mean one thing on disk and another in the API.
"""

from revai.domain.enums import (
    Category,
    EngineMode,
    FindingSource,
    FindingStatus,
    ProviderId,
    ProviderKind,
    ReviewScope,
    ReviewStatus,
    Severity,
)
from revai.domain.models import (
    AnalyzerConfig,
    BudgetConfig,
    Credentials,
    EngineConfig,
    Finding,
    Project,
    ProviderCredential,
    RevaiConfig,
    Review,
    ReviewStats,
    UiConfig,
)

__all__ = [
    "AnalyzerConfig",
    "BudgetConfig",
    "Category",
    "Credentials",
    "EngineConfig",
    "EngineMode",
    "Finding",
    "FindingSource",
    "FindingStatus",
    "Project",
    "ProviderCredential",
    "ProviderId",
    "ProviderKind",
    "RevaiConfig",
    "Review",
    "ReviewScope",
    "ReviewStats",
    "ReviewStatus",
    "Severity",
    "UiConfig",
]
