"""The structured error contract.

Every user-facing error — a validation failure, a not-found lookup, a git or
storage fault — is identified by a stable, dot-namespaced ``error_key``
(``"<domain>.<reason>"``, e.g. ``"budget.warn_above_exceeds_max"``) plus a
``params`` dict of raw, uninterpreted values. No raise site formats prose: the
frontend owns every sentence, in both English and Brazilian Portuguese, keyed
by ``error_key``. This is what lets ``"warn_above_usd must not exceed
max_spend_usd"`` become a clear, translated message instead of a string the
API and the UI would otherwise have to agree on by convention.

Two raise shapes cover the whole API:

* :class:`RevaiError` — for anything currently expressed as
  ``HTTPException(status_code=..., detail=...)``. Carries its own status code
  so the route handler still controls the HTTP semantics, but never builds the
  response body itself.
* ``pydantic_core.PydanticCustomError(error_key, template, params)`` — for
  ``@field_validator``/``@model_validator`` failures. Pydantic requires the
  ``template`` argument to render its own ``ValidationError`` message, but
  nothing downstream reads it: the ``RequestValidationError`` handler in
  ``main.py`` reads ``type`` (the error key) and ``ctx`` (the params) instead.

Naming convention for ``error_key``: ``<domain>.<reason>``, snake_case on both
sides, one key per distinct user-facing situation. Domains in use:
``budget``, ``project``, ``review``, ``git``, ``storage``, ``provider``,
``credential``, ``folder_picker``, ``ai_pipeline``,
``validation`` (generic pydantic fallback), ``internal`` (unhandled fallback).
"""

from __future__ import annotations

from typing import Any


class RevaiError(Exception):
    """A user-facing error with a stable key, structured params, and a status.

    Raised in place of ``HTTPException`` anywhere the response reaches a
    human. The central exception handler in ``main.py`` is the only place
    that turns this into a JSON body — no route handler formats ``detail``.
    """

    def __init__(
        self,
        status_code: int,
        error_key: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(error_key)
        self.status_code = status_code
        self.error_key = error_key
        self.params = params or {}
