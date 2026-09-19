"""Atomic, lock-guarded YAML persistence.

Three guarantees, in order of importance:

1. **A write never leaves a half-written file.** The payload goes to a temporary
   file in the *same directory* and is then moved into place with
   :func:`os.replace`, which is atomic on POSIX and on Windows (``MoveFileEx``
   with ``MOVEFILE_REPLACE_EXISTING``). Same directory matters — a cross-device
   move is a copy, and a copy is not atomic.

2. **Concurrent writers serialise.** A ``filelock`` sidecar guards each path.
   The API is single-process today, but the reload worker, a future CLI and the
   user's own editor can all reach the same file.

3. **Comments and key order survive.** ``ruamel.yaml`` in round-trip mode, so a
   config a human annotated stays annotated after the app saves it.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout
from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from revai.storage.base import StorageError
from revai.storage.migrations import migrate_document

logger = logging.getLogger(__name__)

# Long enough to outlast a slow disk, short enough that a stale lock surfaces as
# an error the user can act on instead of hanging the request.
LOCK_TIMEOUT_S = 10.0


def _yaml() -> YAML:
    """A round-trip parser configured for human-editable files."""
    parser = YAML(typ="rt")
    parser.preserve_quotes = True
    parser.default_flow_style = False
    parser.indent(mapping=2, sequence=4, offset=2)
    parser.width = 100
    return parser


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    """Hold an exclusive lock on ``path`` for the duration of the block."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(lock_path), timeout=LOCK_TIMEOUT_S):
            yield
    except Timeout as exc:
        raise StorageError(
            "storage.lock_timeout",
            {"filename": path.name, "timeout_s": LOCK_TIMEOUT_S},
        ) from exc


def atomic_write(path: Path, content: str) -> None:
    """Replace ``path`` with ``content``, atomically.

    Encoding is always UTF-8 without a BOM, and ``newline="\\n"`` disables the
    platform translation that would otherwise expand every ``\\n`` into ``\\r\\n``
    on Windows. Both are deliberate: the PowerShell version wrote patches with
    ``>`` redirection, which emits UTF-16LE on PS 5.1 and produced files other
    tools could not read.

    Note this pins translation, it does not rewrite the payload — a ``\\r`` you
    pass in is still a ``\\r`` on disk.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_name: str | None = None
    try:
        # delete=False because we move the file rather than let it be removed.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,  # same filesystem → os.replace stays atomic
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(content)
            tmp.flush()
            # Force the bytes to disk before publishing the new name, so a crash
            # cannot leave an empty-but-present file.
            os.fsync(tmp.fileno())

        os.replace(tmp_name, path)
        tmp_name = None
    except UnicodeEncodeError as exc:
        # A lone surrogate (U+D800 to U+DFFF) is not encodable as UTF-8, and it is
        # reachable from the API: Pydantic accepts such a string and `json.dumps`
        # escapes it as "\ud800", so a client can put one in a request body.
        # Without this branch the caller would see a bare UnicodeEncodeError and
        # return 500, instead of a storage error naming the offending character.
        raise StorageError(
            "storage.write_unencodable_character",
            {
                "path": str(path),
                "character": repr(exc.object[exc.start : exc.end]),
                "position": exc.start,
            },
        ) from exc
    except OSError as exc:
        raise StorageError("storage.write_failed", {"path": str(path), "detail": str(exc)}) from exc
    finally:
        # Losing a stray temporary file is never worth masking the original
        # exception that sent us into this block.
        if tmp_name and os.path.exists(tmp_name):
            with suppress(OSError):
                os.unlink(tmp_name)


def _plain(value: Any) -> Any:
    """Convert a Pydantic dump into YAML-native scalars.

    ``ruamel`` will not emit an ``Enum`` or a ``datetime`` subclass cleanly, and
    ``Path`` would serialise as a tagged object. Normalising here keeps the files
    readable by anything, not just by RevAI.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {_plain(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


class YamlStore[T: BaseModel]:
    """Reads and writes one Pydantic model to one YAML file."""

    def __init__(self, model: type[T]) -> None:
        self._model = model
        self._yaml = _yaml()

    # -- read ---------------------------------------------------------------

    def read(self, path: Path) -> T | None:
        """Load and validate. Returns ``None`` when the file does not exist.

        A missing file is a normal state — a fresh install has none. Malformed
        content is not, and raises :class:`StorageError` with the path included,
        because these files are hand-editable and the user needs to know which
        one to fix.
        """
        if not path.is_file():
            return None

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise StorageError(
                "storage.read_failed", {"path": str(path), "detail": str(exc)}
            ) from exc

        try:
            data = self._yaml.load(raw)
        except YAMLError as exc:
            raise StorageError(
                "storage.invalid_yaml", {"filename": path.name, "detail": str(exc)}
            ) from exc

        if data is None:  # an empty file
            return None

        if not isinstance(data, dict):
            raise StorageError(
                "storage.not_a_mapping",
                {"filename": path.name, "found_type": type(data).__name__},
            )

        # A document from an older build is upgraded in memory here; the next
        # write re-stamps it with the current schema version.
        data = migrate_document(dict(data), filename=path.name)

        try:
            return self._model.model_validate(data)
        except ValidationError as exc:
            raise StorageError(
                "storage.schema_mismatch",
                {"filename": path.name, "detail": _describe(exc)},
            ) from exc

    # -- write --------------------------------------------------------------

    def write(self, path: Path, document: T) -> T:
        """Serialise and atomically replace ``path``."""
        payload = _plain(document.model_dump(mode="python"))

        buffer = io.StringIO()
        try:
            self._yaml.dump(payload, buffer)
        except YAMLError as exc:
            raise StorageError(
                "storage.serialize_failed", {"filename": path.name, "detail": str(exc)}
            ) from exc

        with _locked(path):
            atomic_write(path, buffer.getvalue())

        logger.debug("wrote %s", path)
        return document

    # -- helpers ------------------------------------------------------------

    def update(self, path: Path, document: T) -> T:
        """Read-modify-write under a single lock.

        Currently equivalent to :meth:`write`; exists so callers that need
        read-then-write semantics have somewhere to grow without reaching for the
        lock themselves.
        """
        with _locked(path):
            atomic_write(path, self._render(document))
        return document

    def _render(self, document: T) -> str:
        buffer = io.StringIO()
        self._yaml.dump(_plain(document.model_dump(mode="python")), buffer)
        return buffer.getvalue()


def _describe(error: ValidationError) -> str:
    """One-line summary of the first few validation problems."""
    parts = []
    for item in error.errors()[:3]:
        location = ".".join(str(piece) for piece in item["loc"]) or "(root)"
        parts.append(f"{location}: {item['msg']}")
    remaining = len(error.errors()) - len(parts)
    if remaining > 0:
        parts.append(f"and {remaining} more")
    return "; ".join(parts)
