"""Writing the agent definition into the user's project.

RevAI writes exactly two files in the target project, both after an explicit
user action (CLI ``--yes``/interactive confirm or the Settings apply button):

* ``AGENTS.md`` — the managed RevAI block, merged or replaced idempotently.
  The first modification leaves a ``.revai-bak`` backup of the original.
* ``.revai/agent-report.html`` — the standalone report template the agent
  copies for every review.

Nothing else in the project is touched, and the API keys stay in
``~/.revai/credentials.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from revai.agents.generator import MARKER_BEGIN, MARKER_END, compose_document
from revai.agents.renderer import load_template

AGENTS_MD = "AGENTS.md"
AGENT_DIR = ".revai"
AGENT_TEMPLATE = "agent-report.html"
BACKUP_SUFFIX = ".revai-bak"


@dataclass(frozen=True)
class InstallResult:
    """What the installer did (or would do, for a dry run)."""

    agents_md: Path
    template: Path
    agents_md_created: bool
    backup_created: bool
    block_replaced: bool
    dry_run: bool


def preview_document(project_path: Path, block: str) -> tuple[str, bool]:
    """The merged AGENTS.md and whether it already exists on disk."""
    agents_md = project_path / AGENTS_MD
    existing = agents_md.read_text(encoding="utf-8") if agents_md.is_file() else None
    return compose_document(existing, block), existing is not None


def install(
    project_path: Path,
    block: str,
    *,
    dry_run: bool = False,
) -> InstallResult:
    """Merge the block into ``AGENTS.md`` and refresh the report template.

    ``dry_run`` performs every read and computes the result without writing.
    """
    project_path = project_path.resolve()
    if not project_path.is_dir():
        raise NotADirectoryError(f"not a directory: {project_path}")

    agents_md = project_path / AGENTS_MD
    template_path = project_path / AGENT_DIR / AGENT_TEMPLATE
    existing = agents_md.read_text(encoding="utf-8") if agents_md.is_file() else None
    document = compose_document(existing, block)
    block_replaced = existing is not None and MARKER_BEGIN in existing and MARKER_END in existing

    backup_created = False
    if not dry_run:
        if existing is not None:
            backup = agents_md.with_name(AGENTS_MD + BACKUP_SUFFIX)
            if not backup.exists():
                backup.write_text(existing, encoding="utf-8")
                backup_created = True
        agents_md.write_text(document, encoding="utf-8")
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(load_template(), encoding="utf-8")

    return InstallResult(
        agents_md=agents_md,
        template=template_path,
        agents_md_created=existing is None,
        backup_created=backup_created,
        block_replaced=block_replaced,
        dry_run=dry_run,
    )
