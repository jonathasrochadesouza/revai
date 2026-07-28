"""Hosted API providers.

OpenRouter is implemented first because it is OpenAI-compatible: the adapter written
here is also the base for OpenAI and most of the work for the others, which is why
native adapters were scheduled last. See docs/ARCHITECTURE.md §6.
"""

from revai.providers.api.openrouter import OpenRouterProvider

__all__ = ["OpenRouterProvider"]
