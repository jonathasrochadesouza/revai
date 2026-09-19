"""Fix-application service: preconditions, apply, re-validate, revert."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from revai.domain.enums import FindingSource, FindingStatus, ReviewScope
from revai.domain.models import Finding, Project, Review
from revai.errors import RevaiError
from revai.fixes.service import FixPreview, FixResult, apply_finding_fix

_F401_PATCH = "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,2 @@\n-import os\n \n answer = 42\n"


def _git(path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _repository(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "fix@example.com")
    _git(path, "config", "user.name", "Fix Test")
    (path / "app.py").write_text("import os\n\nanswer = 42\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "initial")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finding(**overrides: object) -> Finding:
    base = {
        "severity": "medium",
        "category": "maintainability",
        "title": "Unused import",
        "description": "os is imported and never used.",
        "file": "app.py",
        "line_start": 1,
        "source": FindingSource.RUFF,
        "rule_id": "F401",
        "suggested_patch": _F401_PATCH,
    }
    base.update(overrides)
    return Finding(**base)  # type: ignore[arg-type]


def _review(path: Path, finding: Finding, head_branch: str = "main") -> Review:
    return Review(
        project_id="p1",
        scope=ReviewScope.BRANCH_DIFF,
        base_branch="main",
        head_branch=head_branch,
        findings=[finding],
        file_hashes={"app.py": _sha(path / "app.py")},
    )


def _project(path: Path) -> Project:
    return Project(name="demo", path=str(path))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return _repository(tmp_path / "demo")


async def test_dry_run_previews_and_does_not_touch_the_tree(repo: Path) -> None:
    finding = _finding()

    result = await apply_finding_fix(
        _project(repo), _review(repo, finding), finding, dry_run=True
    )

    assert isinstance(result, FixPreview)
    assert result.files == ["app.py"]
    assert (repo / "app.py").read_text(encoding="utf-8") == "import os\n\nanswer = 42\n"
    assert finding.fix_state == "none"


async def test_apply_removes_the_import_and_validates_with_ruff(repo: Path) -> None:
    finding = _finding()

    result = await apply_finding_fix(_project(repo), _review(repo, finding), finding)

    assert isinstance(result, FixResult)
    assert result.validation == "validated (ruff clean)"
    assert (repo / "app.py").read_text(encoding="utf-8") == "\nanswer = 42\n"
    assert finding.fix_state == "applied"
    assert finding.fix_applied_at is not None


async def test_second_apply_is_rejected(repo: Path) -> None:
    finding = _finding()
    review = _review(repo, finding)
    await apply_finding_fix(_project(repo), review, finding)

    with pytest.raises(RevaiError) as caught:
        await apply_finding_fix(_project(repo), review, finding)

    assert caught.value.error_key == "fix.already_applied"


async def test_branch_mismatch_blocks_the_apply(repo: Path) -> None:
    finding = _finding()

    with pytest.raises(RevaiError) as caught:
        await apply_finding_fix(
            _project(repo), _review(repo, finding, head_branch="feature"), finding
        )

    assert caught.value.error_key == "fix.branch_mismatch"


async def test_file_changed_since_review_blocks_the_apply(repo: Path) -> None:
    finding = _finding()
    review = _review(repo, finding)
    (repo / "app.py").write_text("import os\n\nanswer = 43\n", encoding="utf-8")

    with pytest.raises(RevaiError) as caught:
        await apply_finding_fix(_project(repo), review, finding)

    assert caught.value.error_key == "fix.file_changed"


async def test_finding_without_patch_is_rejected(repo: Path) -> None:
    finding = _finding(suggested_patch=None)

    with pytest.raises(RevaiError) as caught:
        await apply_finding_fix(_project(repo), _review(repo, finding), finding)

    assert caught.value.error_key == "fix.no_patch_available"


async def test_patch_whose_target_drifted_is_stale(repo: Path) -> None:
    # Hash matches (the review captured the same bytes), but the patch expects
    # content the file does not have.
    finding = _finding(
        suggested_patch="--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,2 @@\n-import io\n \n answer = 42\n"
    )

    with pytest.raises(RevaiError) as caught:
        await apply_finding_fix(_project(repo), _review(repo, finding), finding)

    assert caught.value.error_key == "fix.patch_stale"
    assert (repo / "app.py").read_text(encoding="utf-8") == "import os\n\nanswer = 42\n"


async def test_revalidation_failure_reverts_the_tree(repo: Path) -> None:
    # The patch applies cleanly but does not resolve the finding (the import
    # stays), so ruff must still fire F401 and the change must be reverted.
    finding = _finding(
        suggested_patch=(
            "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,3 @@\n"
            " import os\n \n-answer = 42\n+answer = 43\n"
        )
    )

    with pytest.raises(RevaiError) as caught:
        await apply_finding_fix(_project(repo), _review(repo, finding), finding)

    assert caught.value.error_key == "fix.validation_failed"
    assert (repo / "app.py").read_text(encoding="utf-8") == "import os\n\nanswer = 42\n"
    assert finding.fix_state == "none"


async def test_ai_source_is_applied_without_analyzer_recheck(repo: Path) -> None:
    finding = _finding(source=FindingSource.AI, rule_id=None, title="Unused import")

    result = await apply_finding_fix(_project(repo), _review(repo, finding), finding)

    assert isinstance(result, FixResult)
    assert result.validation.startswith("unverified")
    assert (repo / "app.py").read_text(encoding="utf-8") == "\nanswer = 42\n"
    assert finding.fix_state == "applied"


async def test_missing_target_file_is_reported(repo: Path) -> None:
    finding = _finding(
        file="missing.py",
        suggested_patch=_F401_PATCH.replace("app.py", "missing.py"),
    )

    with pytest.raises(RevaiError) as caught:
        await apply_finding_fix(_project(repo), _review(repo, finding), finding)

    assert caught.value.error_key == "fix.file_missing"


async def test_status_is_untouched_by_apply(repo: Path) -> None:
    finding = _finding()

    await apply_finding_fix(_project(repo), _review(repo, finding), finding)

    # Applying a patch is not a user decision: the finding stays open until the
    # user marks it fixed (usually after committing).
    assert finding.status is FindingStatus.OPEN
