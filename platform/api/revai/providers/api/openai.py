"""Native OpenAI Responses API adapter."""

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

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider:
    provider_id = ProviderId.OPENAI
    kind = ProviderKind.API

    def __init__(self, api_key: str | None, base_url: str | None = None) -> None:
        self._api_key = (api_key or "").strip()
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def health(self) -> ProviderHealth:
        if not self._api_key:
            return missing_key_health(
                self.provider_id, "OpenAI", "Add an OpenAI key in Settings > Engine"
            )
        return await probe_health(
            provider_id=self.provider_id,
            label="OpenAI",
            url=f"{self._base_url}/models",
            headers=self._headers(),
            ready_detail="API key accepted.",
            auth_remediation="Check the key in the OpenAI Platform",
        )

    async def analyze(self, request: AnalysisRequest) -> AsyncIterator[ProviderEvent]:
        if not self._api_key:
            yield FailedEvent(message="No OpenAI API key stored.", retryable=False)
            return

        payload: dict = {
            "model": request.model,
            "input": request.user_prompt,
            "max_output_tokens": request.max_output_tokens,
            "store": False,
            "stream": True,
        }
        if request.system_prompt:
            payload["instructions"] = request.system_prompt
        if request.json_schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "revai_findings",
                    "strict": True,
                    "schema": request.json_schema,
                }
            }

        yield StartedEvent(model=request.model)
        collected: list[str] = []
        usage: UsageStats | None = None
        session_id: str | None = None
        completed = False

        try:
            async with (
                httpx.AsyncClient(timeout=request.timeout_s) as client,
                client.stream(
                    "POST",
                    f"{self._base_url}/responses",
                    headers=self._headers(),
                    json=payload,
                ) as response,
            ):
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    yield FailedEvent(
                        message=describe_error(
                            "OpenAI", response.status_code, body, secret=self._api_key
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
                    if event_type in {"error", "response.failed", "response.incomplete"}:
                        yield FailedEvent(
                            message=_stream_error(event, self._api_key),
                            retryable=event_type != "response.incomplete",
                        )
                        return
                    if event_type in {"response.refusal.delta", "response.refusal.done"}:
                        yield FailedEvent(
                            message="OpenAI refused the requested review.", retryable=False
                        )
                        return
                    if event_type == "response.created":
                        response_data = event.get("response")
                        if isinstance(response_data, dict):
                            session_id = _text(response_data.get("id"))
                    elif event_type == "response.output_text.delta":
                        text = _text(event.get("delta"))
                        if text:
                            collected.append(text)
                            yield DeltaEvent(text=text)
                    elif event_type == "response.completed":
                        completed = True
                        response_data = event.get("response")
                        if isinstance(response_data, dict):
                            session_id = _text(response_data.get("id")) or session_id
                            usage = _usage(response_data.get("usage"))

        except httpx.TimeoutException:
            yield FailedEvent(
                message=f"OpenAI did not respond within {request.timeout_s}s.", retryable=True
            )
            return
        except httpx.HTTPError:
            yield FailedEvent(message="OpenAI transport error.", retryable=True)
            return

        if not completed:
            yield FailedEvent(
                message="OpenAI stream ended without a completed response.", retryable=True
            )
            return
        yield FinishedEvent(text="".join(collected), usage=usage, session_id=session_id)


def _usage(raw: object) -> UsageStats | None:
    if not isinstance(raw, dict):
        return None
    details = raw.get("input_tokens_details")
    cached = as_int(details.get("cached_tokens")) if isinstance(details, dict) else 0
    return UsageStats(
        input_tokens=as_int(raw.get("input_tokens")),
        output_tokens=as_int(raw.get("output_tokens")),
        cached_tokens=cached,
        cost_usd=None,
        is_estimated=False,
    )


def _stream_error(event: dict, secret: str) -> str:
    import json

    return describe_error("OpenAI", 500, json.dumps(event), secret=secret)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
