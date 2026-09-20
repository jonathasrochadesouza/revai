"""Installed marketplace skills and how they compose into review prompts.

A skill is third-party procedural knowledge, discovered on the skills.sh
marketplace and installed by copying the body of its ``SKILL.md`` into
``skills.yaml``. Two rules shape everything here:

* **Content is pinned at install time.** The body text and its SHA-256 are
  stored locally, so reviews are reproducible and work offline, and an upstream
  edit can never silently change what the model is told. Upgrades are manual.
* **Skills are instructions, not code.** Only the ``SKILL.md`` body is ever
  used — ``scripts/`` and other support files from a skill folder are never
  fetched or executed. Composing appends each skill as a clearly labelled
  section onto the base prompts; the anti-injection guard and the payload
  sentinel live in :mod:`revai.domain.prompts` and are outside the user's —
  and therefore any skill's — reach.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from revai.domain.models import _Base, _Document, _now

SkillFocus = Literal["review", "fix", "both"]

MAX_INSTALLED_SKILLS = 50
MAX_ENABLED_SKILLS = 10
MAX_SKILL_BODY_CHARS = 40_000
MAX_COMPOSED_SKILL_CHARS = 50_000

# SKILL.md name rules (agentskills.io spec): lowercase letters, digits and
# hyphens, ≤64 chars, no leading/trailing/consecutive hyphens.
SKILL_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
# Marketplace source is the GitHub shorthand "owner/repo" used by skills.sh.
SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


def new_skill_install_id() -> str:
    """A short identifier for one install record, in the house style."""
    return uuid.uuid4().hex[:12]


class InstalledSkill(_Base):
    """One marketplace skill copied into ``skills.yaml``.

    ``id`` is the skill's marketplace slug (the SKILL.md ``name``), stable
    across versions; the row is unique by it. ``body`` is the SKILL.md content
    below the frontmatter, pinned exactly as fetched at install time.
    """

    id: str = Field(pattern=SKILL_ID_PATTERN.pattern, max_length=64)
    source: str = Field(pattern=SOURCE_PATTERN.pattern)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    focus: SkillFocus = "both"
    enabled: bool = True
    body: str = Field(min_length=1, max_length=MAX_SKILL_BODY_CHARS)
    content_sha256: str = Field(min_length=64, max_length=64)
    license: str | None = Field(default=None, max_length=200)
    installs: int | None = Field(default=None, ge=0)
    source_url: str = Field(default="", max_length=500)
    installed_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    @field_validator("content_sha256")
    @classmethod
    def _sha_is_hex(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("content_sha256 must be lowercase hex sha256")
        return value

    def applies_to_review(self) -> bool:
        return self.focus in ("review", "both")

    def applies_to_fix(self) -> bool:
        return self.focus in ("fix", "both")

    @staticmethod
    def sha256(body: str) -> str:
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


class SkillSettings(_Document):
    """``~/.revai/skills.yaml``.

    Every field defaults, so a missing file means "no skills installed" rather
    than a startup failure — the same rule as ``prompts.yaml``.
    """

    skills: list[InstalledSkill] = Field(default_factory=list)

    def get(self, skill_id: str) -> InstalledSkill | None:
        return next((skill for skill in self.skills if skill.id == skill_id), None)

    def remove(self, skill_id: str) -> bool:
        before = len(self.skills)
        self.skills = [skill for skill in self.skills if skill.id != skill_id]
        return len(self.skills) < before

    def enabled_skills(self) -> list[InstalledSkill]:
        """Enabled skills in deterministic order — composition must not jitter."""
        return sorted((skill for skill in self.skills if skill.enabled), key=lambda s: s.id)


def enabled_counts(skills: Iterable[InstalledSkill]) -> tuple[int, int]:
    """How many skills an enabled set has, and the characters they add."""
    total_chars = 0
    count = 0
    for skill in skills:
        if not skill.enabled:
            continue
        count += 1
        total_chars += len(skill.body)
    return count, total_chars


def _append_section(text: str, heading: str, body: str) -> str:
    return f"{text.rstrip()}\n\n## {heading}\n{body.strip()}"


def compose_prompts(
    base_prompt: tuple[str, str],
    skills: Sequence[InstalledSkill],
) -> tuple[str, str]:
    """Append enabled skill bodies to the base ``(system, user)`` prompts.

    Review-scope skills extend the system prompt; fix-scope skills extend the
    user instructions, which sit *before* the payload sentinel inside
    :func:`revai.pipeline.ai._user_prompt` — so no skill can move or remove the
    untrusted-data boundary. Disabled skills are skipped here as well as at
    the call sites, so a stale list can never leak into a prompt; order is
    whatever the caller supplies, and the caps are enforced where skills are
    mutated, keeping this a pure function.
    """
    system_prompt, user_prompt = base_prompt
    for skill in skills:
        if not skill.enabled:
            continue
        if skill.applies_to_review():
            system_prompt = _append_section(
                system_prompt, f"Skill: {skill.name} (from skills.sh)", skill.body
            )
        if skill.applies_to_fix():
            user_prompt = _append_section(
                user_prompt,
                f"Patch guidance — skill: {skill.name} (from skills.sh)",
                skill.body,
            )
    return system_prompt, user_prompt


def composed_skill_chars(skills: Sequence[InstalledSkill]) -> int:
    """Characters the skills will add to the prompts when composed."""
    return sum(len(skill.body) for skill in skills)
