"""OpenRouter adapter tests.

Driven entirely through a mocked transport, so the suite never needs a real key and
never spends money. The SSE parsing tests use payload shapes taken from OpenRouter's
documented format, including the keep-alive comments that would otherwise break a
naive line parser.
"""

from __future__ import annotations

import httpx
import pytest

from revai.domain.enums import ProviderId, ProviderKind
from revai.providers.api.openrouter import (
    OpenRouterProvider,
    _describe_error,
    _describe_key,
    _extract_delta,
    _extract_usage,
    _parse_sse_line,
)
from revai.providers.base import AnalysisRequest, HealthState

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


async def test_health_without_a_key_asks_for_one() -> None:
    """No key is a configuration state, not an error — and no request is made."""
    health = await OpenRouterProvider(api_key=None).health()

    assert health.state is HealthState.NEEDS_AUTH
    assert health.provider_id is ProviderId.OPENROUTER
    assert health.kind is ProviderKind.API
    assert health.adapter_ready is True


async def test_health_treats_whitespace_as_no_key() -> None:
    health = await OpenRouterProvider(api_key="   ").health()

    assert health.state is HealthState.NEEDS_AUTH


async def test_health_reports_ready_and_remaining_credit(monkeypatch) -> None:
    """Showing the balance matters more than "key valid" when money is about to be spent."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer sk-or-test"
        return httpx.Response(
            200, json={"data": {"limit": 10.0, "usage": 5.88, "is_free_tier": False}}
        )

    _patch_transport(monkeypatch, handler)

    health = await OpenRouterProvider(api_key="sk-or-test").health()

    assert health.state is HealthState.READY
    assert health.detail is not None
    assert "$4.12" in health.detail


async def test_health_reports_a_rejected_key(monkeypatch) -> None:
    _patch_transport(monkeypatch, lambda _: httpx.Response(401, json={"error": "bad key"}))

    health = await OpenRouterProvider(api_key="sk-or-wrong").health()

    assert health.state is HealthState.NEEDS_AUTH
    assert health.remediation is not None


async def test_health_reports_a_server_error(monkeypatch) -> None:
    _patch_transport(monkeypatch, lambda _: httpx.Response(503, text="unavailable"))

    health = await OpenRouterProvider(api_key="sk-or-test").health()

    assert health.state is HealthState.ERROR


async def test_health_reports_a_timeout_without_raising(monkeypatch) -> None:
    """The settings page must render even when the network is down."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow", request=request)

    _patch_transport(monkeypatch, handler)

    health = await OpenRouterProvider(api_key="sk-or-test").health()

    assert health.state is HealthState.ERROR
    assert health.detail is not None


async def test_health_reports_an_unreachable_host(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=request)

    _patch_transport(monkeypatch, handler)

    health = await OpenRouterProvider(api_key="sk", base_url="https://nope.invalid/v1").health()

    assert health.state is HealthState.ERROR


# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------


def test_keep_alive_comments_are_skipped() -> None:
    """OpenRouter sends `: OPENROUTER PROCESSING` to hold the connection open.

    A parser that treated these as payloads would fail on every long request.
    """
    assert _parse_sse_line(": OPENROUTER PROCESSING") is None
    assert _parse_sse_line("") is None
    assert _parse_sse_line("   ") is None


def test_done_is_recognised() -> None:
    from revai.providers.api.openrouter import _DONE

    assert _parse_sse_line("data: [DONE]") is _DONE


def test_unparseable_payloads_are_skipped_not_fatal() -> None:
    """One malformed chunk must not abort a stream that is otherwise fine."""
    assert _parse_sse_line("data: {not json") is None


def test_a_valid_chunk_is_parsed() -> None:
    parsed = _parse_sse_line('data: {"choices":[{"delta":{"content":"hi"}}]}')

    assert isinstance(parsed, dict)
    assert _extract_delta(parsed) == "hi"


def test_extract_delta_tolerates_missing_pieces() -> None:
    assert _extract_delta({}) is None
    assert _extract_delta({"choices": []}) is None
    assert _extract_delta({"choices": [{}]}) is None
    assert _extract_delta({"choices": [{"delta": {}}]}) is None
    assert _extract_delta({"choices": [{"delta": {"content": ""}}]}) is None


def test_usage_is_extracted_with_real_cost() -> None:
    usage = _extract_usage(
        {
            "usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 340,
                "cost": 0.0187,
                "prompt_tokens_details": {"cached_tokens": 800},
            }
        }
    )

    assert usage is not None
    assert usage.input_tokens == 1200
    assert usage.output_tokens == 340
    assert usage.cached_tokens == 800
    assert usage.cost_usd == pytest.approx(0.0187)
    assert usage.is_estimated is False


def test_missing_cost_stays_none_rather_than_zero() -> None:
    """An unknown cost and a free request are different facts.

    Reporting 0.0 would let the budget guard under-count real spending.
    """
    usage = _extract_usage({"usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    assert usage is not None
    assert usage.cost_usd is None


def test_extract_usage_returns_none_when_absent() -> None:
    assert _extract_usage({"choices": []}) is None


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


async def test_analyze_streams_deltas_then_finishes(monkeypatch) -> None:
    body = (
        ": OPENROUTER PROCESSING\n"
        'data: {"choices":[{"delta":{"content":"Hello"}}]}\n'
        "\n"
        'data: {"choices":[{"delta":{"content":" world"}}]}\n'
        'data: {"usage":{"prompt_tokens":10,"completion_tokens":2,"cost":0.001}}\n'
        "data: [DONE]\n"
    )
    _patch_transport(monkeypatch, lambda _: httpx.Response(200, text=body))

    events = await _collect(
        OpenRouterProvider(api_key="sk-or-test"),
        AnalysisRequest(model="anthropic/claude-sonnet-4.5", user_prompt="hi"),
    )

    kinds = [event.type for event in events]
    assert kinds[0] == "started"
    assert kinds[-1] == "finished"

    finished = events[-1]
    assert finished.text == "Hello world"
    assert finished.usage is not None
    assert finished.usage.cost_usd == pytest.approx(0.001)


async def test_analyze_without_a_key_fails_without_calling_out(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be made without a key")

    _patch_transport(monkeypatch, handler)

    events = await _collect(
        OpenRouterProvider(api_key=None),
        AnalysisRequest(model="m", user_prompt="hi"),
    )

    assert len(events) == 1
    assert events[0].type == "failed"
    assert events[0].retryable is False


async def test_rate_limits_are_marked_retryable(monkeypatch) -> None:
    """429 and 5xx are worth retrying; a 4xx generally is not.

    This distinction is the seed of the failure taxonomy in
    docs/DEFERRED-FALLBACK-PROVIDER.md.
    """
    _patch_transport(
        monkeypatch,
        lambda _: httpx.Response(429, json={"error": {"message": "slow down"}}),
    )

    events = await _collect(
        OpenRouterProvider(api_key="sk"), AnalysisRequest(model="m", user_prompt="hi")
    )

    failed = events[-1]
    assert failed.type == "failed"
    assert failed.retryable is True
    assert "slow down" in failed.message


async def test_a_bad_request_is_not_retryable(monkeypatch) -> None:
    _patch_transport(
        monkeypatch,
        lambda _: httpx.Response(400, json={"error": {"message": "unknown model"}}),
    )

    events = await _collect(
        OpenRouterProvider(api_key="sk"), AnalysisRequest(model="nope", user_prompt="hi")
    )

    assert events[-1].retryable is False


async def test_a_server_error_is_retryable(monkeypatch) -> None:
    _patch_transport(monkeypatch, lambda _: httpx.Response(502, text="bad gateway"))

    events = await _collect(
        OpenRouterProvider(api_key="sk"), AnalysisRequest(model="m", user_prompt="hi")
    )

    assert events[-1].retryable is True


async def test_a_json_schema_request_asks_for_structured_output(monkeypatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.update(json.loads(request.content))
        return httpx.Response(200, text="data: [DONE]\n")

    _patch_transport(monkeypatch, handler)

    await _collect(
        OpenRouterProvider(api_key="sk"),
        AnalysisRequest(
            model="m",
            user_prompt="hi",
            json_schema={"type": "object", "properties": {}},
        ),
    )

    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True


async def test_a_system_prompt_is_sent_first(monkeypatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.update(json.loads(request.content))
        return httpx.Response(200, text="data: [DONE]\n")

    _patch_transport(monkeypatch, handler)

    await _collect(
        OpenRouterProvider(api_key="sk"),
        AnalysisRequest(model="m", system_prompt="be terse", user_prompt="hi"),
    )

    assert captured["messages"][0] == {"role": "system", "content": "be terse"}
    assert captured["messages"][1]["role"] == "user"


# ---------------------------------------------------------------------------
# Error descriptions
# ---------------------------------------------------------------------------


def test_provider_error_messages_are_surfaced_verbatim() -> None:
    """The provider's own wording is more useful than a generic status line."""
    message = _describe_error(400, '{"error":{"message":"model not found"}}')

    assert "model not found" in message


def test_error_description_falls_back_to_the_status_code() -> None:
    assert "503" in _describe_error(503, "<html>gateway</html>")


def test_key_description_handles_an_unlimited_key() -> None:
    response = httpx.Response(200, json={"data": {"limit": None, "usage": 1.5}})

    described = _describe_key(response)

    assert "unlimited" in described.lower()


def test_key_description_survives_an_unexpected_body() -> None:
    described = _describe_key(httpx.Response(200, text="not json"))

    assert described == "Key accepted."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_transport(monkeypatch, handler) -> None:
    """Route every httpx.AsyncClient through a mock transport.

    Patching the constructor default keeps the adapter untouched — it still builds
    its own clients exactly as it does in production.
    """
    original = httpx.AsyncClient.__init__

    def patched(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)


async def _collect(provider: OpenRouterProvider, request: AnalysisRequest) -> list:
    return [event async for event in provider.analyze(request)]
