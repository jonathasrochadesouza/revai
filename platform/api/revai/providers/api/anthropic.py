"""Native Anthropic Messages API adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from revai.domain.enums import ProviderId, ProviderKind
from revai.providers.api.common import (
    _DONE,
    as_int,
    describe_error,
    is_retryable,
    missing_key_health,
    parse_sse_line,
    probe_health,
)
from revai.providers.base import (
    AnalysisRequest,
    DeltaEvent,
    FailedEvent,
    FinishedEvent,
    ProviderEvent,
    ProviderHealth,
    StartedEvent,
    UsageStats,
)

DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
_VERSION = "2023-06-01"


class AnthropicProvider:
    provider_id = ProviderId.ANTHROPIC
    kind = ProviderKind.API

    def __init__(self, api_key: str | None, base_url: str | None = None) -> None:
        self._api_key = (api_key or "").strip()
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "anthropic-version": _VERSION,
            "content-type": "application/json",
            "x-api-key": self._api_key,
        }

    async def health(self) -> ProviderHealth:
        if not self._api_key:
            return missing_key_health(
                self.provider_id,
                "Anthropic",
                "Add an Anthropic key in Settings > Engine",
            )
        return await probe_health(
            provider_id=self.provider_id,
            label="Anthropic",
            url=f"{self._base_url}/models?limit=1",
            headers=self._headers(),
            ready_detail="API key accepted.",
            auth_remediation="Check the key in the Anthropic Console",
        )

    async def analyze(self, request: AnalysisRequest) -> AsyncIterator[ProviderEvent]:
        if not self._api_key:
            yield FailedEvent(message="No Anthropic API key stored.", retryable=False)
            return

        payload: dict = {
            "model": request.model,
            "max_tokens": request.max_output_tokens,
            "messages": [{"role": "user", "content": request.user_prompt}],
            "stream": True,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        if request.json_schema is not None:
            payload["output_config"] = {
                "format": {"type": "json_schema", "schema": request.json_schema}
            }

        yield StartedEvent(model=request.model)
        collected: list[str] = []
        usage = UsageStats()
        session_id: str | None = None
        stop_reason: str | None = None

        try:
            async with (
                httpx.AsyncClient(timeout=request.timeout_s) as client,
                client.stream(
                    "POST",
                    f"{self._base_url}/messages",
                    headers=self._headers(),
                    json=payload,
                ) as response,
            ):
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    yield FailedEvent(
                        message=describe_error(
                            "Anthropic", response.status_code, body, secret=self._api_key
                        ),
                        retryable=is_retryable(response.status_code),
                    )
                    return

                async for line in response.aiter_lines():
                    event = parse_sse_line(line)
                    if event is None:
                        continue
                    if event is _DONE:
                        break
                    event_type = event.get("type")
                    if event_type == "error":
                        yield FailedEvent(
                            message=_stream_error(event, self._api_key), retryable=True
                        )
                        return
                    if event_type == "message_start":
                        message = event.get("message")
                        if isinstance(message, dict):
                            session_id = _text(message.get("id"))
                            usage = _usage(message.get("usage"), usage)
                    elif event_type == "content_block_delta":
                        delta = event.get("delta")
                        text = _text(delta.get("text")) if isinstance(delta, dict) else None
                        if text:
                            collected.append(text)
                            yield DeltaEvent(text=text)
                    elif event_type == "message_delta":
                        delta = event.get("delta")
                        if isinstance(delta, dict):
                            stop_reason = _text(delta.get("stop_reason")) or stop_reason
                        usage = _usage(event.get("usage"), usage)

        except httpx.TimeoutException:
            yield FailedEvent(
                message=f"Anthropic did not respond within {request.timeout_s}s.",
                retryable=True,
            )
            return
        except httpx.HTTPError:
            yield FailedEvent(message="Anthropic transport error.", retryable=True)
            return

        if stop_reason in {"max_tokens", "refusal"}:
            yield FailedEvent(
                message=f"Anthropic stopped before a complete response ({stop_reason}).",
                retryable=False,
            )
            return
        yield FinishedEvent(text="".join(collected), usage=usage, session_id=session_id)


def _usage(raw: object, previous: UsageStats) -> UsageStats:
    if not isinstance(raw, dict):
        return previous
    return UsageStats(
        input_tokens=as_int(raw.get("input_tokens")) or previous.input_tokens,
        output_tokens=as_int(raw.get("output_tokens")) or previous.output_tokens,
        cached_tokens=as_int(raw.get("cache_read_input_tokens")) or previous.cached_tokens,
        cost_usd=None,
        is_estimated=False,
    )


def _stream_error(event: dict, secret: str) -> str:
    import json

    return describe_error("Anthropic", 500, json.dumps(event), secret=secret)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
