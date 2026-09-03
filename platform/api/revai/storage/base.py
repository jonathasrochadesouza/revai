"""Storage contracts.

Two shapes cover everything the product needs:

* :class:`DocumentRepository` — exactly one document, always present
  (``config.yaml``, ``credentials.yaml``).
* :class:`Repository` — a collection addressed by id (projects, reviews).

Both are ``Protocol`` classes rather than base classes, so an implementation only
has to match the shape. That is what keeps a future Mongo backend from needing to
inherit anything from the YAML one.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class StorageError(RuntimeError):
    """Raised when persistence fails for a reason the caller can report.

    Deliberately not an ``HTTPException``: the storage layer must not know it is
    being used behind an HTTP API. Carries a namespaced ``error_key`` and
    structured ``params`` (never pre-formatted prose) so a route handler can
    translate it into the API's error contract.
    """

    def __init__(self, error_key: str, params: dict[str, Any] | None = None) -> None:
        self.error_key = error_key
        self.params = params or {}
        super().__init__(error_key)


@runtime_checkable
class DocumentRepository[T](Protocol):
    """A single document that always exists, defaulting when absent."""

    def load(self) -> T:
        """Return the document, or a freshly defaulted one if no file exists."""
        ...

    def save(self, document: T) -> T:
        """Persist the document atomically and return what was written."""
        ...

    def exists(self) -> bool: ...


@runtime_checkable
class Repository[T](Protocol):
    """A collection of documents addressed by string id."""

    def get(self, entity_id: str) -> T | None: ...

    def list(self) -> list[T]:
        """All entities. Ordering is defined by the implementation."""
        ...

    def save(self, entity: T) -> T:
        """Insert or replace, atomically."""
        ...

    def delete(self, entity_id: str) -> bool:
        """Return ``True`` if something was removed."""
        ...

    def exists(self, entity_id: str) -> bool: ...
