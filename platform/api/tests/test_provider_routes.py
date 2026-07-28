"""HTTP contract for the provider endpoints.

The recurring assertion: probing must never fail the request. The Detected providers
panel has to render every engine, and an engine that is missing or broken is data to
show, not an error to propagate.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from revai.config import Settings
from revai.domain.enums import ProviderId, ProviderKind
from revai.providers.base import HealthState, ProviderHealth
from revai.providers.detection import CLI_SPECS


@pytest.fixture(autouse=True)
def _fake_cli_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace real CLI probing for every test in this module.

    Two reasons. Spawning three CLIs per request made this file alone take minutes —
    `copilot` is slow to start. And the results would depend on what happens to be
    installed on the machine running the suite, so the assertions could not be exact.

    The states here mirror what was actually measured on the development machine, so
    the fake is representative rather than convenient.
    """
    measured = {
        ProviderId.CLAUDE_CODE: (HealthState.NOT_FOUND, None, "install it"),
        ProviderId.COPILOT_CLI: (HealthState.UNKNOWN, "1.0.69", "copilot login"),
        ProviderId.KIRO_CLI: (HealthState.NEEDS_AUTH, "2.14.1", "kiro-cli login"),
    }

    async def fake_detect_all() -> list[ProviderHealth]:
        return [
            ProviderHealth(
                provider_id=spec.provider_id,
                kind=ProviderKind.CLI,
                state=measured[spec.provider_id][0],
                version=measured[spec.provider_id][1],
                detail="fake detection",
                remediation=measured[spec.provider_id][2],
                adapter_ready=False,
            )
            for spec in CLI_SPECS
        ]

    monkeypatch.setattr("revai.providers.registry.detect_all_clis", fake_detect_all)


def test_providers_lists_every_known_engine(client: TestClient) -> None:
    response = client.get("/api/providers")

    assert response.status_code == 200
    body = response.json()

    returned = {entry["provider_id"] for entry in body["providers"]}
    expected = {member.value for member in ProviderId}
    assert returned == expected, "every ProviderId must be reported, even unimplemented ones"


def test_providers_reports_the_active_engine(client: TestClient) -> None:
    body = client.get("/api/providers").json()

    assert body["active_provider_id"] == "openrouter"
    # No key is stored in the test fixture, so the active engine is not usable.
    assert body["active_is_usable"] is False


def test_every_provider_declares_its_kind(client: TestClient) -> None:
    for entry in client.get("/api/providers").json()["providers"]:
        assert entry["kind"] in {"api", "cli"}


def test_cli_providers_are_reported_but_not_adapter_ready(client: TestClient) -> None:
    """CLI detection ships in phase 2; the adapters land in phase 8."""
    providers = client.get("/api/providers").json()["providers"]
    clis = [entry for entry in providers if entry["kind"] == "cli"]

    assert len(clis) == 3
    for entry in clis:
        assert entry["adapter_ready"] is False


def test_openrouter_is_the_only_ready_adapter(client: TestClient) -> None:
    providers = client.get("/api/providers").json()["providers"]
    ready = [entry["provider_id"] for entry in providers if entry["adapter_ready"]]

    assert ready == ["openrouter"]


def test_planned_api_providers_are_listed_honestly(client: TestClient) -> None:
    """Listed rather than hidden, so the roadmap is visible in the product."""
    providers = client.get("/api/providers").json()["providers"]
    anthropic = next(e for e in providers if e["provider_id"] == "anthropic")

    assert anthropic["adapter_ready"] is False
    assert anthropic["detail"] is not None
    assert "not been implemented" in anthropic["detail"]


def test_unhealthy_providers_carry_remediation(client: TestClient) -> None:
    """A problem with no suggested fix is a dead end."""
    providers = client.get("/api/providers").json()["providers"]

    for entry in providers:
        if entry["state"] in {"needs_auth", "not_found"}:
            assert entry["remediation"], f"{entry['provider_id']} offers no way forward"


def test_verify_returns_200_even_for_a_broken_provider(client: TestClient) -> None:
    """ "I checked, and it is not working" is a successful check."""
    response = client.post("/api/providers/openrouter/verify")

    assert response.status_code == 200
    assert response.json()["state"] == "needs_auth"  # no key in the fixture


def test_verify_works_for_a_cli_provider(client: TestClient) -> None:
    response = client.post("/api/providers/kiro_cli/verify")

    assert response.status_code == 200
    assert response.json()["kind"] == "cli"


def test_verify_rejects_an_unknown_provider(client: TestClient) -> None:
    assert client.post("/api/providers/not-a-provider/verify").status_code == 422


def test_verify_reflects_a_stored_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Storing a key must change the probe's behaviour, proving it reads credentials.

    The outbound call is stubbed: hitting the real OpenRouter would make the suite
    depend on the network and on a valid key.
    """
    before = client.post("/api/providers/openrouter/verify").json()
    assert before["state"] == "needs_auth"
    assert before["detail"] == "No API key stored."

    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer sk-or-v1-fake"
        return httpx.Response(200, json={"data": {"limit": 5.0, "usage": 1.0}})

    original = httpx.AsyncClient.__init__

    def patched(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)

    client.put("/api/credentials", json={"provider_id": "openrouter", "api_key": "sk-or-v1-fake"})

    after = client.post("/api/providers/openrouter/verify").json()

    assert after["state"] == "ready"
    assert "$4.00" in after["detail"]


def test_a_secret_never_appears_in_a_provider_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The most important assertion in this file.

    A key leaked into a response body would end up in browser devtools, logs and
    screenshots.
    """
    import httpx

    original = httpx.AsyncClient.__init__

    def patched(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda _: httpx.Response(200, json={"data": {"limit": 1.0, "usage": 0.0}})
        )
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)

    secret = "sk-or-v1-0123456789abcdefghijklmnop"
    client.put("/api/credentials", json={"provider_id": "openrouter", "api_key": secret})

    assert secret not in client.get("/api/providers").text
    assert secret not in client.post("/api/providers/openrouter/verify").text


def test_malformed_config_yields_422_not_500(client: TestClient, settings: Settings) -> None:
    """The file is hand-editable, so a bad edit is a fixable user error."""
    settings.config_file.write_text("engine: [broken\n", encoding="utf-8")

    response = client.get("/api/providers")

    assert response.status_code == 422
    assert "config.yaml" in response.json()["detail"]


def test_openapi_documents_the_provider_endpoints(client: TestClient) -> None:
    """The frontend generates its types from this schema."""
    paths = client.get("/api/openapi.json").json()["paths"]

    assert "/api/providers" in paths
    assert "/api/providers/{provider_id}/verify" in paths
