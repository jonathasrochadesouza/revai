"""Ephemeral clone lifecycle, used by cloud projects.

``ephemeral_clone`` is the one new git primitive this feature needs: clone a
remote into a temp directory, hand the caller a `Path`, and guarantee the
directory is gone on any exit — success, exception, or otherwise.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from revai.git.repo import GitError, ephemeral_clone


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repository(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "cloud@example.com")
    _git(path, "config", "user.name", "Cloud Project")
    (path / "README.md").write_text("# Demo\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "initial")
    return path


def test_ephemeral_clone_yields_a_working_checkout(tmp_path: Path) -> None:
    source = _repository(tmp_path / "source")

    with ephemeral_clone(source.as_uri()) as checkout:
        assert checkout.is_dir()
        assert (checkout / ".git").is_dir()
        assert (checkout / "README.md").read_text(encoding="utf-8") == "# Demo\n"


def test_ephemeral_clone_removes_the_directory_after_a_normal_exit(tmp_path: Path) -> None:
    source = _repository(tmp_path / "source")
    captured: Path | None = None

    with ephemeral_clone(source.as_uri()) as checkout:
        captured = checkout

    assert captured is not None
    assert not captured.exists()
    assert not captured.parent.exists()


def test_ephemeral_clone_removes_the_directory_when_the_block_raises(tmp_path: Path) -> None:
    source = _repository(tmp_path / "source")
    captured: Path | None = None

    with pytest.raises(RuntimeError), ephemeral_clone(source.as_uri()) as checkout:
        captured = checkout
        raise RuntimeError("boom")

    assert captured is not None
    assert not captured.exists()


def test_ephemeral_clone_of_an_unreachable_remote_raises_git_error(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"

    with pytest.raises(GitError), ephemeral_clone(missing.as_uri()):
        pass


async def test_ephemeral_clone_removes_the_directory_when_its_task_is_cancelled(
    tmp_path: Path,
) -> None:
    """Cancelling the task running inside the `with` block unwinds through it
    exactly like any other exception — this is what makes cancelling a cloud
    project's review still clean up its ephemeral clone."""
    import asyncio

    source = _repository(tmp_path / "source")
    captured: Path | None = None
    started = asyncio.Event()

    async def run() -> None:
        nonlocal captured
        with ephemeral_clone(source.as_uri()) as checkout:
            captured = checkout
            started.set()
            await asyncio.sleep(10)

    task = asyncio.create_task(run())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert captured is not None
    assert not captured.exists()
