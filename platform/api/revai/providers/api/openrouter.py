"""OpenRouter adapter.

Chosen as the first provider because one key reaches hundreds of models through an
**OpenAI-compatible** surface, and because it returns real cost per request — which
feeds the budget guard without RevAI maintaining a price table.

Two endpoints are used:

* ``GET  /api/v1/key``          — health. Validates the key and returns the credit
  limit without consuming any tokens.
* ``POST /api/v1/chat/completions`` — analysis, streamed as SSE.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from revai.domain.enums import ProviderId, ProviderKind
from revai.providers.base import (
    AnalysisRequest,
    DeltaEvent,
    FailedEvent,
    FinishedEvent,
    HealthState,
    ProviderEvent,
    ProviderHealth,
    StartedEvent,
    UsageStats,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

# Short: this only validates a key, and a slow answer should not stall the settings
# page. The analysis call gets the user's configured timeout instead.
HEALTH_TIMEOUT_S = 10.0

# Sent so usage appears attributed in the OpenRouter dashboard. Both are optional
# in their API but recommended, and neither identifies the user.
_ATTRIBUTION = {
    "HTTP-Referer": "https://github.com/senior-labs/revai",
    "X-Title": "RevAI",
}


class OpenRouterProvider:
    """Implements :class:`~revai.providers.base.Provider` for OpenRouter."""

    provider_id = ProviderId.OPENROUTER
    kind = ProviderKind.API

    def __init__(self, api_key: str | None, base_url: str | None = None) -> None:
        self._api_key = (api_key or "").strip()
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

    # -- health -------------------------------------------------------------

    async def health(self) -> ProviderHealth:
        """Validate the key without spending anything.

        Never raises: the settings panel has to render every provider, including the
        ones that are broken.
        """
        if not self._api_key:
            return self._unhealthy(
                HealthState.NEEDS_AUTH,
                "No API key stored.",
                "Add an OpenRouter key in Settings > Engine",
            )

        try:
            async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT_S) as client:
                response = await client.get(f"{self._base_url}/key", headers=self._headers())
        except httpx.TimeoutException:
            return self._unhealthy(
                HealthState.ERROR,
                f"OpenRouter did not respond within {HEALTH_TIMEOUT_S:g}s.",
                "Check your network connection",
            )
        except httpx.HTTPError as exc:
            return self._unhealthy(
                HealthState.ERROR,
                f"Could not reach {self._base_url}: {exc}",
                "Check the base URL and your network connection",
            )

        if response.status_code in (401, 403):
            return self._unhealthy(
                HealthState.NEEDS_AUTH,
                "OpenRouter rejected the key.",
                "Check the key at openrouter.ai/keys",
            )
        if response.status_code != 200:
            return self._unhealthy(
                HealthState.ERROR,
                f"OpenRouter returned HTTP {response.status_code}.",
            )

        return ProviderHealth(
            provider_id=self.provider_id,
            kind=self.kind,
            state=HealthState.READY,
            detail=_describe_key(response),
            adapter_ready=True,
        )

    def _unhealthy(
        self, state: HealthState, detail: str, remediation: str | None = None
    ) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            kind=self.kind,
            state=state,
            detail=detail,
            remediation=remediation,
            adapter_ready=True,
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", **_ATTRIBUTION}

    # -- analysis -----------------------------------------------------------

    async def analyze(self, request: AnalysisRequest) -> AsyncIterator[ProviderEvent]:
        """Stream one completion.

        Yields ``FailedEvent`` rather than raising, so a caller consuming the stream
        handles success and failure through the same path.
        """
        if not self._api_key:
            yield FailedEvent(message="No OpenRouter API key stored.", retryable=False)
            return

        payload: dict = {
            "model": request.model,
            "messages": _messages(request),
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "stream": True,
            # Ask OpenRouter to include token counts and cost in the final chunk.
            "usage": {"include": True},
        }
        if request.json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "revai_findings",
                    "strict": True,
                    "schema": request.json_schema,
                },
            }

        yield StartedEvent(model=request.model)

        collected: list[str] = []
        usage: UsageStats | None = None

        try:
            async with (
                httpx.AsyncClient(timeout=request.timeout_s) as client,
                client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as response,
            ):
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    yield FailedEvent(
                        message=_describe_error(response.status_code, body),
                        # 429 and 5xx are worth retrying; 4xx generally is not.
                        retryable=response.status_code == 429 or response.status_code >= 500,
                    )
                    return

                async for line in response.aiter_lines():
                    event = _parse_sse_line(line)
                    if event is None:
                        continue
                    if event == _DONE:
                        break

                    delta = _extract_delta(event)
                    if delta:
                        collected.append(delta)
                        yield DeltaEvent(text=delta)

                    if (reported := _extract_usage(event)) is not None:
                        usage = reported

        except httpx.TimeoutException:
            yield FailedEvent(
                message=f"OpenRouter did not respond within {request.timeout_s}s.",
                retryable=True,
            )
            return
        except httpx.HTTPError as exc:
            yield FailedEvent(message=f"Transport error: {exc}", retryable=True)
            return

        yield FinishedEvent(text="".join(collected), usage=usage)


# ===========================================================================
# Parsing
# ===========================================================================

_DONE = object()


def _messages(request: AnalysisRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.user_prompt})
    return messages


def _parse_sse_line(line: str) -> dict | object | None:
    """Decode one SSE line.

    Returns the parsed object, the ``_DONE`` sentinel, or ``None`` for lines that
    carry no payload — blank keep-alives and ``: OPENROUTER PROCESSING`` comments,
    which OpenRouter sends to hold the connection open.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith(":"):
        return None
    if not stripped.startswith("data:"):
        return None

    data = stripped[5:].strip()
    if data == "[DONE]":
        return _DONE
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        logger.debug("skipping unparseable SSE payload: %r", data[:120])
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_delta(event: dict) -> str | None:
    choices = event.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    delta = first.get("delta")
    if not isinstance(delta, dict):
        return None
    content = delta.get("content")
    return content if isinstance(content, str) and content else None


def _extract_usage(event: dict) -> UsageStats | None:
    """Read the usage block OpenRouter appends to the final chunk.

    ``cost`` is reported in USD. When absent we leave ``cost_usd`` as ``None``
    rather than inventing a zero — an unknown cost and a free request are different
    facts, and the UI says so.
    """
    usage = event.get("usage")
    if not isinstance(usage, dict):
        return None

    details = usage.get("prompt_tokens_details")
    cached = 0
    if isinstance(details, dict):
        value = details.get("cached_tokens")
        if isinstance(value, int):
            cached = value

    cost = usage.get("cost")
    return UsageStats(
        input_tokens=_as_int(usage.get("prompt_tokens")),
        output_tokens=_as_int(usage.get("completion_tokens")),
        cached_tokens=cached,
        cost_usd=float(cost) if isinstance(cost, int | float) else None,
        is_estimated=False,
    )


def _as_int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _describe_key(response: httpx.Response) -> str:
    """Summarise ``GET /key`` for the UI.

    Showing remaining credit is worth the parsing: "key valid" is far less useful
    than "key valid, $4.12 remaining" when a review is about to be paid for.
    """
    try:
        data = response.json().get("data", {})
    except (json.JSONDecodeError, ValueError):
        return "Key accepted."
    if not isinstance(data, dict):
        return "Key accepted."

    parts = ["Key accepted"]
    limit = data.get("limit")
    usage = data.get("usage")

    if limit is None and isinstance(usage, int | float):
        parts.append(f"unlimited credit, ${float(usage):.2f} used")
    elif isinstance(limit, int | float):
        remaining = float(limit) - float(usage if isinstance(usage, int | float) else 0)
        parts.append(f"${remaining:.2f} of ${float(limit):.2f} remaining")

    if data.get("is_free_tier"):
        parts.append("free tier")

    return ", ".join(parts) + "."


def _describe_error(status: int, body: str) -> str:
    """Surface OpenRouter's own message when it sends one."""
    try:
        parsed = json.loads(body)
        error = parsed.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return f"OpenRouter error {status}: {error['message']}"
        if isinstance(error, str):
            return f"OpenRouter error {status}: {error}"
    except (json.JSONDecodeError, AttributeError):
        pass
    return f"OpenRouter returned HTTP {status}."
