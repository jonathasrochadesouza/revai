"""Apply a finding's suggested patch to the working tree, then re-check it.

The contract this module enforces, in order:

1. Preconditions — patch exists, target file matches the state the review saw
   (recorded content hash), the active branch is the review's head, and the
   patch is still applicable per ``git apply --check``.
2. Apply — unstaged, via Git; never staged, never committed.
3. Re-validate — when the finding came from a deterministic analyzer, that
   same analyzer re-runs on the touched file and the finding's rule must not
   fire anymore.
4. Revert on failure — original bytes are restored, the working tree ends the
   call exactly as it started, and the error is raised with a stable key.

Nothing in here touches the index or creates commits. The user owns the tree;
RevAI only leaves a reviewed-or-reverted diff in it.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from revai.analyzers.runner import run_analyzers
from revai.domain.enums import FindingSource, FixState
from revai.domain.models import (
    AnalyzerConfig,
    Finding,
    Project,
    Review,
    SonarQubeConfig,
)
from revai.errors import RevaiError
from revai.git.repo import GitError, apply_patch, current_branch

_SOURCES_WITH_RECHECK: dict[FindingSource, str] = {
    FindingSource.RUFF: "ruff",
    FindingSource.ESLINT: "eslint",
    FindingSource.SEMGREP: "semgrep",
    FindingSource.SECURITY: "security",
}


class FixPreview(BaseModel):
    """A dry run: what would be applied, without touching the tree."""

    dry_run: bool = True
    patch: str
    files: list[str]


class FixResult(BaseModel):
    """The outcome of an applied fix."""

    dry_run: bool = False
    patch: str
    files: list[str]
    validation: str
    """``validated`` (analyzer re-ran clean), ``unverified`` (no analyzer
    mapping, or the tool was unavailable) — a failed re-validation raises
    instead of returning."""


async def apply_finding_fix(
    project: Project,
    review: Review,
    finding: Finding,
    *,
    dry_run: bool = False,
    patch: str | None = None,
) -> FixPreview | FixResult:
    """Run the full precondition → apply → re-validate pipeline for one finding.

    ``patch`` overrides the finding's stored ``suggested_patch`` — used when a
    freshly generated fix is applied before it is persisted anywhere.
    """
    repository = Path(project.path)
    patch = patch or finding.suggested_patch
    if not patch:
        raise RevaiError(422, "fix.no_patch_available", {"finding_id": finding.id})
    if finding.fix_state is FixState.APPLIED:
        raise RevaiError(409, "fix.already_applied", {"finding_id": finding.id})

    active = current_branch(repository)
    if review.head_branch and active and active != review.head_branch:
        raise RevaiError(
            409,
            "fix.branch_mismatch",
            {"review_head": review.head_branch, "current_branch": active},
        )

    files = _patch_files(patch)
    if finding.file not in files:
        raise RevaiError(
            422,
            "fix.patch_file_mismatch",
            {"finding_file": finding.file, "patch_files": files},
        )

    target = repository / finding.file
    if not target.is_file():
        raise RevaiError(422, "fix.file_missing", {"file": finding.file})

    recorded = review.file_hashes.get(finding.file)
    if recorded is not None and _file_sha256(target) != recorded:
        raise RevaiError(409, "fix.file_changed", {"file": finding.file})

    try:
        apply_patch(repository, patch, check=True)
    except GitError as exc:
        status = 409 if exc.error_key == "fix.patch_stale" else 422
        raise RevaiError(status, exc.error_key, exc.params) from exc

    if dry_run:
        return FixPreview(patch=patch, files=files)

    backups: dict[str, bytes] = {}
    for path in files:
        candidate = repository / path
        if candidate.is_file():
            backups[path] = candidate.read_bytes()

    try:
        apply_patch(repository, patch)
    except GitError as exc:
        _restore(repository, backups)
        raise RevaiError(422, exc.error_key, exc.params) from exc

    validation, ok = await _revalidate(repository, finding)
    if not ok:
        _restore(repository, backups)
        raise RevaiError(422, "fix.validation_failed", {"detail": validation, "file": finding.file})

    finding.fix_state = FixState.APPLIED
    finding.fix_applied_at = datetime.now(UTC)
    finding.fix_validation = validation
    return FixResult(patch=patch, files=files, validation=validation)


def _patch_files(patch: str) -> list[str]:
    """Repo-relative paths a unified diff touches, in order of appearance."""
    files: list[str] = []
    for line in patch.splitlines():
        if not line.startswith("+++ "):
            continue
        raw = line[4:].split("\t")[0].strip()
        if raw == "/dev/null":
            continue
        if raw.startswith("b/"):
            raw = raw[2:]
        if raw and raw not in files:
            files.append(raw)
    return files


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _restore(repository: Path, backups: dict[str, bytes]) -> None:
    """Put every touched file back; a failed revert is raised, never swallowed."""
    for path, content in backups.items():
        try:
            (repository / path).write_bytes(content)
        except OSError as exc:
            raise RevaiError(500, "fix.revert_failed", {"file": path}) from exc


async def _revalidate(repository: Path, finding: Finding) -> tuple[str, bool]:
    """Re-run the analyzer that produced the finding; fail if its rule persists.

    Returns ``(validation_text, ok)``. Only sources with a mapped analyzer are
    re-checked; everything else is reported as ``unverified`` rather than
    pretending a validation happened.
    """
    flag = _SOURCES_WITH_RECHECK.get(FindingSource(finding.source))
    if flag is None:
        return "unverified (no analyzer mapping for this finding source)", True

    minimal = AnalyzerConfig(
        security=False,
        semgrep=False,
        ruff=False,
        eslint=False,
        gitleaks=False,
        checkstyle=False,
        project_tests=False,
        project_build=False,
        treesitter=False,
        sonarqube=SonarQubeConfig(enabled=False),
    )
    setattr(minimal, flag, True)
    runs = await run_analyzers(repository, [finding.file], minimal)
    run = runs[0] if runs else None
    if run is None or run.status in {"skipped", "unavailable"}:
        return f"unverified ({flag} was not available)", True
    if run.status == "failed":
        # Most commonly: the applied patch left the file in a state the tool
        # cannot even parse.
        return f"{flag} failed after the patch: {run.detail or 'no detail'}", False

    expected = (finding.rule_id or finding.title).lower()
    still_firing = [
        item.rule_id or item.title
        for item in run.findings
        if item.file == finding.file and (item.rule_id or item.title).lower() == expected
    ]
    if still_firing:
        return f"patch did not resolve {finding.rule_id or finding.title}", False
    return f"validated ({flag} clean)", True
