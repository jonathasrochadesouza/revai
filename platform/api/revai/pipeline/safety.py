"""Safety boundary between repository content and an AI provider."""

from __future__ import annotations

import re
from dataclasses import dataclass

from revai.pipeline.deterministic import CodeChunk

_SECRET_PATTERNS = (
    re.compile(
        r"(?i)\b[\w$]*(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|password)[\w$]*"
        r"\s*[:=]\s*(['\"])([^'\"\r\n]{8,})\1"
    ),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?"
        r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
)
_REDACTION = "[REDACTED_REVAI_SECRET]"


@dataclass(frozen=True)
class SanitizedChunks:
    chunks: list[CodeChunk]
    redactions: int


def sanitize_chunks(chunks: list[CodeChunk]) -> SanitizedChunks:
    """Redact credential-like values without changing file or line boundaries."""
    sanitized: list[CodeChunk] = []
    total = 0
    for chunk in chunks:
        content, count = redact_secrets(chunk.content)
        total += count
        sanitized.append(
            CodeChunk(
                path=chunk.path,
                symbol=chunk.symbol,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                content=content,
                estimated_tokens=max(1, (len(content) + 3) // 4) if content else 0,
            )
        )
    return SanitizedChunks(sanitized, total)


def redact_secrets(value: str) -> tuple[str, int]:
    redacted = value
    count = 0
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            def replace(match: re.Match[str]) -> str:
                nonlocal count
                count += 1
                entire = match.group(0)
                secret = match.group(2)
                return entire.replace(secret, _REDACTION)

            redacted = pattern.sub(replace, redacted)
        else:
            redacted, replacements = pattern.subn(_REDACTION, redacted)
            count += replacements
    return redacted, count
