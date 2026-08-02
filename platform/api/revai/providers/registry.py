"""Provider lookup.

The registry is the only place that knows which adapters exist, so adding one is a
single-line change here rather than an edit scattered across routes and pipeline
stages.
"""

from __future__ import annotations

import asyncio
import logging

from revai.domain.enums import ProviderId, ProviderKind
from revai.domain.models import Credentials, RevaiConfig
from revai.providers.api.openrouter import OpenRouterProvider
from revai.providers.base import HealthState, Provider, ProviderHealth
from revai.providers.cli import ClaudeCodeProvider, CopilotCliProvider, KiroCliProvider

logger = logging.getLogger(__name__)

# API providers whose adapters are not written yet. Declared so the panel can list
# them as recognised-but-unavailable instead of pretending they do not exist.
_PLANNED_API_PROVIDERS: tuple[ProviderId, ...] = (
    ProviderId.ANTHROPIC,
    ProviderId.OPENAI,
    ProviderId.GEMINI,
    ProviderId.OLLAMA,
)


class ProviderRegistry:
    """Resolves a provider id to a working adapter."""

    def __init__(self, config: RevaiConfig, credentials: Credentials) -> None:
        self._config = config
        self._credentials = credentials

    # -- lookup -------------------------------------------------------------

    def get(self, provider_id: ProviderId) -> Provider | None:
        """Return an adapter, or ``None`` when one is not implemented yet."""
        if provider_id is ProviderId.OPENROUTER:
            credential = self._credentials.get(ProviderId.OPENROUTER)
            return OpenRouterProvider(
                api_key=credential.api_key if credential else None,
                base_url=self._config.engine.base_url,
            )
        if provider_id is ProviderId.CLAUDE_CODE:
            return ClaudeCodeProvider()
        if provider_id is ProviderId.COPILOT_CLI:
            return CopilotCliProvider()
        if provider_id is ProviderId.KIRO_CLI:
            return KiroCliProvider()
        return None

    def active(self) -> Provider | None:
        """The adapter for the currently configured engine."""
        return self.get(self._config.engine.provider_id)

    # -- health -------------------------------------------------------------

    async def health_all(self) -> list[ProviderHealth]:
        """Probe every provider RevAI knows about.

        API probes and CLI probes run concurrently: three CLI probes with a 20-second
        ceiling each would otherwise block a request for a minute.
        """
        implemented = [
            self.get(provider_id)
            for provider_id in (
                ProviderId.OPENROUTER,
                ProviderId.CLAUDE_CODE,
                ProviderId.COPILOT_CLI,
                ProviderId.KIRO_CLI,
            )
        ]
        implemented_healths = await asyncio.gather(
            *(provider.health() for provider in implemented if provider is not None)
        )

        planned = [_planned(provider_id) for provider_id in _PLANNED_API_PROVIDERS]

        api_healths = [health for health in implemented_healths if health.kind is ProviderKind.API]
        cli_healths = [health for health in implemented_healths if health.kind is ProviderKind.CLI]
        return [*api_healths, *planned, *cli_healths]


def _planned(provider_id: ProviderId) -> ProviderHealth:
    """A recognised provider with no adapter yet.

    Listed rather than hidden so the roadmap is visible in the product, not only in
    the docs.
    """
    return ProviderHealth(
        provider_id=provider_id,
        kind=ProviderKind.API,
        state=HealthState.NOT_FOUND,
        detail="Recognised, but the adapter has not been implemented yet.",
        remediation="Use OpenRouter, which already reaches this model",
        adapter_ready=False,
    )


def build_registry(config: RevaiConfig, credentials: Credentials) -> ProviderRegistry:
    return ProviderRegistry(config, credentials)
