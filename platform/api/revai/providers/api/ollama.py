"""Native Ollama local chat adapter."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from revai.domain.enums import ProviderId, ProviderKind
from revai.providers.api.common import as_int, describe_error, is_retryable, probe_health
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

DEFAULT_BASE_URL = "http://127.0.0.1:11434"


class OllamaProvider:
    provider_id = ProviderId.OLLAMA
    kind = ProviderKind.API

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

    async def health(self) -> ProviderHealth:
        return await probe_health(
            provider_id=self.provider_id,
            label="Ollama",
            url=f"{self._base_url}/api/version",
            headers={},
            ready_detail="Local Ollama service is reachable.",
            auth_remediation=None,
        )

    async def analyze(self, request: AnalysisRequest) -> AsyncIterator[ProviderEvent]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt})
        payload: dict = {
            "model": request.model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_predict": request.max_output_tokens,
                "temperature": request.temperature,
            },
        }
        if request.json_schema is not None:
            payload["format"] = request.json_schema

        yield StartedEvent(model=request.model)
        collected: list[str] = []
        usage: UsageStats | None = None
        completed = False

        try:
            async with (
                httpx.AsyncClient(timeout=request.timeout_s) as client,
                client.stream(
                    "POST", f"{self._base_url}/api/chat", headers={}, json=payload
                ) as response,
            ):
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    yield FailedEvent(
                        message=describe_error("Ollama", response.status_code, body),
                        retryable=is_retryable(response.status_code),
                    )
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    if isinstance(event.get("error"), str):
                        yield FailedEvent(
                            message=describe_error("Ollama", 500, json.dumps(event)),
                            retryable=False,
                        )
                        return
                    message = event.get("message")
                    if isinstance(message, dict):
                        text = message.get("content")
                        if isinstance(text, str) and text:
                            collected.append(text)
                            yield DeltaEvent(text=text)
                    if event.get("done") is True:
                        completed = True
                        if event.get("done_reason") == "length":
                            yield FailedEvent(
                                message="Ollama reached its output token limit.", retryable=False
                            )
                            return
                        usage = UsageStats(
                            input_tokens=as_int(event.get("prompt_eval_count")),
                            output_tokens=as_int(event.get("eval_count")),
                            cached_tokens=0,
                            cost_usd=0.0,
                            is_estimated=False,
                        )

        except httpx.TimeoutException:
            yield FailedEvent(
                message=f"Ollama did not respond within {request.timeout_s}s.", retryable=True
            )
            return
        except httpx.HTTPError:
            yield FailedEvent(message="Ollama transport error.", retryable=True)
            return

        if not completed:
            yield FailedEvent(
                message="Ollama stream ended without a completed response.", retryable=True
            )
            return
        yield FinishedEvent(text="".join(collected), usage=usage)
