"""Concrete YAML repositories.

Layout on disk:

    ~/.revai/
    ├── config.yaml                  RevaiConfig      (single document)
    ├── credentials.yaml             Credentials      (single document, chmod 600)
    ├── projects/<id>.yaml           Project          (collection)
    └── reviews/<project_id>/<id>.yaml   Review       (collection, partitioned)

Reviews are partitioned by project so deleting a project is a directory removal,
and so a project with hundreds of reviews never slows down listing another one.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import sys
from pathlib import Path

from revai.config import Settings
from revai.domain.models import Credentials, Project, RevaiConfig, Review
from revai.storage.base import StorageError
from revai.storage.yaml_store import YamlStore

logger = logging.getLogger(__name__)


def _restrict_permissions(path: Path) -> None:
    """Make a file readable only by its owner.

    ``chmod 600`` is meaningful on POSIX. On Windows the bit has no equivalent, so
    this is a documented no-op there rather than a silent lie — the credentials
    file still lives outside any project folder, which is the protection that
    actually matters against committing a secret.
    """
    if sys.platform == "win32":
        return
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        logger.warning("could not restrict permissions on %s", path, exc_info=True)


# ===========================================================================
# Single-document repositories
# ===========================================================================


class ConfigRepository:
    """``config.yaml``. A missing file means "all defaults", never an error."""

    def __init__(self, settings: Settings) -> None:
        self._path = settings.config_file
        self._store: YamlStore[RevaiConfig] = YamlStore(RevaiConfig)

    def load(self) -> RevaiConfig:
        return self._store.read(self._path) or RevaiConfig()

    def save(self, document: RevaiConfig) -> RevaiConfig:
        return self._store.write(self._path, document)

    def exists(self) -> bool:
        return self._path.is_file()

    @property
    def path(self) -> Path:
        return self._path


class CredentialsRepository:
    """``credentials.yaml``. Tightened permissions on every write."""

    def __init__(self, settings: Settings) -> None:
        self._path = settings.credentials_file
        self._store: YamlStore[Credentials] = YamlStore(Credentials)

    def load(self) -> Credentials:
        return self._store.read(self._path) or Credentials()

    def save(self, document: Credentials) -> Credentials:
        saved = self._store.write(self._path, document)
        _restrict_permissions(self._path)
        return saved

    def exists(self) -> bool:
        return self._path.is_file()

    @property
    def path(self) -> Path:
        return self._path


# ===========================================================================
# Collection repositories
# ===========================================================================


class ProjectRepository:
    """One file per project, named by id."""

    def __init__(self, settings: Settings) -> None:
        self._dir = settings.projects_dir
        self._reviews_dir = settings.reviews_dir
        self._store: YamlStore[Project] = YamlStore(Project)

    def _path(self, project_id: str) -> Path:
        return self._dir / f"{_safe(project_id)}.yaml"

    def get(self, entity_id: str) -> Project | None:
        return self._store.read(self._path(entity_id))

    def list(self) -> list[Project]:
        """Newest first.

        A single unreadable file must not hide every other project, so parse
        failures are logged and skipped rather than raised.
        """
        if not self._dir.is_dir():
            return []

        projects: list[Project] = []
        for path in sorted(self._dir.glob("*.yaml")):
            try:
                project = self._store.read(path)
            except StorageError:
                logger.warning("skipping unreadable project %s", path.name, exc_info=True)
                continue
            if project is not None:
                projects.append(project)

        return sorted(projects, key=lambda p: p.created_at, reverse=True)

    def save(self, entity: Project) -> Project:
        return self._store.write(self._path(entity.id), entity)

    def delete(self, entity_id: str) -> bool:
        """Remove the project and every review belonging to it."""
        path = self._path(entity_id)
        if not path.is_file():
            return False

        path.unlink()

        # Orphaned reviews would otherwise accumulate forever.
        review_dir = self._reviews_dir / _safe(entity_id)
        if review_dir.is_dir():
            shutil.rmtree(review_dir, ignore_errors=True)

        return True

    def exists(self, entity_id: str) -> bool:
        return self._path(entity_id).is_file()


class ReviewRepository:
    """Reviews, partitioned into one directory per project."""

    def __init__(self, settings: Settings) -> None:
        self._dir = settings.reviews_dir
        self._store: YamlStore[Review] = YamlStore(Review)

    def _project_dir(self, project_id: str) -> Path:
        return self._dir / _safe(project_id)

    def _path(self, project_id: str, review_id: str) -> Path:
        return self._project_dir(project_id) / f"{_safe(review_id)}.yaml"

    def get(self, entity_id: str, project_id: str | None = None) -> Review | None:
        """Fetch a review.

        Passing ``project_id`` turns this into a direct file read. Without it we
        have to scan the partitions, which is fine for a local tool but is why the
        API always carries the project id.
        """
        if project_id is not None:
            return self._store.read(self._path(project_id, entity_id))

        if not self._dir.is_dir():
            return None

        filename = f"{_safe(entity_id)}.yaml"
        for candidate in self._dir.glob(f"*/{filename}"):
            return self._store.read(candidate)
        return None

    def list(self, project_id: str | None = None) -> list[Review]:
        """Newest first, optionally scoped to one project."""
        pattern = f"{_safe(project_id)}/*.yaml" if project_id else "*/*.yaml"
        if not self._dir.is_dir():
            return []

        reviews: list[Review] = []
        for path in self._dir.glob(pattern):
            try:
                review = self._store.read(path)
            except StorageError:
                logger.warning("skipping unreadable review %s", path.name, exc_info=True)
                continue
            if review is not None:
                reviews.append(review)

        return sorted(reviews, key=lambda r: r.created_at, reverse=True)

    def save(self, entity: Review) -> Review:
        return self._store.write(self._path(entity.project_id, entity.id), entity)

    def delete(self, entity_id: str, project_id: str | None = None) -> bool:
        if project_id is not None:
            path = self._path(project_id, entity_id)
            if path.is_file():
                path.unlink()
                return True
            return False

        if not self._dir.is_dir():
            return False

        filename = f"{_safe(entity_id)}.yaml"
        for candidate in self._dir.glob(f"*/{filename}"):
            candidate.unlink()
            return True
        return False

    def exists(self, entity_id: str, project_id: str | None = None) -> bool:
        return self.get(entity_id, project_id) is not None


# ===========================================================================
# Helpers
# ===========================================================================

_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


def _safe(identifier: str) -> str:
    """Reject anything that could escape the data directory.

    Ids are generated internally, but they also arrive from URL path parameters.
    Validating here means a traversal attempt cannot reach the filesystem even if
    a future route forgets to check.
    """
    if not identifier:
        raise StorageError("storage.empty_identifier")
    if not set(identifier) <= _ALLOWED:
        raise StorageError("storage.invalid_identifier_characters", {"identifier": identifier})
    return identifier
