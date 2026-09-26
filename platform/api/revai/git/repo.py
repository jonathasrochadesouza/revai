"""Read-only Git operations used by the Phase 3 project workspace.

The only write operation is :func:`apply_patch`, which stages a user-initiated
finding fix into the working tree (never staged, never committed); the user
reviews it with ``git diff`` and decides what to do with it.
"""

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
from typing import Any

from revai.domain.enums import ProjectKind
from revai.domain.models import Project
from revai.shell import command_for_execution

_GIT_TIMEOUT_SECONDS = 30
_PATCH_LIMIT_BYTES = 1_000_000
_ESTIMATED_INPUT_USD_PER_MILLION_TOKENS = 3.0
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

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
    """A user-actionable Git failure.

    Carries a namespaced ``error_key`` and structured ``params`` so a route
    handler can translate it into the API's error contract without
    forwarding raw stderr as the primary message text.
    """

    def __init__(self, error_key: str, params: dict[str, Any] | None = None) -> None:
        self.error_key = error_key
        self.params = params or {}
        super().__init__(error_key)


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
        execution, environment = command_for_execution(command)
        result = subprocess.run(
            execution,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise GitError("git.not_installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("git.timed_out", {"timeout_s": timeout}) from exc

    if result.returncode not in allowed_returncodes:
        detail = result.stderr.strip() or result.stdout.strip() or "Git command failed."
        raise GitError("git.command_failed", {"detail": detail})
    return result.stdout


def apply_patch(repository: Path, patch: str, *, check: bool = False) -> None:
    """Apply a unified diff to the working tree, unstaged.

    ``check=True`` performs Git's own dry run: everything validates (context
    matches, target file is in the expected state) without touching a byte.
    The patch travels on stdin so an oversized or hostile patch cannot become
    an argument.
    """
    command = ["git", "-C", str(repository), "apply"]
    if check:
        command.append("--check")
    command.extend(["--whitespace=nowarn", "--recount", "-"])

    # Persisted fields are whitespace-stripped, which can amputate a diff's
    # final newline; Git calls that a corrupt patch. A trailing newline is
    # always syntactically recoverable, so repair it before handing over.
    if patch and not patch.endswith("\n"):
        patch += "\n"

    try:
        execution, environment = command_for_execution(command)
        result = subprocess.run(
            execution,
            check=False,
            input=patch.encode("utf-8"),
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise GitError("git.not_installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("git.timed_out", {"timeout_s": _GIT_TIMEOUT_SECONDS}) from exc

    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        key = "fix.patch_stale" if check else "fix.patch_apply_failed"
        raise GitError(key, {"detail": detail[:400]})


def repository_root(path: Path) -> Path:
    if not path.exists() or not path.is_dir():
        raise GitError("git.folder_does_not_exist", {"path": str(path)})
    try:
        root = _run(path, "rev-parse", "--show-toplevel").strip()
    except GitError as exc:
        raise GitError("git.not_a_repository", {"path": str(path)}) from exc
    return Path(root).resolve()


def branches(path: Path) -> list[str]:
    output = _run(
        path,
        "for-each-ref",
        "--format=%(refname:short)%09%(symref)",
        "--sort=refname",
        "refs/heads",
        "refs/remotes",
    )
    return sorted(
        {
            line.split("\t", 1)[0]
            for line in output.splitlines()
            if line and not line.partition("\t")[2]
        }
    )


def current_branch(path: Path) -> str | None:
    branch = _run(path, "branch", "--show-current").strip()
    return branch or None


def review_identities(path: Path, ref: str) -> tuple[str, str]:
    """Return commit author and local reviewer identity without changing Git state."""
    _verify_ref(path, ref)
    author = _run(path, "show", "-s", "--format=%an <%ae>", ref).strip() or "Undefined"
    name = _run(
        path,
        "config",
        "--get",
        "user.name",
        allowed_returncodes=(0, 1),
    ).strip()
    email = _run(
        path,
        "config",
        "--get",
        "user.email",
        allowed_returncodes=(0, 1),
    ).strip()
    reviewer = f"{name} <{email}>" if name and email else name or email or "Undefined"
    return author, reviewer


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
    command, environment = command_for_execution(
        ["git", "-C", str(path), "config", "--get", "remote.origin.url"]
    )
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_GIT_TIMEOUT_SECONDS,
        env=environment,
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
    raise GitError("git.no_commits_or_branches", {"path": str(path)})


def inspect_project(
    path: Path, *, source_url: str | None = None, kind: ProjectKind = ProjectKind.LOCAL_OPEN
) -> Project:
    root = repository_root(path)
    return Project(
        name=root.name,
        kind=kind,
        path=None if kind is ProjectKind.CLOUD else str(root),
        remote_url=source_url or remote_url(root),
        base_branch=detect_base_branch(root),
        languages=detect_languages(root),
    )


def clone_repository(remote: str, destination_root: Path) -> Project:
    name = _remote_name(remote)
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / name
    if destination.exists():
        raise GitError("git.destination_already_exists", {"destination": str(destination)})

    try:
        _run(None, "clone", "--", remote, str(destination), timeout=120)
        return inspect_project(destination, source_url=remote, kind=ProjectKind.LOCAL_CLONE)
    except Exception:
        if destination.is_dir():
            shutil.rmtree(destination, ignore_errors=True)
        raise


@contextmanager
def ephemeral_clone(remote: str) -> Iterator[Path]:
    """Clone ``remote`` into a temp directory for the caller's duration only.

    Sibling to :func:`materialized_tree`: same "clone/extract, hand over a
    ``Path``, delete on any exit" shape, one level up — the whole repository
    rather than a single ref. Used for cloud projects, which never keep a
    persistent working tree; every review run (and the one-shot peek at
    creation time) clones fresh and this guarantees cleanup even when the
    caller raises or is cancelled, because ``TemporaryDirectory.__exit__``
    always runs.

    No ``--depth``: a shallow clone can miss the merge base needed for
    ``git diff base..head``, and the whole point of this project kind is
    still doing a normal branch-diff review.

    ``git clone`` only creates local branches for the remote's default one;
    every other head exists merely as ``origin/<branch>``. A cloud review
    addresses branches the way a local project does (``git diff main..head``
    against plain branch names), so every remote head is materialised as a
    local branch before the clone is handed over.
    """
    with tempfile.TemporaryDirectory(prefix="revai-cloud-") as directory:
        destination = Path(directory) / _remote_name(remote)
        _run(None, "clone", "--", remote, str(destination), timeout=120)
        # The clone already has HEAD's branch as a local branch; force-fetching
        # it would be refused ("fetch into current branch"), so it is excluded
        # and every other remote head is materialised as a local branch.
        head = current_branch(destination) or ""
        _run(
            destination,
            "fetch",
            "--prune",
            "origin",
            "+refs/heads/*:refs/heads/*",
            f"^{f'refs/heads/{head}' if head else 'refs/heads/none'}",
            timeout=120,
        )
        yield destination


@contextmanager
def materialized_tree(path: Path, ref: str) -> Iterator[Path]:
    """Extract a Git ref into a temporary read-only analysis tree."""
    try:
        command, environment = command_for_execution(
            ["git", "-C", str(path), "archive", "--format=tar", ref]
        )
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise GitError("git.not_installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("git.timed_out", {"timeout_s": _GIT_TIMEOUT_SECONDS}) from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitError("git.materialize_ref_failed", {"ref": ref, "detail": detail})

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


def snapshot_preview(
    path: Path,
    head: str,
    *,
    selected_files: list[str] | None = None,
) -> DiffPreview:
    """Represent tracked content as additions for whole-project/selected-file review."""
    _verify_ref(path, head)
    args = [_EMPTY_TREE, head]
    if selected_files:
        known = set(tracked_files(path, head))
        unknown = sorted(set(selected_files) - known)
        if unknown:
            raise GitError("git.files_not_tracked", {"ref": head, "files": unknown})
        args.extend(["--", *selected_files])
    patch = _run(
        path,
        "diff",
        "--no-ext-diff",
        "--no-color",
        "--find-renames",
        *args,
    )
    numstat = _run(path, "diff", "--numstat", *args)
    files = [_parse_numstat(line) for line in numstat.splitlines() if line]
    additions = sum(item.additions for item in files)
    deletions = sum(item.deletions for item in files)
    estimated_tokens = math.ceil(len(patch) / 4) if patch else 0
    return DiffPreview(
        base="<empty-tree>",
        head=head,
        files=files,
        additions=additions,
        deletions=deletions,
        estimated_tokens=estimated_tokens,
        estimated_cost_usd=round(
            estimated_tokens * _ESTIMATED_INPUT_USD_PER_MILLION_TOKENS / 1_000_000,
            6,
        ),
        patch=patch,
        truncated=False,
    )


def _verify_ref(path: Path, ref: str) -> None:
    try:
        _run(path, "rev-parse", "--verify", f"{ref}^{{commit}}")
    except GitError as exc:
        raise GitError("git.unknown_ref", {"ref": ref}) from exc


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
        raise GitError("git.cannot_derive_repository_name", {"remote": remote})
    return safe[:80]
