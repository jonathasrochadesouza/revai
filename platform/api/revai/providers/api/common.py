"""Small, security-conscious helpers shared by hosted API adapters."""

from __future__ import annotations

import json
import logging
import re

import httpx

from revai.domain.enums import ProviderId, ProviderKind
from revai.providers.base import HealthState, ProviderHealth

logger = logging.getLogger(__name__)

HEALTH_TIMEOUT_S = 10.0
_DONE = object()
_SECRET_PATTERN = re.compile(r"(?:sk-[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{10,})")


def parse_sse_line(line: str) -> dict | object | None:
    """Return one JSON SSE payload, a done sentinel, or ``None`` for metadata."""
    stripped = line.strip()
    if not stripped or stripped.startswith(":") or not stripped.startswith("data:"):
        return None

    data = stripped[5:].strip()
    if data == "[DONE]":
        return _DONE
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        logger.debug("skipping unparseable SSE payload")
        return None
    return parsed if isinstance(parsed, dict) else None


def as_int(value: object) -> int:
    """Accept integer token counters without treating booleans as integers."""
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def is_retryable(status: int) -> bool:
    return status == 429 or status >= 500


def describe_error(label: str, status: int, body: str, *, secret: str = "") -> str:
    """Surface a bounded provider message without reflecting credentials."""
    message: str | None = None
    try:
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            error = parsed.get("error")
            if isinstance(error, dict):
                candidate = error.get("message") or error.get("status")
                message = candidate if isinstance(candidate, str) else None
            elif isinstance(error, str):
                message = error
            elif isinstance(parsed.get("message"), str):
                message = parsed["message"]
    except (json.JSONDecodeError, ValueError):
        pass

    if not message:
        return f"{label} returned HTTP {status}."

    clean = " ".join(message.split())[:300]
    if secret:
        clean = clean.replace(secret, "[redacted]")
    clean = _SECRET_PATTERN.sub("[redacted]", clean)
    return f"{label} error {status}: {clean}"


async def probe_health(
    *,
    provider_id: ProviderId,
    label: str,
    url: str,
    headers: dict[str, str],
    ready_detail: str,
    auth_remediation: str | None,
    auth_statuses: frozenset[int] = frozenset({401, 403}),
) -> ProviderHealth:
    """Run a zero-token reachability/authentication probe that never raises."""
    try:
        async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT_S) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        return _health(
            provider_id,
            HealthState.ERROR,
            f"{label} did not respond within {HEALTH_TIMEOUT_S:g}s.",
            "Check your network connection and base URL",
        )
    except httpx.HTTPError:
        return _health(
            provider_id,
            HealthState.ERROR,
            f"Could not reach {label}.",
            "Check your network connection and base URL",
        )

    if response.status_code in auth_statuses:
        return _health(
            provider_id,
            HealthState.NEEDS_AUTH,
            f"{label} rejected the API key.",
            auth_remediation,
        )
    if response.status_code != 200:
        return _health(
            provider_id,
            HealthState.ERROR,
            f"{label} returned HTTP {response.status_code}.",
        )
    return ProviderHealth(
        provider_id=provider_id,
        kind=ProviderKind.API,
        state=HealthState.READY,
        detail=ready_detail,
        adapter_ready=True,
    )


def missing_key_health(provider_id: ProviderId, label: str, remediation: str) -> ProviderHealth:
    return _health(
        provider_id,
        HealthState.NEEDS_AUTH,
        f"No {label} API key stored.",
        remediation,
    )


def _health(
    provider_id: ProviderId,
    state: HealthState,
    detail: str,
    remediation: str | None = None,
) -> ProviderHealth:
    return ProviderHealth(
        provider_id=provider_id,
        kind=ProviderKind.API,
        state=state,
        detail=detail,
        remediation=remediation,
        adapter_ready=True,
    )
