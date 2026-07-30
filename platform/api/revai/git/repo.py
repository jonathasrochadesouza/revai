"""Read-only Git operations used by the Phase 3 project workspace."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from revai.domain.models import Project

_GIT_TIMEOUT_SECONDS = 30
_PATCH_LIMIT_BYTES = 1_000_000
_ESTIMATED_INPUT_USD_PER_MILLION_TOKENS = 3.0

_LANGUAGES = {
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".go": "Go",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".md": "Markdown",
    ".php": "PHP",
    ".ps1": "PowerShell",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".scss": "SCSS",
    ".sh": "Shell",
    ".swift": "Swift",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vue": "Vue",
}


class GitError(RuntimeError):
    """A user-actionable Git failure."""


@dataclass(frozen=True)
class DiffFile:
    path: str
    additions: int
    deletions: int
    binary: bool = False


@dataclass(frozen=True)
class DiffPreview:
    base: str
    head: str
    files: list[DiffFile]
    additions: int
    deletions: int
    estimated_tokens: int
    estimated_cost_usd: float
    patch: str
    truncated: bool


def _run(
    cwd: Path | None,
    *args: str,
    timeout: int = _GIT_TIMEOUT_SECONDS,
    allowed_returncodes: tuple[int, ...] = (0,),
) -> str:
    command = ["git"]
    if cwd is not None:
        command.extend(["-C", str(cwd)])
    command.extend(args)

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise GitError("Git is not installed or is not available on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("Git did not finish within 30 seconds.") from exc

    if result.returncode not in allowed_returncodes:
        detail = result.stderr.strip() or result.stdout.strip() or "Git command failed."
        raise GitError(detail)
    return result.stdout


def repository_root(path: Path) -> Path:
    if not path.exists() or not path.is_dir():
        raise GitError("The selected folder does not exist.")
    try:
        root = _run(path, "rev-parse", "--show-toplevel").strip()
    except GitError as exc:
        raise GitError("The selected folder is not a Git repository.") from exc
    return Path(root).resolve()


def branches(path: Path) -> list[str]:
    output = _run(
        path,
        "for-each-ref",
        "--format=%(refname:short)",
        "--sort=refname",
        "refs/heads",
    )
    return [line for line in output.splitlines() if line]


def current_branch(path: Path) -> str | None:
    branch = _run(path, "branch", "--show-current").strip()
    return branch or None


def tracked_files(path: Path, ref: str = "HEAD") -> list[str]:
    _verify_ref(path, ref)
    output = _run(path, "ls-tree", "-r", "--name-only", ref)
    return [line for line in output.splitlines() if line]


def detect_languages(path: Path) -> list[str]:
    found = {
        language
        for filename in tracked_files(path)
        if (language := _LANGUAGES.get(Path(filename).suffix.lower()))
    }
    return sorted(found)


def remote_url(path: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(path), "config", "--get", "remote.origin.url"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    value = result.stdout.strip()
    return value or None


def detect_base_branch(path: Path) -> str:
    known = branches(path)
    for candidate in ("main", "develop", "master"):
        if candidate in known:
            return candidate
    active = current_branch(path)
    if active:
        return active
    if known:
        return known[0]
    raise GitError("The repository has no commits or branches yet.")


def inspect_project(path: Path, *, source_url: str | None = None) -> Project:
    root = repository_root(path)
    return Project(
        name=root.name,
        path=str(root),
        remote_url=source_url or remote_url(root),
        base_branch=detect_base_branch(root),
        languages=detect_languages(root),
    )


def clone_repository(remote: str, destination_root: Path) -> Project:
    name = _remote_name(remote)
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / name
    if destination.exists():
        raise GitError(f"Destination already exists: {destination}")

    try:
        _run(None, "clone", "--", remote, str(destination), timeout=120)
        return inspect_project(destination, source_url=remote)
    except Exception:
        if destination.is_dir():
            shutil.rmtree(destination, ignore_errors=True)
        raise


@contextmanager
def materialized_tree(path: Path, ref: str) -> Iterator[Path]:
    """Extract a Git ref into a temporary read-only analysis tree."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "archive", "--format=tar", ref],
            check=False,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise GitError("Git is not installed or is not available on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("Git did not finish within 30 seconds.") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(detail or f"Could not materialize Git ref: {ref}")

    with tempfile.TemporaryDirectory(prefix="revai-review-") as directory:
        destination = Path(directory)
        with tarfile.open(fileobj=BytesIO(result.stdout), mode="r:") as archive:
            archive.extractall(destination, filter="data")
        yield destination


def diff_preview(
    path: Path,
    base: str,
    head: str,
    *,
    patch_limit_bytes: int | None = _PATCH_LIMIT_BYTES,
) -> DiffPreview:
    _verify_ref(path, base)
    _verify_ref(path, head)
    comparison = "HEAD" if base == head else f"{base}...{head}"

    patch = _run(
        path,
        "diff",
        "--no-ext-diff",
        "--find-renames",
        "--no-color",
        comparison,
    )
    numstat = _run(path, "diff", "--numstat", comparison)
    if base == head:
        untracked_patch, untracked_numstat = _untracked_diff(path)
        patch += untracked_patch
        numstat += untracked_numstat

    files = [_parse_numstat(line) for line in numstat.splitlines() if line]
    additions = sum(item.additions for item in files)
    deletions = sum(item.deletions for item in files)
    estimated_tokens = math.ceil(len(patch) / 4) if patch else 0
    estimated_cost = round(
        estimated_tokens * _ESTIMATED_INPUT_USD_PER_MILLION_TOKENS / 1_000_000,
        6,
    )

    encoded = patch.encode("utf-8")
    truncated = patch_limit_bytes is not None and len(encoded) > patch_limit_bytes
    if truncated:
        patch = encoded[:patch_limit_bytes].decode("utf-8", errors="ignore")

    return DiffPreview(
        base=base,
        head=head,
        files=files,
        additions=additions,
        deletions=deletions,
        estimated_tokens=estimated_tokens,
        estimated_cost_usd=estimated_cost,
        patch=patch,
        truncated=truncated,
    )


def _verify_ref(path: Path, ref: str) -> None:
    try:
        _run(path, "rev-parse", "--verify", f"{ref}^{{commit}}")
    except GitError as exc:
        raise GitError(f"Unknown Git branch or ref: {ref}") from exc


def _parse_numstat(line: str) -> DiffFile:
    additions, deletions, filename = line.split("\t", 2)
    if " => " in filename:
        filename = filename.rsplit(" => ", 1)[-1]
    binary = additions == "-" or deletions == "-"
    return DiffFile(
        path=filename,
        additions=0 if binary else int(additions),
        deletions=0 if binary else int(deletions),
        binary=binary,
    )


def _untracked_diff(path: Path) -> tuple[str, str]:
    output = _run(path, "ls-files", "--others", "--exclude-standard", "-z")
    filenames = [filename for filename in output.split("\0") if filename]
    patches: list[str] = []
    stats: list[str] = []

    for filename in filenames:
        patches.append(
            _run(
                path,
                "diff",
                "--no-index",
                "--no-color",
                "--",
                os.devnull,
                filename,
                allowed_returncodes=(0, 1),
            )
        )
        stats.append(
            _run(
                path,
                "diff",
                "--no-index",
                "--numstat",
                "--",
                os.devnull,
                filename,
                allowed_returncodes=(0, 1),
            )
        )

    return "".join(patches), "".join(stats)


def _remote_name(remote: str) -> str:
    cleaned = remote.rstrip("/").removesuffix(".git")
    raw = cleaned.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    safe = "".join(character for character in raw if character.isalnum() or character in "-_.")
    if not safe or safe in {".", ".."}:
        raise GitError("Could not derive a repository name from that remote URL.")
    return safe[:80]
