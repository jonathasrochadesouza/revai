"""HTTP contract for configuration and credentials.

The credential tests are the important ones: a leaked key in a response body would
end up in browser devtools, logs and screenshots.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from revai.config import Settings

SECRET = "sk-or-v1-0123456789abcdefghijklmnopqrstuv"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_get_config_returns_defaults_before_any_save(client: TestClient) -> None:
    response = client.get("/api/config")

    assert response.status_code == 200
    body = response.json()
    assert body["exists"] is False
    assert body["config"]["engine"]["provider_id"] == "openrouter"
    assert body["path"].endswith("config.yaml")


def test_put_config_writes_the_file(client: TestClient, settings: Settings) -> None:
    payload = client.get("/api/config").json()["config"]
    payload["budget"]["max_spend_usd"] = 1.25
    payload["engine"]["model"] = "openai/gpt-5.2"

    response = client.put("/api/config", json=payload)

    assert response.status_code == 200
    assert response.json()["exists"] is True
    assert settings.config_file.is_file()


def test_saved_config_is_returned_on_the_next_read(client: TestClient) -> None:
    """The acceptance criterion behind `Save to config.yaml`."""
    payload = client.get("/api/config").json()["config"]
    payload["ui"]["locale"] = "pt-BR"
    client.put("/api/config", json=payload)

    reread = client.get("/api/config").json()

    assert reread["config"]["ui"]["locale"] == "pt-BR"
    assert reread["exists"] is True


def test_put_config_stamps_updated_at_server_side(client: TestClient) -> None:
    """A client clock must not be able to write a misleading timestamp."""
    payload = client.get("/api/config").json()["config"]
    payload["updated_at"] = "2000-01-01T00:00:00+00:00"

    response = client.put("/api/config", json=payload)

    assert not response.json()["config"]["updated_at"].startswith("2000")


def test_put_config_rejects_an_invalid_budget(client: TestClient) -> None:
    payload = client.get("/api/config").json()["config"]
    payload["budget"]["max_spend_usd"] = -1

    assert client.put("/api/config", json=payload).status_code == 422


def test_put_config_rejects_a_warning_above_the_hard_cap(client: TestClient) -> None:
    """A threshold above the cap could never fire, so it is a configuration bug."""
    payload = client.get("/api/config").json()["config"]
    payload["budget"]["max_spend_usd"] = 0.10
    payload["budget"]["warn_above_usd"] = 5.00

    assert client.put("/api/config", json=payload).status_code == 422


def test_put_config_rejects_unknown_fields(client: TestClient) -> None:
    payload = client.get("/api/config").json()["config"]
    payload["totally_made_up"] = True

    assert client.put("/api/config", json=payload).status_code == 422


# ---------------------------------------------------------------------------
# Unlimited budgets
# ---------------------------------------------------------------------------


def test_spend_can_be_set_to_unlimited(client: TestClient) -> None:
    """`null` is the only value meaning unlimited — 0 and -1 stay invalid."""
    payload = client.get("/api/config").json()["config"]
    payload["budget"]["max_spend_usd"] = None

    response = client.put("/api/config", json=payload)

    assert response.status_code == 200
    assert response.json()["config"]["budget"]["max_spend_usd"] is None


def test_context_can_be_set_to_unlimited(client: TestClient) -> None:
    payload = client.get("/api/config").json()["config"]
    payload["budget"]["max_context_tokens"] = None

    response = client.put("/api/config", json=payload)

    assert response.status_code == 200
    assert response.json()["config"]["budget"]["max_context_tokens"] is None


def test_unlimited_survives_a_reload(client: TestClient) -> None:
    payload = client.get("/api/config").json()["config"]
    payload["budget"]["max_spend_usd"] = None
    client.put("/api/config", json=payload)

    reread = client.get("/api/config").json()

    assert reread["config"]["budget"]["max_spend_usd"] is None


def test_zero_is_still_rejected(client: TestClient) -> None:
    """Zero must not become a back-door 'unlimited' — that is what `null` is for."""
    payload = client.get("/api/config").json()["config"]
    payload["budget"]["max_spend_usd"] = 0

    assert client.put("/api/config", json=payload).status_code == 422


def test_warning_threshold_is_free_when_spend_is_unlimited(client: TestClient) -> None:
    """With no cap there is nothing for the threshold to exceed."""
    payload = client.get("/api/config").json()["config"]
    payload["budget"]["max_spend_usd"] = None
    payload["budget"]["warn_above_usd"] = 99.0

    assert client.put("/api/config", json=payload).status_code == 200


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_default_locale_is_english(client: TestClient) -> None:
    """Regression guard: the shipped default uses the current English locale tag."""
    config = client.get("/api/config").json()["config"]

    assert config["ui"]["locale"] == "en-US"


def test_default_budget_is_bounded(client: TestClient) -> None:
    """Unlimited must be opt-in, never the state a fresh install starts in."""
    budget = client.get("/api/config").json()["config"]["budget"]

    assert budget["max_spend_usd"] is not None
    assert budget["max_context_tokens"] is not None


def test_auto_save_is_undecided_by_default(client: TestClient) -> None:
    """`null` is what makes the web UI keep offering auto-save until answered."""
    config = client.get("/api/config").json()["config"]

    assert config["ui"]["auto_save"] is None


def test_auto_save_accepts_all_three_states(client: TestClient) -> None:
    """Undecided, enabled and dismissed are all first-class values."""
    payload = client.get("/api/config").json()["config"]

    for value in (True, False, None):
        payload["ui"]["auto_save"] = value
        response = client.put("/api/config", json=payload)

        assert response.status_code == 200
        assert response.json()["config"]["ui"]["auto_save"] is value


def test_auto_save_decision_survives_a_reload(client: TestClient) -> None:
    """ "Don't ask again" must hold across sessions, not just the current page."""
    payload = client.get("/api/config").json()["config"]
    payload["ui"]["auto_save"] = False
    client.put("/api/config", json=payload)

    reread = client.get("/api/config").json()

    assert reread["config"]["ui"]["auto_save"] is False


# ---------------------------------------------------------------------------
# Legacy migration
# ---------------------------------------------------------------------------


def test_a_config_with_removed_fallback_fields_still_loads(
    client: TestClient, settings: Settings
) -> None:
    """A config.yaml written before the fallback fields were removed must not break.

    `EngineConfig` sets `extra="ignore"` for exactly this reason — the keys are
    dropped on the next save rather than rejected on read.
    """
    settings.config_file.write_text(
        "schema_version: 1\n"
        "engine:\n"
        "  mode: api\n"
        "  provider_id: openrouter\n"
        "  model: anthropic/claude-sonnet-4.5\n"
        "  fallback_provider_id: openai\n"
        "  fallback_model: gpt-5.2\n"
        "  base_url:\n",
        encoding="utf-8",
    )

    response = client.get("/api/config")

    assert response.status_code == 200
    engine = response.json()["config"]["engine"]
    assert engine["provider_id"] == "openrouter"
    assert "fallback_provider_id" not in engine


def test_saving_drops_the_legacy_fallback_keys(client: TestClient, settings: Settings) -> None:
    settings.config_file.write_text(
        "engine:\n  provider_id: openrouter\n  fallback_provider_id: openai\n",
        encoding="utf-8",
    )

    client.put("/api/config", json=client.get("/api/config").json()["config"])

    assert "fallback" not in settings.config_file.read_text(encoding="utf-8")


def test_malformed_config_file_yields_422_not_500(client: TestClient, settings: Settings) -> None:
    """The file is hand-editable, so a bad edit is a user error with a fixable message."""
    settings.config_file.write_text("engine: [broken\n", encoding="utf-8")

    response = client.get("/api/config")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_key"] == "storage.invalid_yaml"
    assert detail["params"]["filename"] == "config.yaml"


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


def test_credentials_list_is_empty_initially(client: TestClient) -> None:
    response = client.get("/api/credentials")

    assert response.status_code == 200
    assert response.json()["credentials"] == []


def test_put_credential_never_echoes_the_secret(client: TestClient) -> None:
    """The single most important assertion in this file."""
    response = client.put(
        "/api/credentials",
        json={"provider_id": "openrouter", "api_key": SECRET, "label": "main"},
    )

    assert response.status_code == 200
    assert SECRET not in response.text

    entry = response.json()["credentials"][0]
    assert entry["masked_key"].startswith("sk-or-v1")
    assert "0123456789" not in entry["masked_key"]


def test_stored_credential_is_never_returned_by_a_later_read(
    client: TestClient,
) -> None:
    client.put("/api/credentials", json={"provider_id": "openai", "api_key": SECRET})

    assert SECRET not in client.get("/api/credentials").text


def test_credential_is_persisted_to_disk(client: TestClient, settings: Settings) -> None:
    client.put("/api/credentials", json={"provider_id": "openrouter", "api_key": SECRET})

    assert settings.credentials_file.is_file()
    assert SECRET in settings.credentials_file.read_text(encoding="utf-8")


def test_putting_the_same_provider_twice_replaces_it(client: TestClient) -> None:
    client.put("/api/credentials", json={"provider_id": "openrouter", "api_key": "sk-a"})
    client.put("/api/credentials", json={"provider_id": "openrouter", "api_key": "sk-b"})

    assert len(client.get("/api/credentials").json()["credentials"]) == 1


def test_delete_credential(client: TestClient) -> None:
    client.put("/api/credentials", json={"provider_id": "openrouter", "api_key": SECRET})

    assert client.delete("/api/credentials/openrouter").status_code == 204
    assert client.get("/api/credentials").json()["credentials"] == []


def test_deleting_an_absent_credential_is_404(client: TestClient) -> None:
    assert client.delete("/api/credentials/anthropic").status_code == 404


def test_unknown_provider_is_rejected(client: TestClient) -> None:
    response = client.put(
        "/api/credentials", json={"provider_id": "not-a-provider", "api_key": "x"}
    )

    assert response.status_code == 422


def test_empty_api_key_is_rejected(client: TestClient) -> None:
    response = client.put("/api/credentials", json={"provider_id": "openrouter", "api_key": ""})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


def test_openapi_documents_the_new_endpoints(client: TestClient) -> None:
    """The frontend generates its types from this schema."""
    paths = client.get("/api/openapi.json").json()["paths"]

    assert "/api/config" in paths
    assert "put" in paths["/api/config"]
    assert "/api/credentials" in paths
