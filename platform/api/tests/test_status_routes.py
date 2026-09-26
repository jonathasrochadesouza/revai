"""HTTP contract for the aggregated status endpoint.

The recurring assertions: an unhealthy component never fails the request, the
expensive provider sweep is not repeated inside the TTL, and the AI verdict follows
the *configured* provider rather than "anything that happens to work".
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from revai.config import Settings
from revai.connection import AiVerdict, classify_ai
from revai.domain.enums import ProviderId, ProviderKind
from revai.providers.base import HealthState, ProviderHealth
from revai.providers.registry import ProviderRegistry


@pytest.fixture(autouse=True)
def _no_real_probing(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Replace the whole provider sweep with a counted fake.

    Spawning real CLIs would make the suite slow and machine-dependent; counting the
    calls is also what proves the cache works.
    """
    calls: list[int] = []

    async def fake_health_all(self: ProviderRegistry) -> list[ProviderHealth]:
        calls.append(1)
        return _sweep()

    monkeypatch.setattr(ProviderRegistry, "health_all", fake_health_all)
    return calls


def _health(
    provider_id: ProviderId,
    state: HealthState,
    *,
    adapter_ready: bool = True,
    kind: ProviderKind = ProviderKind.API,
) -> ProviderHealth:
    return ProviderHealth(
        provider_id=provider_id,
        kind=kind,
        state=state,
        detail="fake probe",
        remediation="do the thing",
        adapter_ready=adapter_ready,
    )


def _sweep() -> list[ProviderHealth]:
    """A representative sweep: the configured provider unauthenticated, Ollama ready."""
    return [
        _health(ProviderId.OPENROUTER, HealthState.NEEDS_AUTH),
        _health(ProviderId.ANTHROPIC, HealthState.NEEDS_AUTH),
        _health(ProviderId.OPENAI, HealthState.NEEDS_AUTH),
        _health(ProviderId.GEMINI, HealthState.NEEDS_AUTH),
        _health(ProviderId.OLLAMA, HealthState.READY),
        _health(ProviderId.CLAUDE_CODE, HealthState.NOT_FOUND, kind=ProviderKind.CLI),
        _health(ProviderId.COPILOT_CLI, HealthState.UNKNOWN, kind=ProviderKind.CLI),
        _health(ProviderId.KIRO_CLI, HealthState.NEEDS_AUTH, kind=ProviderKind.CLI),
        _health(ProviderId.OPENCODE_CLI, HealthState.NOT_FOUND, kind=ProviderKind.CLI),
    ]


# --- endpoint shape --------------------------------------------------------


def test_one_response_carries_every_section(client: TestClient) -> None:
    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()

    assert body["api"]["status"] == "ok"
    assert body["api"]["version"]
    assert body["api"]["environment"] == "test"

    ai = body["ai"]
    assert ai["active_provider_id"] == "openrouter"
    assert ai["active_state"] == "needs_auth"
    assert ai["active_usable"] is False
    assert ai["ready_provider_ids"] == ["ollama"]
    assert ai["unknown_provider_ids"] == ["copilot_cli"]
    assert ai["total"] == len(ProviderId)
    assert ai["verdict"] == "active_broken"

    assert body["checked_at"]
    assert body["ttl_s"] > 0


def test_unhealthy_components_do_not_fail_the_request(client: TestClient) -> None:
    """No provider authenticated is still a successful check."""
    body = client.get("/api/status").json()

    assert body["ai"]["active_usable"] is False


def test_malformed_config_yields_422_not_500(client: TestClient, settings: Settings) -> None:
    settings.config_file.write_text("engine: [broken\n", encoding="utf-8")

    response = client.get("/api/status")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_key"] == "storage.invalid_yaml"
    assert detail["params"]["filename"] == "config.yaml"


def test_openapi_documents_the_status_endpoint(client: TestClient) -> None:
    assert "/api/status" in client.get("/api/openapi.json").json()["paths"]


# --- caching ---------------------------------------------------------------


def test_two_calls_inside_the_ttl_probe_once(
    client: TestClient, _no_real_probing: list[int]
) -> None:
    first = client.get("/api/status").json()
    second = client.get("/api/status").json()

    assert len(_no_real_probing) == 1, "the second call must be served from the cache"
    assert first["from_cache"] is False
    assert second["from_cache"] is True
    assert second["checked_at"] == first["checked_at"]


def test_refresh_reprobes_with_a_newer_timestamp(
    client: TestClient, _no_real_probing: list[int]
) -> None:
    first = client.get("/api/status").json()
    refreshed = client.get("/api/status?refresh=true").json()

    assert len(_no_real_probing) == 2
    assert refreshed["from_cache"] is False
    assert refreshed["checked_at"] >= first["checked_at"]


def test_expired_cache_is_replaced(client: TestClient, _no_real_probing: list[int]) -> None:
    client.get("/api/status")
    # Reach into the live service rather than sleeping 30 s.
    service = client.app.state.status_service
    service._ai.expires_at = 0.0

    body = client.get("/api/status").json()

    assert len(_no_real_probing) == 2
    assert body["from_cache"] is False


# --- verdict classification ------------------------------------------------


def test_verdict_ok_when_the_configured_provider_is_ready() -> None:
    sweep = [_health(ProviderId.ANTHROPIC, HealthState.READY)]

    section = classify_ai(sweep, ProviderId.ANTHROPIC)

    assert section.verdict is AiVerdict.OK
    assert section.active_usable is True


def test_verdict_active_broken_names_the_ready_alternative() -> None:
    sweep = [
        _health(ProviderId.ANTHROPIC, HealthState.NEEDS_AUTH),
        _health(ProviderId.OLLAMA, HealthState.READY),
    ]

    section = classify_ai(sweep, ProviderId.ANTHROPIC)

    assert section.verdict is AiVerdict.ACTIVE_BROKEN
    assert section.ready_provider_ids == [ProviderId.OLLAMA]
    assert section.active_remediation == "do the thing"


def test_verdict_none_ready_when_nothing_works() -> None:
    sweep = [
        _health(ProviderId.ANTHROPIC, HealthState.NEEDS_AUTH),
        _health(ProviderId.OPENAI, HealthState.NOT_FOUND),
    ]

    section = classify_ai(sweep, ProviderId.ANTHROPIC)

    assert section.verdict is AiVerdict.NONE_READY
    assert section.ready_provider_ids == []


def test_verdict_unknown_is_its_own_value() -> None:
    """Copilot CLI cannot report its auth state; that is not a claimed failure."""
    sweep = [
        _health(ProviderId.COPILOT_CLI, HealthState.UNKNOWN, kind=ProviderKind.CLI),
        _health(ProviderId.OLLAMA, HealthState.READY),
    ]

    section = classify_ai(sweep, ProviderId.COPILOT_CLI)

    assert section.verdict is AiVerdict.UNKNOWN
    assert section.unknown_provider_ids == [ProviderId.COPILOT_CLI]


def test_an_unimplemented_adapter_never_counts_as_ready() -> None:
    sweep = [
        _health(ProviderId.ANTHROPIC, HealthState.NEEDS_AUTH),
        _health(ProviderId.OPENAI, HealthState.READY, adapter_ready=False),
    ]

    section = classify_ai(sweep, ProviderId.ANTHROPIC)

    assert section.ready_provider_ids == []
    assert section.verdict is AiVerdict.NONE_READY


def test_a_missing_active_entry_is_reported_as_error_not_usable() -> None:
    section = classify_ai([_health(ProviderId.OLLAMA, HealthState.READY)], ProviderId.ANTHROPIC)

    assert section.active_state is HealthState.ERROR
    assert section.active_usable is False
    assert section.verdict is AiVerdict.ACTIVE_BROKEN


# --- no interface copy in the payload --------------------------------------


def test_response_carries_enumerated_states_not_sentences(client: TestClient) -> None:
    """Every user-facing sentence is composed in the web catalog, where the locale is
    known. The only free text allowed through is the provider's own detail and
    remediation, which the UI renders verbatim as technical output."""
    body = client.get("/api/status").json()

    assert body["ai"]["verdict"] in {v.value for v in AiVerdict}
    assert body["ai"]["active_state"] in {s.value for s in HealthState}

    free_text = {
        key: value
        for key, value in body["ai"].items()
        if isinstance(value, str) and key not in {"active_provider_id", "active_state", "verdict"}
    }
    assert set(free_text) <= {"active_detail", "active_remediation"}


def test_a_secret_never_appears_in_a_status_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "sk-or-v1-0123456789abcdefghijklmnop"
    client.put("/api/credentials", json={"provider_id": "openrouter", "api_key": secret})

    assert secret not in client.get("/api/status?refresh=true").text
