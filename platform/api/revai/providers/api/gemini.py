"""Native Google Gemini generate-content adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import quote

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

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider:
    provider_id = ProviderId.GEMINI
    kind = ProviderKind.API

    def __init__(self, api_key: str | None, base_url: str | None = None) -> None:
        self._api_key = (api_key or "").strip()
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "x-goog-api-key": self._api_key}

    async def health(self) -> ProviderHealth:
        if not self._api_key:
            return missing_key_health(
                self.provider_id, "Gemini", "Add a Gemini key in Settings > Engine"
            )
        return await probe_health(
            provider_id=self.provider_id,
            label="Gemini",
            url=f"{self._base_url}/models?pageSize=1",
            headers=self._headers(),
            ready_detail="API key accepted.",
            auth_remediation="Check the key in Google AI Studio",
            # Google reports API_KEY_INVALID as 400, unlike the 401 used by the
            # other hosted providers.
            auth_statuses=frozenset({400, 401, 403}),
        )

    async def analyze(self, request: AnalysisRequest) -> AsyncIterator[ProviderEvent]:
        if not self._api_key:
            yield FailedEvent(message="No Gemini API key stored.", retryable=False)
            return

        payload: dict = {
            "contents": [{"role": "user", "parts": [{"text": request.user_prompt}]}],
            "generationConfig": {"maxOutputTokens": request.max_output_tokens},
        }
        if request.system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": request.system_prompt}]}
        if request.json_schema is not None:
            payload["generationConfig"].update(
                {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": request.json_schema,
                }
            )

        yield StartedEvent(model=request.model)
        collected: list[str] = []
        usage: UsageStats | None = None
        finish_reason: str | None = None
        model = quote(request.model.removeprefix("models/"), safe="-._~")

        try:
            async with (
                httpx.AsyncClient(timeout=request.timeout_s) as client,
                client.stream(
                    "POST",
                    f"{self._base_url}/models/{model}:streamGenerateContent?alt=sse",
                    headers=self._headers(),
                    json=payload,
                ) as response,
            ):
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    yield FailedEvent(
                        message=describe_error(
                            "Gemini", response.status_code, body, secret=self._api_key
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
                    if isinstance(event.get("error"), dict):
                        yield FailedEvent(
                            message=_stream_error(event, self._api_key), retryable=True
                        )
                        return
                    block = event.get("promptFeedback")
                    if isinstance(block, dict) and block.get("blockReason"):
                        yield FailedEvent(
                            message=f"Gemini blocked the prompt ({block['blockReason']}).",
                            retryable=False,
                        )
                        return
                    candidates = event.get("candidates")
                    if isinstance(candidates, list) and candidates:
                        candidate = candidates[0]
                        if isinstance(candidate, dict):
                            finish_reason = _text(candidate.get("finishReason")) or finish_reason
                            for text in _candidate_text(candidate):
                                collected.append(text)
                                yield DeltaEvent(text=text)
                    reported = _usage(event.get("usageMetadata"))
                    if reported is not None:
                        usage = reported

        except httpx.TimeoutException:
            yield FailedEvent(
                message=f"Gemini did not respond within {request.timeout_s}s.", retryable=True
            )
            return
        except httpx.HTTPError:
            yield FailedEvent(message="Gemini transport error.", retryable=True)
            return

        if finish_reason and finish_reason not in {"STOP", "FINISH_REASON_UNSPECIFIED"}:
            yield FailedEvent(
                message=f"Gemini stopped before a complete response ({finish_reason}).",
                retryable=False,
            )
            return
        yield FinishedEvent(text="".join(collected), usage=usage)


def _candidate_text(candidate: dict) -> list[str]:
    content = candidate.get("content")
    if not isinstance(content, dict) or not isinstance(content.get("parts"), list):
        return []
    return [
        part["text"]
        for part in content["parts"]
        if (
            isinstance(part, dict)
            and part.get("thought") is not True
            and isinstance(part.get("text"), str)
            and part["text"]
        )
    ]


def _usage(raw: object) -> UsageStats | None:
    if not isinstance(raw, dict):
        return None
    return UsageStats(
        input_tokens=as_int(raw.get("promptTokenCount")),
        output_tokens=as_int(raw.get("candidatesTokenCount")),
        cached_tokens=as_int(raw.get("cachedContentTokenCount")),
        cost_usd=None,
        is_estimated=False,
    )


def _stream_error(event: dict, secret: str) -> str:
    import json

    return describe_error("Gemini", 500, json.dumps(event), secret=secret)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
