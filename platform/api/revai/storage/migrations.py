"""Document migrations for persisted YAML files.

Every persisted document carries ``schema_version``. When a release changes a
persisted shape, it bumps :data:`revai.domain.enums.SCHEMA_VERSION` and
registers an upgrade step here, keyed by the version the file is coming *from*.
:meth:`migrate_document` is invoked by :class:`revai.storage.yaml_store.YamlStore`
on every read, so a document written by an older build is upgraded in memory
before validation and is re-stamped with the current version on the next save.

Rules for a migration step:

* Pure function: takes the parsed mapping, returns a new mapping. No I/O.
* Idempotent by intent: applied to a document that already half-satisfies the
  newer shape, it must be a no-op, because a user's hand-edited file may
  combine old and new fields freely.
* Never reintroduces data: dropping a deprecated key is the migration.

History (these used to live as ad-hoc model validators and now have a real
home — see the notes on each step):

* v1 → v2: legacy UI locale ``en`` normalised to ``en-US``.
* v2 → v3: the deferred fallback-provider keys dropped from ``engine``
  (``platform/docs/DEFERRED-FALLBACK-PROVIDER.md`` records the design).
* v3 → v4: Kiro CLI placeholder model ``kiro-default`` renamed to
  ``claude-haiku-4.5``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from revai.domain.enums import SCHEMA_VERSION
from revai.storage.base import StorageError

Migration = Callable[[dict[str, Any]], dict[str, Any]]


def _migrate_v1_to_v2(document: dict[str, Any]) -> dict[str, Any]:
    """Normalise the legacy ``en`` UI locale onto ``en-US``.

    ``en`` was shipped by alpha config files; without this a user upgrade
    silently drops their preferred language.
    """
    ui = document.get("ui")
    if isinstance(ui, dict) and ui.get("locale") == "en":
        ui["locale"] = "en-US"
    return document


def _migrate_v2_to_v3(document: dict[str, Any]) -> dict[str, Any]:
    """Drop the withdrawn ``engine.fallback_provider_id`` / ``fallback_model``.

    A fallback that silently changes model mid-review makes cost and quality
    unattributable; the keys were removed from the schema and the old config
    loader merely ignored them. Doing it here makes the removal explicit and
    keeps hand-edited files from carrying dead keys forever.
    """
    engine = document.get("engine")
    if isinstance(engine, dict):
        engine.pop("fallback_provider_id", None)
        engine.pop("fallback_model", None)
    return document


def _migrate_v3_to_v4(document: dict[str, Any]) -> dict[str, Any]:
    """Rename the Kiro CLI placeholder model to a real catalogue id."""
    engine = document.get("engine")
    if (
        isinstance(engine, dict)
        and engine.get("provider_id") == "kiro_cli"
        and engine.get("model") == "kiro-default"
    ):
        engine["model"] = "claude-haiku-4.5"
    return document


MIGRATIONS: dict[int, Migration] = {
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
    3: _migrate_v3_to_v4,
}


def migrate_document(
    document: dict[str, Any],
    *,
    target: int = SCHEMA_VERSION,
    filename: str = "",
) -> dict[str, Any]:
    """Upgrade ``document`` to ``target`` in registered, ordered steps.

    Raises :class:`StorageError` for a document from a version with no known
    path forward (including files written by a *newer* build, which this
    process cannot safely interpret). The error names the file because these
    documents are hand-editable.
    """
    try:
        version = int(document.get("schema_version", 1))
    except (TypeError, ValueError):
        raise StorageError("storage.invalid_schema_version", {"filename": filename}) from None

    while version < target:
        step = MIGRATIONS.get(version)
        if step is None:
            raise StorageError(
                "storage.unsupported_schema_version",
                {"filename": filename, "found": version, "target": target},
            )
        document = step(document)
        version += 1
        document["schema_version"] = version

    if version > target:
        raise StorageError(
            "storage.schema_version_from_the_future",
            {"filename": filename, "found": version, "target": target},
        )
    return document
