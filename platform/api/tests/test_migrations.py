"""Document migration behaviour.

Migrations are the guarantee that a config written by an older build still
loads after an upgrade — and that a file written by a *newer* build fails
loudly instead of being half-interpreted.
"""

from __future__ import annotations

import pytest

from revai.config import Settings
from revai.domain.models import RevaiConfig
from revai.storage.base import StorageError
from revai.storage.migrations import migrate_document
from revai.storage.yaml_store import YamlStore

# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def test_v1_locale_en_becomes_en_us() -> None:
    migrated = migrate_document({"schema_version": 1, "ui": {"locale": "en"}})

    assert migrated["ui"]["locale"] == "en-US"
    assert migrated["schema_version"] == 7


def test_v4_documents_pass_through_the_fix_state_migration() -> None:
    migrated = migrate_document({"schema_version": 4})

    assert migrated["schema_version"] == 7


def test_v2_drops_withdrawn_fallback_engine_keys() -> None:
    migrated = migrate_document(
        {
            "schema_version": 2,
            "engine": {"fallback_provider_id": "openrouter", "fallback_model": "x"},
        }
    )

    assert "fallback_provider_id" not in migrated["engine"]
    assert "fallback_model" not in migrated["engine"]


def test_v3_renames_the_kiro_placeholder_model() -> None:
    migrated = migrate_document(
        {
            "schema_version": 3,
            "engine": {"provider_id": "kiro_cli", "model": "kiro-default"},
        }
    )

    assert migrated["engine"]["model"] == "claude-haiku-4.5"


def test_v5_project_with_remote_url_becomes_local_clone() -> None:
    migrated = migrate_document(
        {"schema_version": 5, "path": "/repo", "remote_url": "https://example.com/x.git"}
    )

    assert migrated["kind"] == "local_clone"


def test_v5_project_without_remote_url_becomes_local_open() -> None:
    migrated = migrate_document({"schema_version": 5, "path": "/repo", "remote_url": None})

    assert migrated["kind"] == "local_open"


def test_v5_non_project_documents_are_untouched_by_the_kind_backfill() -> None:
    """Only documents shaped like a project (both ``path`` and ``remote_url``)
    are eligible for the backfill — a config or credentials document must
    pass through with no ``kind`` key added."""
    migrated = migrate_document({"schema_version": 5, "engine": {"provider_id": "openrouter"}})

    assert "kind" not in migrated


def test_v5_project_kind_backfill_does_not_override_an_explicit_kind() -> None:
    migrated = migrate_document(
        {
            "schema_version": 5,
            "path": "/repo",
            "remote_url": None,
            "kind": "local_clone",
        }
    )

    assert migrated["kind"] == "local_clone"


def test_v6_drops_the_withdrawn_sonarqube_analyzer_block() -> None:
    migrated = migrate_document(
        {
            "schema_version": 6,
            "analyzers": {"ruff": True, "sonarqube": {"enabled": False, "wsl": False}},
        }
    )

    assert migrated["analyzers"] == {"ruff": True}
    assert migrated["schema_version"] == 7


def test_v6_documents_without_sonar_keys_pass_through() -> None:
    migrated = migrate_document({"schema_version": 6, "analyzers": {"ruff": True}})

    assert migrated["analyzers"] == {"ruff": True}
    assert migrated["schema_version"] == 7


def test_migrations_are_idempotent_on_current_documents() -> None:
    """A document already on the current shape must pass through untouched."""
    document = {"schema_version": 7, "engine": {"provider_id": "openrouter"}}

    assert migrate_document(document) == document


def test_current_version_is_not_migrated_again() -> None:
    document = {"schema_version": 7}

    assert migrate_document(document)["schema_version"] == 7


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def test_unknown_historical_version_is_rejected() -> None:
    """No registered path means the file cannot be interpreted safely."""
    with pytest.raises(StorageError) as caught:
        migrate_document({"schema_version": 0}, filename="config.yaml")

    assert caught.value.error_key == "storage.unsupported_schema_version"
    assert caught.value.params["filename"] == "config.yaml"


def test_future_schema_version_is_rejected() -> None:
    with pytest.raises(StorageError) as caught:
        migrate_document({"schema_version": 99}, filename="config.yaml")

    assert caught.value.error_key == "storage.schema_version_from_the_future"


def test_non_integer_schema_version_is_rejected() -> None:
    with pytest.raises(StorageError) as caught:
        migrate_document({"schema_version": "four"}, filename="config.yaml")

    assert caught.value.error_key == "storage.invalid_schema_version"


# ---------------------------------------------------------------------------
# Store integration
# ---------------------------------------------------------------------------


def test_yaml_store_migrates_old_documents_on_read(settings: Settings) -> None:
    """Write a v1 file by hand, then read it through the typed store."""
    path = settings.config_file
    path.write_text(
        "schema_version: 1\nui:\n  locale: en\nengine:\n  model: anthropic/claude-sonnet-5\n",
        encoding="utf-8",
    )

    config = YamlStore(RevaiConfig).read(path)

    assert config is not None
    assert config.ui.locale == "en-US"


def test_yaml_store_round_trips_a_migrated_document_at_the_current_version(
    settings: Settings,
) -> None:
    path = settings.config_file
    path.write_text("schema_version: 1\nui:\n  locale: en\n", encoding="utf-8")
    store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)

    store.write(path, store.read(path) or RevaiConfig())

    reloaded = store.read(path)
    assert reloaded is not None
    assert reloaded.schema_version == 7
    assert reloaded.ui.locale == "en-US"
