"""Zero-token collection, filtering, parsing, and chunking."""

from __future__ import annotations

import ast
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from unidiff import PatchSet

from revai.git.repo import DiffFile

_LOCKFILES = {
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "yarn.lock",
}
_NOISE_DIRECTORIES = {
    ".next",
    ".nuxt",
    "build",
    "coverage",
    "dist",
    "generated",
    "node_modules",
    "vendor",
}
_TREE_SITTER_LANGUAGES = {
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cs": "c_sharp",
    ".go": "go",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".kt": "kotlin",
    ".php": "php",
    ".rb": "ruby",
    ".rs": "rust",
    ".swift": "swift",
    ".ts": "typescript",
    ".tsx": "tsx",
}
_SYMBOL_NODE_TYPES = {
    "class_declaration",
    "class_definition",
    "function_declaration",
    "function_definition",
    "interface_declaration",
    "method_declaration",
    "method_definition",
    "struct_item",
}
_TREE_SITTER_CACHE: dict[tuple[str, bytes], list[tuple[str | None, int, int]]] = {}
_TREE_SITTER_CACHE_LIMIT = 32


@dataclass(frozen=True)
class ParsedHunk:
    path: str
    source_start: int
    target_start: int
    added_lines: set[int]
    removed_lines: set[int]
    changed_text: str


@dataclass(frozen=True)
class CodeChunk:
    path: str
    symbol: str | None
    line_start: int
    line_end: int
    content: str
    estimated_tokens: int


def filter_changed_files(
    files: list[DiffFile],
) -> tuple[list[DiffFile], list[DiffFile]]:
    """Separate reviewable source from deterministic noise."""
    kept: list[DiffFile] = []
    skipped: list[DiffFile] = []
    for item in files:
        path = PurePosixPath(item.path.replace("\\", "/"))
        lowered_parts = {part.lower() for part in path.parts}
        lowered_name = path.name.lower()
        noisy = (
            item.binary
            or lowered_name in _LOCKFILES
            or bool(lowered_parts & _NOISE_DIRECTORIES)
            or lowered_name.endswith((".min.js", ".min.css", ".map", ".snap"))
            or ".generated." in lowered_name
            or "__snapshots__" in lowered_parts
        )
        (skipped if noisy else kept).append(item)
    return kept, skipped


def parse_unified_diff(
    patch: str,
    *,
    allowed_paths: set[str] | None = None,
) -> list[ParsedHunk]:
    """Parse a unified diff while retaining exact added and removed line numbers."""
    parsed: list[ParsedHunk] = []
    for patched_file in PatchSet(patch):
        path = patched_file.path.replace("\\", "/")
        if allowed_paths is not None and path not in allowed_paths:
            continue
        for hunk in patched_file:
            added_lines = {
                line.target_line_no
                for line in hunk
                if line.is_added and line.target_line_no is not None
            }
            removed_lines = {
                line.source_line_no
                for line in hunk
                if line.is_removed and line.source_line_no is not None
            }
            changed_text = "\n".join(
                line.value.rstrip("\n")
                for line in hunk
                if line.is_added or line.is_removed
            )
            parsed.append(
                ParsedHunk(
                    path=path,
                    source_start=hunk.source_start,
                    target_start=hunk.target_start,
                    added_lines=added_lines,
                    removed_lines=removed_lines,
                    changed_text=changed_text,
                )
            )
    return parsed


def build_chunks(
    repository: Path,
    hunks: list[ParsedHunk],
    *,
    max_tokens: int | None,
) -> list[CodeChunk]:
    """Build symbol-aligned context chunks without exceeding the review budget."""
    chunks: list[CodeChunk] = []
    remaining = max_tokens
    seen_boundaries: set[tuple[str, int, int]] = set()
    for hunk in hunks:
        if _is_trivial(hunk.changed_text):
            continue
        source = repository / hunk.path
        if not source.is_file():
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        changed_lines = [
            line
            for line in sorted(hunk.added_lines or {hunk.target_start})
            if 1 <= line <= len(lines) and not _is_trivial(lines[line - 1])
        ]
        for changed_line in changed_lines or [hunk.target_start]:
            symbol, line_start, line_end = _symbol_boundary(source, text, changed_line)
            boundary = (hunk.path, line_start, line_end)
            if boundary in seen_boundaries:
                continue
            seen_boundaries.add(boundary)

            content = "\n".join(lines[line_start - 1 : line_end])
            token_count = math.ceil(len(content) / 4) if content else 0
            if remaining is not None:
                if remaining <= 0:
                    return chunks
                if token_count > remaining:
                    content = content[: remaining * 4]
                    token_count = remaining
                remaining -= token_count
            chunks.append(
                CodeChunk(
                    path=hunk.path,
                    symbol=symbol,
                    line_start=line_start,
                    line_end=line_end,
                    content=content,
                    estimated_tokens=token_count,
                )
            )
    return chunks


def _symbol_boundary(
    path: Path,
    source: str,
    changed_line: int,
) -> tuple[str | None, int, int]:
    lines = source.splitlines()
    fallback = (None, max(1, changed_line), min(len(lines), max(1, changed_line)))
    if path.suffix.lower() not in {".py", ".pyi"}:
        return _tree_sitter_symbol(path, source, changed_line) or fallback
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return fallback

    candidates: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef)):
            end_line = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= changed_line <= end_line:
                candidates.append((node.lineno, end_line, node.name))
    if not candidates:
        return fallback
    start, end, name = min(candidates, key=lambda item: item[1] - item[0])
    return name, start, end


def _tree_sitter_symbol(
    path: Path,
    source: str,
    changed_line: int,
) -> tuple[str | None, int, int] | None:
    language = _TREE_SITTER_LANGUAGES.get(path.suffix.lower())
    if language is None:
        return None
    candidates = [
        symbol
        for symbol in _tree_sitter_symbols(language, source)
        if symbol[1] <= changed_line <= symbol[2]
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[2] - item[1])


def _tree_sitter_symbols(language: str, source: str) -> list[tuple[str | None, int, int]]:
    """Parse one source file in an isolated helper process.

    Some ``tree-sitter-language-pack`` native grammar combinations can segfault when
    several languages are traversed in one long-lived Python process. A code review
    must never take down the API, so the native boundary lives in a short-lived child.
    A bounded content-hash cache avoids paying that process cost for every hunk.
    """
    source_bytes = source.encode("utf-8")
    key = (language, hashlib.sha256(source_bytes).digest())
    if key in _TREE_SITTER_CACHE:
        return _TREE_SITTER_CACHE[key]

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "revai.pipeline.tree_sitter_worker", language],
            input=source_bytes,
            capture_output=True,
            timeout=10,
            check=False,
        )
        payload = json.loads(completed.stdout) if completed.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        payload = []

    symbols = [
        (item.get("name"), int(item["line_start"]), int(item["line_end"]))
        for item in payload
        if isinstance(item, dict)
        and isinstance(item.get("name"), str | type(None))
        and isinstance(item.get("line_start"), int)
        and isinstance(item.get("line_end"), int)
    ]
    if len(_TREE_SITTER_CACHE) >= _TREE_SITTER_CACHE_LIMIT:
        _TREE_SITTER_CACHE.pop(next(iter(_TREE_SITTER_CACHE)))
    _TREE_SITTER_CACHE[key] = symbols
    return symbols


def _is_trivial(changed_text: str) -> bool:
    meaningful = [
        line.strip()
        for line in changed_text.splitlines()
        if line.strip() and not line.strip().startswith(("#", "//", "/*", "*"))
    ]
    return not meaningful
