"""Phase 10 native-provider contracts, with zero paid network calls."""

from __future__ import annotations

import json

import httpx
import pytest

from revai.domain.enums import ProviderId
from revai.domain.models import Credentials, ProviderCredential, RevaiConfig
from revai.pipeline.ai import preflight_ai_stage, run_ai_stage
from revai.pipeline.deterministic import CodeChunk
from revai.providers.api import (
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
)
from revai.providers.base import AnalysisRequest, HealthState
from revai.providers.registry import build_registry


def _sse(*events: dict) -> str:
    return "\n".join(f"data: {json.dumps(event, separators=(',', ':'))}" for event in events)


def _ndjson(*events: dict) -> str:
    return "\n".join(json.dumps(event, separators=(",", ":")) for event in events)


@pytest.mark.parametrize(
    "provider",
    [AnthropicProvider(None), OpenAIProvider(None), GeminiProvider(None)],
)
async def test_keyed_provider_health_requires_a_key_without_a_request(
    provider, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args, **kwargs):  # pragma: no cover - must never be called
        raise AssertionError("health must not call out without a key")

    monkeypatch.setattr(httpx.AsyncClient, "get", fail)

    health = await provider.health()

    assert health.state is HealthState.NEEDS_AUTH
    assert health.adapter_ready is True
    assert health.remediation


@pytest.mark.parametrize(
    ("provider", "expected_path", "expected_header"),
    [
        (AnthropicProvider("secret"), "/v1/models", "x-api-key"),
        (OpenAIProvider("secret"), "/v1/models", "authorization"),
        (GeminiProvider("secret"), "/v1beta/models", "x-goog-api-key"),
        (OllamaProvider(), "/api/version", None),
    ],
)
async def test_health_uses_a_zero_token_endpoint(
    provider, expected_path: str, expected_header: str | None, monkeypatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == expected_path
        if expected_header:
            assert "secret" in request.headers[expected_header].lower()
        return httpx.Response(200, json={"version": "0.11"})

    _patch_transport(monkeypatch, handler)

    health = await provider.health()

    assert health.state is HealthState.READY


async def test_gemini_classifies_its_http_400_invalid_key_as_needs_auth(monkeypatch) -> None:
    _patch_transport(
        monkeypatch,
        lambda _: httpx.Response(
            400, json={"error": {"status": "INVALID_ARGUMENT", "message": "API key invalid"}}
        ),
    )

    health = await GeminiProvider("secret").health()

    assert health.state is HealthState.NEEDS_AUTH
    assert health.remediation


async def test_anthropic_request_and_stream_contract(monkeypatch) -> None:
    captured: dict = {}
    body = _sse(
        {
            "type": "message_start",
            "message": {
                "id": "msg_1",
                "usage": {"input_tokens": 12, "cache_read_input_tokens": 5},
            },
        },
        {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": '{"findings":'},
        },
        {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "[]}"},
        },
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 4},
        },
        {"type": "message_stop"},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "secret"
        return httpx.Response(200, text=body)

    _patch_transport(monkeypatch, handler)
    events = await _collect(AnthropicProvider("secret"), _request())

    finished = events[-1]
    assert finished.type == "finished"
    assert finished.text == '{"findings":[]}'
    assert finished.session_id == "msg_1"
    assert finished.usage.input_tokens == 12
    assert finished.usage.output_tokens == 4
    assert finished.usage.cached_tokens == 5
    assert captured["system"] == "Review safely"
    assert captured["output_config"]["format"]["type"] == "json_schema"
    assert "temperature" not in captured


async def test_openai_responses_request_and_stream_contract(monkeypatch) -> None:
    captured: dict = {}
    body = _sse(
        {"type": "response.created", "response": {"id": "resp_1"}},
        {"type": "response.output_text.delta", "delta": '{"findings":'},
        {"type": "response.output_text.delta", "delta": "[]}"},
        {
            "type": "response.completed",
            "response": {
                "id": "resp_1",
                "usage": {
                    "input_tokens": 15,
                    "output_tokens": 4,
                    "input_tokens_details": {"cached_tokens": 6},
                },
            },
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.url.path == "/v1/responses"
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(200, text=body)

    _patch_transport(monkeypatch, handler)
    events = await _collect(OpenAIProvider("secret"), _request())

    finished = events[-1]
    assert finished.type == "finished"
    assert finished.text == '{"findings":[]}'
    assert finished.session_id == "resp_1"
    assert finished.usage.input_tokens == 15
    assert finished.usage.cached_tokens == 6
    assert captured["instructions"] == "Review safely"
    assert captured["text"]["format"]["strict"] is True
    assert captured["store"] is False
    assert "temperature" not in captured


async def test_openai_refusal_is_a_non_retryable_failure(monkeypatch) -> None:
    body = _sse({"type": "response.refusal.delta", "delta": "Cannot comply"})
    _patch_transport(monkeypatch, lambda _: httpx.Response(200, text=body))

    events = await _collect(OpenAIProvider("secret"), _request())

    assert events[-1].type == "failed"
    assert events[-1].retryable is False


async def test_gemini_request_and_stream_contract(monkeypatch) -> None:
    captured: dict = {}
    body = _sse(
        {"candidates": [{"content": {"parts": [{"text": '{"findings":'}]}}]},
        {
            "candidates": [{"content": {"parts": [{"text": "[]}"}]}, "finishReason": "STOP"}],
            "usageMetadata": {
                "promptTokenCount": 18,
                "candidatesTokenCount": 4,
                "cachedContentTokenCount": 7,
            },
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.url.path.endswith("/models/gemini-test:streamGenerateContent")
        assert request.url.params["alt"] == "sse"
        assert request.headers["x-goog-api-key"] == "secret"
        return httpx.Response(200, text=body)

    _patch_transport(monkeypatch, handler)
    events = await _collect(GeminiProvider("secret"), _request())

    finished = events[-1]
    assert finished.type == "finished"
    assert finished.text == '{"findings":[]}'
    assert finished.usage.input_tokens == 18
    assert finished.usage.cached_tokens == 7
    assert captured["systemInstruction"]["parts"][0]["text"] == "Review safely"
    assert captured["generationConfig"]["responseMimeType"] == "application/json"
    assert "temperature" not in captured["generationConfig"]


async def test_ollama_request_and_stream_contract(monkeypatch) -> None:
    captured: dict = {}
    body = _ndjson(
        {"message": {"role": "assistant", "content": '{"findings":'}, "done": False},
        {"message": {"role": "assistant", "content": "[]}"}, "done": False},
        {
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 21,
            "eval_count": 4,
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.url.path == "/api/chat"
        assert "authorization" not in request.headers
        return httpx.Response(200, text=body)

    _patch_transport(monkeypatch, handler)
    events = await _collect(OllamaProvider(), _request())

    finished = events[-1]
    assert finished.type == "finished"
    assert finished.text == '{"findings":[]}'
    assert finished.usage.input_tokens == 21
    assert finished.usage.cost_usd == 0.0
    assert captured["messages"][0]["role"] == "system"
    assert captured["format"]["type"] == "object"


@pytest.mark.parametrize(
    "provider",
    [AnthropicProvider("secret"), OpenAIProvider("secret"), GeminiProvider("secret")],
)
async def test_rate_limits_are_retryable_and_secrets_are_redacted(provider, monkeypatch) -> None:
    _patch_transport(
        monkeypatch,
        lambda _: httpx.Response(429, json={"error": {"message": "retry secret later"}}),
    )

    events = await _collect(provider, _request())

    assert events[-1].type == "failed"
    assert events[-1].retryable is True
    assert "secret" not in events[-1].message
    assert "[redacted]" in events[-1].message


def test_registry_resolves_every_native_adapter_and_isolates_custom_url() -> None:
    config = RevaiConfig()
    config.engine.provider_id = ProviderId.OPENAI
    config.engine.base_url = "http://openai-proxy.test/v1"
    credentials = Credentials()
    for provider_id in (ProviderId.ANTHROPIC, ProviderId.OPENAI, ProviderId.GEMINI):
        credentials.put(ProviderCredential(provider_id=provider_id, api_key="secret"))

    registry = build_registry(config, credentials)

    assert isinstance(registry.get(ProviderId.ANTHROPIC), AnthropicProvider)
    assert isinstance(registry.get(ProviderId.OPENAI), OpenAIProvider)
    assert isinstance(registry.get(ProviderId.GEMINI), GeminiProvider)
    assert isinstance(registry.get(ProviderId.OLLAMA), OllamaProvider)
    assert registry.get(ProviderId.OPENAI)._base_url == "http://openai-proxy.test/v1"
    assert registry.get(ProviderId.ANTHROPIC)._base_url.startswith("https://")


def test_ollama_spend_preflight_remains_free() -> None:
    config = RevaiConfig()
    config.engine.provider_id = ProviderId.OLLAMA
    config.budget.warn_above_usd = 0
    config.budget.max_spend_usd = 0.000001
    config.budget.max_context_tokens = None

    preflight_ai_stage(config, [_chunk(tokens=1_000_000)])


def test_gemini_does_not_mix_thought_summaries_into_structured_json() -> None:
    from revai.providers.api.gemini import _candidate_text

    candidate = {
        "content": {
            "parts": [
                {"text": "internal reasoning", "thought": True},
                {"text": '{"findings":[]}'},
            ]
        }
    }

    assert _candidate_text(candidate) == ['{"findings":[]}']


@pytest.mark.parametrize(
    ("provider_id", "provider", "body"),
    [
        (
            ProviderId.ANTHROPIC,
            AnthropicProvider("secret"),
            _sse(
                {"type": "content_block_delta", "delta": {"text": '{"findings":[]}'}},
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn"},
                    "usage": {"output_tokens": 4},
                },
            ),
        ),
        (
            ProviderId.OPENAI,
            OpenAIProvider("secret"),
            _sse(
                {"type": "response.output_text.delta", "delta": '{"findings":[]}'},
                {
                    "type": "response.completed",
                    "response": {"usage": {"input_tokens": 8, "output_tokens": 4}},
                },
            ),
        ),
        (
            ProviderId.GEMINI,
            GeminiProvider("secret"),
            _sse(
                {
                    "candidates": [
                        {
                            "content": {"parts": [{"text": '{"findings":[]}'}]},
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 4},
                }
            ),
        ),
        (
            ProviderId.OLLAMA,
            OllamaProvider(),
            _ndjson(
                {"message": {"content": '{"findings":[]}'}, "done": False},
                {
                    "message": {"content": ""},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 8,
                    "eval_count": 4,
                },
            ),
        ),
    ],
)
async def test_all_native_adapters_complete_the_same_review_flow(
    provider_id: ProviderId, provider, body: str, monkeypatch
) -> None:
    _patch_transport(monkeypatch, lambda _: httpx.Response(200, text=body))
    config = RevaiConfig()
    config.engine.provider_id = provider_id
    config.engine.model = "test-model"

    result = await run_ai_stage(provider, config, [_chunk()])

    assert result.findings == []
    assert result.response_text == '{"findings":[]}'
    assert result.usage.output_tokens == 4


def _request() -> AnalysisRequest:
    return AnalysisRequest(
        model="gemini-test",
        system_prompt="Review safely",
        user_prompt="Review this diff",
        max_output_tokens=512,
        json_schema={"type": "object", "properties": {"findings": {"type": "array"}}},
    )


def _chunk(tokens: int = 12) -> CodeChunk:
    return CodeChunk(
        path="src/example.py",
        symbol="example",
        line_start=1,
        line_end=1,
        content="value = 1",
        estimated_tokens=tokens,
    )


def _patch_transport(monkeypatch, handler) -> None:
    original = httpx.AsyncClient.__init__

    def patched(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)


async def _collect(provider, request: AnalysisRequest) -> list:
    return [event async for event in provider.analyze(request)]
