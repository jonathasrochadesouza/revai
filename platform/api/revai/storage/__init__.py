"""Persistence layer.

Everything above this package talks to :class:`Repository` and never touches a
file. Swapping YAML for MongoDB later means adding one module and changing the
wiring — no caller changes.
"""

from revai.storage.base import DocumentRepository, Repository, StorageError
from revai.storage.repositories import (
    ConfigRepository,
    CredentialsRepository,
    ProjectRepository,
    PromptRepository,
    ReviewRepository,
    SkillRepository,
)
from revai.storage.yaml_store import YamlStore, atomic_write

__all__ = [
    "ConfigRepository",
    "CredentialsRepository",
    "DocumentRepository",
    "ProjectRepository",
    "PromptRepository",
    "Repository",
    "ReviewRepository",
    "SkillRepository",
    "StorageError",
    "YamlStore",
    "atomic_write",
]
