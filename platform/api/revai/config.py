"""Runtime settings.

Every value can be overridden with a ``REVAI_`` prefixed environment variable,
which is what makes the app testable without touching the real home directory.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, resolved once per process."""

    model_config = SettingsConfigDict(
        env_prefix="REVAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- identity -----------------------------------------------------------
    app_name: str = "RevAI Platform"
    version: str = "3.0.0a0"
    environment: str = Field(default="development")

    # --- network ------------------------------------------------------------
    # Bound to loopback on purpose: this is a single-user local tool with no
    # authentication, so it must never be reachable from the network.
    #
    # 8799 rather than a rounder number because 8787 and its neighbours are
    # commonly taken by JVM tooling and debug agents.
    host: str = "127.0.0.1"
    port: int = 8799

    # Origins allowed to call the API. The web app dev server runs on 3000.
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # --- storage ------------------------------------------------------------
    # Overridable so tests can point at a temporary directory.
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".revai")

    @field_validator("data_dir", mode="after")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @property
    def config_file(self) -> Path:
        return self.data_dir / "config.yaml"

    @property
    def credentials_file(self) -> Path:
        return self.data_dir / "credentials.yaml"

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def reviews_dir(self) -> Path:
        return self.data_dir / "reviews"

    @property
    def rules_dir(self) -> Path:
        return self.data_dir / "rules"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    def ensure_dirs(self) -> None:
        """Create the data directories if they are missing.

        Phase 1 will own reading and writing the files themselves; here we only
        guarantee the tree exists so later phases never have to check.
        """
        for path in (
            self.data_dir,
            self.projects_dir,
            self.reviews_dir,
            self.rules_dir,
            self.cache_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance.

    Used as a FastAPI dependency, so overriding it in tests is a one-liner.
    """
    return Settings()
