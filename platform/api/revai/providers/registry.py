"""Provider lookup.

The registry is the only place that knows which adapters exist, so adding one is a
single-line change here rather than an edit scattered across routes and pipeline
stages.
"""

from __future__ import annotations

import asyncio

from revai.domain.enums import ProviderId, ProviderKind
from revai.domain.models import Credentials, RevaiConfig
from revai.providers.api.anthropic import AnthropicProvider
from revai.providers.api.gemini import GeminiProvider
from revai.providers.api.ollama import OllamaProvider
from revai.providers.api.openai import OpenAIProvider
from revai.providers.api.openrouter import OpenRouterProvider
from revai.providers.base import Provider, ProviderHealth
from revai.providers.cli import (
    ClaudeCodeProvider,
    CopilotCliProvider,
    KiroCliProvider,
    OpencodeCliProvider,
)


class ProviderRegistry:
    """Resolves a provider id to a working adapter."""

    def __init__(self, config: RevaiConfig, credentials: Credentials) -> None:
        self._config = config
        self._credentials = credentials

    # -- lookup -------------------------------------------------------------

    def get(self, provider_id: ProviderId) -> Provider | None:
        """Return the adapter for a known provider."""
        if provider_id is ProviderId.OPENROUTER:
            credential = self._credentials.get(provider_id)
            return OpenRouterProvider(
                api_key=credential.api_key if credential else None,
                base_url=self._base_url_for(provider_id),
            )
        if provider_id is ProviderId.ANTHROPIC:
            credential = self._credentials.get(provider_id)
            return AnthropicProvider(
                api_key=credential.api_key if credential else None,
                base_url=self._base_url_for(provider_id),
            )
        if provider_id is ProviderId.OPENAI:
            credential = self._credentials.get(provider_id)
            return OpenAIProvider(
                api_key=credential.api_key if credential else None,
                base_url=self._base_url_for(provider_id),
            )
        if provider_id is ProviderId.GEMINI:
            credential = self._credentials.get(provider_id)
            return GeminiProvider(
                api_key=credential.api_key if credential else None,
                base_url=self._base_url_for(provider_id),
            )
        if provider_id is ProviderId.OLLAMA:
            return OllamaProvider(base_url=self._base_url_for(provider_id))
        if provider_id is ProviderId.CLAUDE_CODE:
            return ClaudeCodeProvider()
        if provider_id is ProviderId.COPILOT_CLI:
            return CopilotCliProvider()
        if provider_id is ProviderId.KIRO_CLI:
            return KiroCliProvider()
        if provider_id is ProviderId.OPENCODE_CLI:
            return OpencodeCliProvider()
        return None

    def _base_url_for(self, provider_id: ProviderId) -> str | None:
        """A custom URL belongs only to the active adapter that saved it."""
        if self._config.engine.provider_id is provider_id:
            return self._config.engine.base_url
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
        providers = [
            self.get(provider_id)
            for provider_id in (
                ProviderId.OPENROUTER,
                ProviderId.ANTHROPIC,
                ProviderId.OPENAI,
                ProviderId.GEMINI,
                ProviderId.OLLAMA,
                ProviderId.CLAUDE_CODE,
                ProviderId.COPILOT_CLI,
                ProviderId.KIRO_CLI,
                ProviderId.OPENCODE_CLI,
            )
        ]
        healths = await asyncio.gather(
            *(provider.health() for provider in providers if provider is not None)
        )
        api_healths = [health for health in healths if health.kind is ProviderKind.API]
        cli_healths = [health for health in healths if health.kind is ProviderKind.CLI]
        return [*api_healths, *cli_healths]


def build_registry(config: RevaiConfig, credentials: Credentials) -> ProviderRegistry:
    return ProviderRegistry(config, credentials)
