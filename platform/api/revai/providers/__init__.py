"""Provider adapters.

Every engine — a hosted API or a local CLI agent — implements the same
:class:`Provider` protocol, so the pipeline never branches on provider type.
"""

from revai.providers.base import (
    AnalysisRequest,
    HealthState,
    Provider,
    ProviderError,
    ProviderEvent,
    ProviderHealth,
)
from revai.providers.cli import ClaudeCodeProvider, CopilotCliProvider, KiroCliProvider
from revai.providers.detection import CLI_SPECS, CliSpec, detect_all_clis, detect_cli
from revai.providers.registry import ProviderRegistry, build_registry

__all__ = [
    "CLI_SPECS",
    "AnalysisRequest",
    "ClaudeCodeProvider",
    "CliSpec",
    "CopilotCliProvider",
    "HealthState",
    "KiroCliProvider",
    "Provider",
    "ProviderError",
    "ProviderEvent",
    "ProviderHealth",
    "ProviderRegistry",
    "build_registry",
    "detect_all_clis",
    "detect_cli",
]
