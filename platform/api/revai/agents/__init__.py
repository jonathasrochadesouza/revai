"""The RevAI review agent: AGENTS.md generation, install, and report rendering."""

from revai.agents.generator import collect_rules, compose_block, compose_document
from revai.agents.installer import install, preview_document
from revai.agents.renderer import render_report

__all__ = [
    "collect_rules",
    "compose_block",
    "compose_document",
    "install",
    "preview_document",
    "render_report",
]
