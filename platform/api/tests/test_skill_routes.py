"""Marketplace skill routes and prompt composition.

The invariants under test:

* **Install is previewed and pinned.** The install endpoint fetches the
  SKILL.md, stores the exact body plus its SHA-256, and refuses duplicates.
* **Caps are enforced at mutation time.** Max enabled skills and the composed
  character budget are 422s, never silent truncation.
* **Composition is additive and bounded.** Enabled review skills extend the
  system prompt, fix skills extend the user instructions, disabled skills
  change nothing, and the injection guard/sentinel remain server-side only.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from revai.config import Settings
from revai.domain.skills import (
    MAX_COMPOSED_SKILL_CHARS,
    MAX_ENABLED_SKILLS,
    InstalledSkill,
    SkillSettings,
)
from revai.skills.marketplace import MarketplaceClient, SkillContent
from revai.storage.repositories import SkillRepository


def _content(
    skill_id: str = "code-review", body: str = "Review the diff carefully."
) -> SkillContent:
    return SkillContent(
        skill_id=skill_id,
        source="mattpocock/skills",
        name=skill_id,
        description="A review skill.",
        body=body,
        content_sha256=hashlib.sha256(body.encode()).hexdigest(),
        license="MIT",
        path=f"skills/{skill_id}/SKILL.md",
        source_url=f"https://github.com/mattpocock/skills/tree/HEAD/skills/{skill_id}",
    )


def _patch_client(monkeypatch: pytest.MonkeyPatch, *, content: SkillContent | None = None) -> None:
    """Point the routes' marketplace client at a deterministic fake."""

    async def fake_content(_self: MarketplaceClient, _source: str, skill_id: str) -> SkillContent:
        if content is not None:
            return content
        return _content(skill_id)

    monkeypatch.setattr(MarketplaceClient, "content", fake_content, raising=True)


def _install(client: TestClient, skill_id: str = "code-review", focus: str = "both") -> dict:
    response = client.post(
        "/api/skills/install",
        json={"source": "mattpocock/skills", "skill_id": skill_id, "focus": focus},
    )
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# Install / list
# ---------------------------------------------------------------------------


def test_install_pins_body_and_sha(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, content=_content(body="Pinned instructions."))

    skill = _install(client)

    assert skill["id"] == "code-review"
    assert skill["enabled"] is True
    assert skill["focus"] == "both"
    assert skill["body"] == "Pinned instructions."
    assert skill["content_sha256"] == hashlib.sha256(b"Pinned instructions.").hexdigest()

    listed = client.get("/api/skills").json()
    assert [item["id"] for item in listed["skills"]] == ["code-review"]
    assert listed["path"].endswith("skills.yaml")


def test_install_refuses_duplicates(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch)
    _install(client)

    response = client.post(
        "/api/skills/install",
        json={"source": "mattpocock/skills", "skill_id": "code-review"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error_key"] == "skill.already_installed"


def test_list_is_empty_before_any_install(client: TestClient) -> None:
    body = client.get("/api/skills").json()

    assert body["skills"] == []


# ---------------------------------------------------------------------------
# Update / toggle / caps
# ---------------------------------------------------------------------------


def test_toggle_and_re_focus(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch)
    _install(client)

    toggled = client.put("/api/skills/code-review", json={"enabled": False})
    assert toggled.status_code == 200
    assert toggled.json()["enabled"] is False

    focused = client.put("/api/skills/code-review", json={"focus": "fix"})
    assert focused.json()["focus"] == "fix"
    assert focused.json()["enabled"] is False


def test_unknown_skill_is_404(client: TestClient) -> None:
    response = client.put("/api/skills/missing", json={"enabled": False})

    assert response.status_code == 404
    assert response.json()["detail"]["error_key"] == "skill.not_found"


def test_enabling_more_than_the_cap_is_rejected(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_client(monkeypatch)
    skill_repo = SkillRepository(settings)
    skill_repo.save(
        SkillSettings(
            skills=[
                InstalledSkill(
                    id=f"skill-{index}",
                    source="acme/skills",
                    name=f"Skill {index}",
                    body="x" * 100,
                    content_sha256="a" * 64,
                )
                for index in range(MAX_ENABLED_SKILLS + 1)
            ]
        )
    )

    # Any mutation re-checks the cap — even toggling one of the rows itself.
    response = client.put("/api/skills/skill-0", json={"focus": "fix"})

    assert response.status_code == 422
    assert response.json()["detail"]["error_key"] == "skill.max_enabled"


def test_composing_over_the_character_budget_is_rejected(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_client(monkeypatch)
    skill_repo = SkillRepository(settings)
    big_body = "x" * 30_000
    skill_repo.save(
        SkillSettings(
            skills=[
                InstalledSkill(
                    id=f"big-{index}",
                    source="acme/skills",
                    name=f"Big {index}",
                    body=big_body,
                    content_sha256="a" * 64,
                )
                for index in range(2)  # 60k > MAX_COMPOSED_SKILL_CHARS
            ]
        )
    )

    response = client.put("/api/skills/big-0", json={"focus": "fix"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_key"] == "skill.composed_too_large"
    assert detail["params"]["max_chars"] == MAX_COMPOSED_SKILL_CHARS


# ---------------------------------------------------------------------------
# Update (manual upgrade) / uninstall
# ---------------------------------------------------------------------------


def test_refresh_detects_change_and_re_pins(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_client(monkeypatch)
    _install(client)

    async def changed(_self: MarketplaceClient, _source: str, _skill_id: str) -> SkillContent:
        return _content(body="Newly updated instructions.")

    monkeypatch.setattr(MarketplaceClient, "content", changed, raising=True)

    response = client.post("/api/skills/code-review/update")

    assert response.status_code == 200
    body = response.json()
    assert body["updated"] is True
    assert body["skill"]["body"] == "Newly updated instructions."
    assert (
        body["skill"]["content_sha256"]
        == hashlib.sha256(b"Newly updated instructions.").hexdigest()
    )


def test_refresh_without_upstream_change_is_a_no_op(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_client(monkeypatch)
    _install(client)

    response = client.post("/api/skills/code-review/update")

    assert response.json()["updated"] is False


def test_check_updates_reports_availability(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_client(monkeypatch)
    _install(client)

    async def changed(_self: MarketplaceClient, _source: str, _skill_id: str) -> SkillContent:
        return _content(body="Changed upstream.")

    monkeypatch.setattr(MarketplaceClient, "content", changed, raising=True)

    updates = client.post("/api/skills/check-updates").json()["updates"]

    assert updates == [
        {
            "skill_id": "code-review",
            "installed_sha256": hashlib.sha256(b"Review the diff carefully.").hexdigest(),
            "remote_sha256": hashlib.sha256(b"Changed upstream.").hexdigest(),
            "update_available": True,
        }
    ]


def test_uninstall_removes_the_row(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch)
    _install(client)

    response = client.delete("/api/skills/code-review")

    assert response.status_code == 204
    assert client.get("/api/skills").json()["skills"] == []


# ---------------------------------------------------------------------------
# Marketplace browse + preview
# ---------------------------------------------------------------------------


def _patch_search(monkeypatch: pytest.MonkeyPatch, results: list[dict[str, Any]]) -> None:
    async def fake_search(_self: MarketplaceClient, query: str, *, limit: int = 24):
        return [
            type(
                "S",
                (),
                {
                    "id": item["id"],
                    "name": item["id"],
                    "source": item["source"],
                    "installs": item.get("installs"),
                    "description": item.get("description", ""),
                    "url": f"https://skills.sh/skill/{item['source']}/{item['id']}",
                },
            )()
            for item in results
        ]

    monkeypatch.setattr(MarketplaceClient, "search", fake_search, raising=True)


def test_marketplace_search_passes_through(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_search(
        monkeypatch,
        [
            {"id": "code-review", "source": "acme/skills", "installs": 1000, "description": "d"},
        ],
    )

    body = client.get("/api/skills/marketplace", params={"q": "review"}).json()

    assert body["query"] == "review"
    assert body["skills"] == [
        {
            "id": "code-review",
            "name": "code-review",
            "source": "acme/skills",
            "installs": 1000,
            "description": "d",
            "url": "https://skills.sh/skill/acme/skills/code-review",
        }
    ]


def test_marketplace_requires_a_real_query(client: TestClient) -> None:
    response = client.get("/api/skills/marketplace", params={"q": "a"})

    assert response.status_code == 422


def test_preview_returns_the_full_body(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, content=_content(body="Everything the model will read."))

    body = client.get(
        "/api/skills/marketplace/preview",
        params={"source": "mattpocock/skills", "skill_id": "code-review"},
    ).json()

    assert body["body"] == "Everything the model will read."
    assert body["content_sha256"] == hashlib.sha256(b"Everything the model will read.").hexdigest()


# ---------------------------------------------------------------------------
# Composition with the review pipeline
# ---------------------------------------------------------------------------


def test_compose_appends_review_and_fix_sections() -> None:
    review_skill = InstalledSkill(
        id="reviewer",
        source="acme/skills",
        name="Reviewer",
        focus="review",
        body="REVIEW GUIDANCE",
        content_sha256="a" * 64,
    )
    fix_skill = InstalledSkill(
        id="fixer",
        source="acme/skills",
        name="Fixer",
        focus="fix",
        body="FIX GUIDANCE",
        content_sha256="b" * 64,
    )

    from revai.domain.skills import compose_prompts

    system, user = compose_prompts(("BASE SYSTEM", "BASE USER"), [review_skill, fix_skill])

    assert system.startswith("BASE SYSTEM")
    assert "## Skill: Reviewer (from skills.sh)\nREVIEW GUIDANCE" in system
    assert "FIX GUIDANCE" not in system
    assert user.startswith("BASE USER")
    assert "## Patch guidance — skill: Fixer (from skills.sh)\nFIX GUIDANCE" in user
    assert "REVIEW GUIDANCE" not in user


def test_compose_ignores_disabled_skills() -> None:
    disabled = InstalledSkill(
        id="reviewer",
        source="acme/skills",
        name="Reviewer",
        enabled=False,
        body="REVIEW GUIDANCE",
        content_sha256="a" * 64,
    )

    from revai.domain.skills import compose_prompts

    system, user = compose_prompts(("BASE SYSTEM", "BASE USER"), [disabled])

    assert system == "BASE SYSTEM"
    assert user == "BASE USER"


def test_review_route_composition_extends_the_resolved_prompts(
    settings: Settings,
) -> None:
    """The review endpoint composes skills on top of the base prompt pair."""
    from revai.api.routes.reviews import _compose_skill_prompts
    from revai.domain.models import PromptOverride
    from revai.storage.repositories import SkillRepository

    skill_repo = SkillRepository(settings)
    skill_repo.save(
        SkillSettings(
            skills=[
                InstalledSkill(
                    id="reviewer",
                    source="acme/skills",
                    name="Reviewer",
                    focus="review",
                    body="REVIEW GUIDANCE",
                    content_sha256="a" * 64,
                ),
                InstalledSkill(
                    id="sleepy",
                    source="acme/skills",
                    name="Sleepy",
                    focus="review",
                    enabled=False,
                    body="SHOULD NOT APPEAR",
                    content_sha256="b" * 64,
                ),
            ]
        )
    )
    base = PromptOverride(system_prompt="BASE SYSTEM", user_prompt="BASE USER")

    composed = _compose_skill_prompts(skill_repo, base)

    assert "BASE SYSTEM" in composed.system_prompt
    assert "REVIEW GUIDANCE" in composed.system_prompt
    assert "SHOULD NOT APPEAR" not in composed.system_prompt
    assert composed.user_prompt == "BASE USER"
    # The base prompt object is untouched — composition is additive.
    assert base.system_prompt == "BASE SYSTEM"


def test_review_route_composition_survives_a_corrupt_skills_file(
    settings: Settings,
) -> None:
    from revai.api.routes.reviews import _compose_skill_prompts
    from revai.domain.models import PromptOverride
    from revai.storage.repositories import SkillRepository

    skills_file = settings.skills_file
    skills_file.parent.mkdir(parents=True, exist_ok=True)
    skills_file.write_text(":: not yaml [", encoding="utf-8")

    base = PromptOverride(system_prompt="BASE SYSTEM", user_prompt="BASE USER")

    composed = _compose_skill_prompts(SkillRepository(settings), base)

    # A broken skills file must never fail a review: compose without skills.
    assert composed.system_prompt == "BASE SYSTEM"
    assert composed.user_prompt == "BASE USER"
