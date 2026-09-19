"""HTTP contract for prompt templates and scenarios.

The important invariants:

* The built-in defaults are code constants — they are customised and reset,
  never created or deleted.
* Every read and write names a locale, so customising one language can never
  leak into another.
* Scenarios are deletable snapshots; the only undeletable things are the two
  default prompt pairs, which are not rows in the file at all.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from revai.domain.prompts import DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_INSTRUCTIONS


def _saved_defaults(client: TestClient, locale: str = "en-US") -> dict:
    return client.get(f"/api/prompts?locale={locale}").json()["defaults"]


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_get_prompts_returns_builtins_before_any_save(client: TestClient) -> None:
    response = client.get("/api/prompts")

    assert response.status_code == 200
    body = response.json()
    assert body["locale"] == "en-US"
    assert body["builtin"]["system_prompt"] == DEFAULT_SYSTEM_PROMPT["en-US"]
    assert body["defaults"]["customized"] is False
    assert body["scenarios"] == []
    assert body["path"].endswith("prompts.yaml")


def test_get_prompts_defaults_to_the_configured_ui_locale(client: TestClient) -> None:
    payload = client.get("/api/config").json()["config"]
    payload["ui"]["locale"] = "pt-BR"
    client.put("/api/config", json=payload)

    body = client.get("/api/prompts").json()

    assert body["locale"] == "pt-BR"
    assert body["builtin"]["system_prompt"] == DEFAULT_SYSTEM_PROMPT["pt-BR"]
    assert body["defaults"]["user_prompt"] == DEFAULT_USER_INSTRUCTIONS["pt-BR"]


def test_put_defaults_customises_only_the_requested_locale(client: TestClient) -> None:
    response = client.put(
        "/api/prompts/defaults",
        json={
            "locale": "pt-BR",
            "system_prompt": "Revisor sênior personalizado.",
            "user_prompt": "Instruções personalizadas.",
        },
    )

    assert response.status_code == 200
    assert response.json()["customized"] is True

    pt = _saved_defaults(client, "pt-BR")
    assert pt["customized"] is True
    assert pt["system_prompt"] == "Revisor sênior personalizado."

    en = _saved_defaults(client, "en-US")
    assert en["customized"] is False
    assert en["system_prompt"] == DEFAULT_SYSTEM_PROMPT["en-US"]


def test_reset_defaults_restores_the_builtin_for_one_locale(client: TestClient) -> None:
    client.put(
        "/api/prompts/defaults",
        json={
            "locale": "en-US",
            "system_prompt": "A custom system prompt.",
            "user_prompt": "Custom instructions.",
        },
    )

    response = client.post("/api/prompts/defaults/reset", json={"locale": "en-US"})

    assert response.status_code == 200
    body = response.json()
    assert body["customized"] is False
    assert body["system_prompt"] == DEFAULT_SYSTEM_PROMPT["en-US"]
    assert _saved_defaults(client)["system_prompt"] == DEFAULT_SYSTEM_PROMPT["en-US"]


def test_reset_defaults_with_no_customization_is_a_noop(client: TestClient) -> None:
    response = client.post("/api/prompts/defaults/reset", json={"locale": "pt-BR"})

    assert response.status_code == 200
    assert response.json()["customized"] is False


def test_put_defaults_rejects_empty_prompts(client: TestClient) -> None:
    response = client.put(
        "/api/prompts/defaults",
        json={"locale": "en-US", "system_prompt": "", "user_prompt": "x"},
    )

    assert response.status_code == 422


def test_put_defaults_rejects_an_unknown_locale(client: TestClient) -> None:
    response = client.put(
        "/api/prompts/defaults",
        json={"locale": "fr-FR", "system_prompt": "a", "user_prompt": "b"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def test_create_scenario_copies_the_current_defaults(client: TestClient) -> None:
    client.put(
        "/api/prompts/defaults",
        json={
            "locale": "en-US",
            "system_prompt": "Backend only.",
            "user_prompt": "Focus on SQL.",
        },
    )

    response = client.post("/api/prompts/scenarios", json={"name": "Backend - Java"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Backend - Java"
    assert body["system_prompt"] == "Backend only."
    assert body["user_prompt"] == "Focus on SQL."


def test_create_scenario_accepts_explicit_prompts(client: TestClient) -> None:
    response = client.post(
        "/api/prompts/scenarios",
        json={
            "name": "Backend - Go",
            "system_prompt": "Go reviewer.",
            "user_prompt": "Race checks.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["system_prompt"] == "Go reviewer."
    assert body["id"]


def test_scenario_names_are_unique_regardless_of_case(client: TestClient) -> None:
    client.post("/api/prompts/scenarios", json={"name": "Backend - Python"})

    response = client.post("/api/prompts/scenarios", json={"name": "backend - python"})

    assert response.status_code == 422
    assert response.json()["detail"]["error_key"] == "prompt_scenario.duplicate_name"


def test_update_scenario_edits_name_and_prompts(client: TestClient) -> None:
    scenario = client.post("/api/prompts/scenarios", json={"name": "Draft"}).json()

    response = client.put(
        f"/api/prompts/scenarios/{scenario['id']}",
        json={
            "name": "Backend - Java",
            "system_prompt": "Java reviewer.",
            "user_prompt": "Nullability.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Backend - Java"
    assert body["system_prompt"] == "Java reviewer."

    listed = client.get("/api/prompts").json()["scenarios"]
    assert [item["name"] for item in listed] == ["Backend - Java"]


def test_update_scenario_rejects_a_name_used_by_another_scenario(client: TestClient) -> None:
    first = client.post("/api/prompts/scenarios", json={"name": "Backend - Java"}).json()
    client.post("/api/prompts/scenarios", json={"name": "Backend - Go"})

    response = client.put(
        f"/api/prompts/scenarios/{first['id']}",
        json={"name": "Backend - Go", "system_prompt": "s", "user_prompt": "u"},
    )

    assert response.status_code == 422


def test_delete_scenario_removes_it(client: TestClient) -> None:
    scenario = client.post("/api/prompts/scenarios", json={"name": "Backend - Java"}).json()

    response = client.delete(f"/api/prompts/scenarios/{scenario['id']}")

    assert response.status_code == 204
    assert client.get("/api/prompts").json()["scenarios"] == []


def test_delete_unknown_scenario_returns_the_structured_404(client: TestClient) -> None:
    response = client.delete("/api/prompts/scenarios/missing")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error_key"] == "prompt_scenario.not_found"
    assert detail["params"] == {"scenario_id": "missing"}


def test_scenario_prompts_survive_a_defaults_reset(client: TestClient) -> None:
    """Scenarios are independent snapshots — resetting the defaults must not
    silently rewrite a prompt pair the user curated."""
    client.put(
        "/api/prompts/defaults",
        json={"locale": "en-US", "system_prompt": "Custom.", "user_prompt": "Custom instructions."},
    )
    scenario = client.post("/api/prompts/scenarios", json={"name": "Backend - Java"}).json()
    client.post("/api/prompts/defaults/reset", json={"locale": "en-US"})

    listed = client.get("/api/prompts").json()["scenarios"]
    assert listed[0]["id"] == scenario["id"]
    assert listed[0]["system_prompt"] == "Custom."
