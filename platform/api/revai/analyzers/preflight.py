"""Fast, read-only analyzer capability checks used before a review starts."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from revai.domain.models import AnalyzerConfig, Project
from revai.shell import resolve_command


@dataclass(frozen=True)
class AnalyzerCapability:
    name: str
    status: str
    detail: str
    remediation: str | None = None


def preflight_analyzers(
    project: Project,
    config: AnalyzerConfig,
) -> list[AnalyzerCapability]:
    # Cloud projects have no persistent working tree to inspect outside of a
    # review run — `repository` stays `None` and every filesystem-dependent
    # check below degrades to "cannot be checked without running a review"
    # rather than crashing on a missing path.
    repository = Path(project.path) if project.path is not None else None
    checks: list[AnalyzerCapability] = []
    if config.security:
        supported = {"Python", "Java", "JavaScript", "TypeScript"} & set(project.languages)
        checks.append(
            AnalyzerCapability(
                "security",
                "ready" if supported else "unsupported",
                f"Built-in rules cover: {', '.join(sorted(supported))}."
                if supported
                else "No supported source language detected.",
            )
        )
    if config.ruff:
        checks.append(_module("ruff", "ruff", "Install the pipeline dependencies."))
    if config.eslint:
        ready = (
            repository is not None
            and (repository / "node_modules" / "eslint" / "bin" / "eslint.js").is_file()
        )
        checks.append(
            AnalyzerCapability(
                "eslint",
                "ready" if ready else "unavailable",
                "Project-local ESLint found." if ready else "Project-local ESLint was not found.",
                None if ready else "Run the project's package-manager install command.",
            )
        )
    if config.semgrep:
        executable = resolve_command("semgrep")
        rule = repository is not None and (
            (repository / ".semgrep.yml").is_file() or (repository / ".semgrep.yaml").is_file()
        )
        ready = bool(executable and rule)
        checks.append(
            AnalyzerCapability(
                "semgrep",
                "ready" if ready else "unavailable",
                "Semgrep and project rules found."
                if ready
                else "Semgrep executable or project rules are missing.",
                None if ready else "Install Semgrep and add .semgrep.yml.",
            )
        )
    if config.gitleaks:
        checks.append(_command("gitleaks", "gitleaks", "Install Gitleaks and add it to PATH."))
    if config.checkstyle:
        checks.append(_configured("checkstyle", project.checkstyle_command))
    if config.project_tests:
        checks.append(_configured("project_tests", project.test_command))
    if config.project_build:
        checks.append(_configured("project_build", project.build_command))
    if config.treesitter:
        checks.append(
            _module(
                "treesitter",
                "tree_sitter_language_pack",
                "Install RevAI pipeline dependencies.",
            )
        )
    return checks


def _module(name: str, module: str, remediation: str) -> AnalyzerCapability:
    ready = importlib.util.find_spec(module) is not None
    return AnalyzerCapability(
        name,
        "ready" if ready else "unavailable",
        f"{name} is available." if ready else f"{name} is not installed.",
        None if ready else remediation,
    )


def _command(name: str, executable: str, remediation: str) -> AnalyzerCapability:
    ready = resolve_command(executable) is not None
    return AnalyzerCapability(
        name,
        "ready" if ready else "unavailable",
        f"{name} is available." if ready else f"{name} is not installed.",
        None if ready else remediation,
    )


def _configured(name: str, command: list[str]) -> AnalyzerCapability:
    return AnalyzerCapability(
        name,
        "ready" if command else "unavailable",
        "Project command is configured." if command else "Project command is not configured.",
        None if command else "Configure a shell-free command argument array for this project.",
    )
