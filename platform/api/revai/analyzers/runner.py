"""Concurrent execution of optional deterministic analyzers."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from revai.analyzers.eslint import parse_eslint_output
from revai.analyzers.gitleaks import parse_gitleaks_output
from revai.analyzers.ruff import parse_ruff_output
from revai.analyzers.semgrep import parse_semgrep_output
from revai.domain.models import AnalyzerConfig, Finding

AnalyzerStatus = Literal["completed", "unavailable", "failed"]


@dataclass(frozen=True)
class AnalyzerRun:
    name: str
    status: AnalyzerStatus
    findings: list[Finding]
    duration_ms: int
    detail: str | None = None


async def run_analyzers(
    repository: Path,
    paths: list[str],
    config: AnalyzerConfig,
) -> list[AnalyzerRun]:
    """Run every enabled analyzer concurrently and isolate tool failures."""
    jobs = []
    if config.ruff:
        jobs.append(_run_ruff(repository, paths))
    if config.eslint:
        jobs.append(_run_eslint(repository, paths))
    if config.semgrep:
        jobs.append(_run_semgrep(repository, paths))
    if config.gitleaks:
        jobs.append(_run_gitleaks(repository, paths))
    if config.checkstyle:
        jobs.append(
            _unavailable(
                "checkstyle",
                "Checkstyle integration requires a project command.",
            )
        )
    if config.treesitter:
        jobs.append(_tree_sitter_status())
    return list(await asyncio.gather(*jobs))


async def _run_ruff(repository: Path, paths: list[str]) -> AnalyzerRun:
    python_paths = [path for path in paths if Path(path).suffix.lower() in {".py", ".pyi"}]
    if not python_paths:
        return AnalyzerRun("ruff", "completed", [], 0, "No changed Python files.")
    if importlib.util.find_spec("ruff") is None:
        return AnalyzerRun("ruff", "unavailable", [], 0, "Ruff is not installed.")
    return await _execute(
        name="ruff",
        command=[
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--output-format",
            "json",
            "--no-fix",
            "--",
            *python_paths,
        ],
        repository=repository,
        parser=parse_ruff_output,
        allowed_returncodes={0, 1},
    )


async def _run_eslint(repository: Path, paths: list[str]) -> AnalyzerRun:
    extensions = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue"}
    source_paths = [path for path in paths if Path(path).suffix.lower() in extensions]
    if not source_paths:
        return AnalyzerRun("eslint", "completed", [], 0, "No changed JS/TS files.")
    node = shutil.which("node")
    script = repository / "node_modules" / "eslint" / "bin" / "eslint.js"
    if node is None or not script.is_file():
        return AnalyzerRun(
            "eslint",
            "unavailable",
            [],
            0,
            "A project-local ESLint installation was not found.",
        )
    return await _execute(
        name="eslint",
        command=[node, str(script), "--format", "json", "--no-fix", "--", *source_paths],
        repository=repository,
        parser=parse_eslint_output,
        allowed_returncodes={0, 1},
    )


async def _run_semgrep(repository: Path, paths: list[str]) -> AnalyzerRun:
    executable = shutil.which("semgrep")
    config = next(
        (
            repository / name
            for name in (".semgrep.yml", ".semgrep.yaml")
            if (repository / name).is_file()
        ),
        None,
    )
    if executable is None:
        return AnalyzerRun("semgrep", "unavailable", [], 0, "Semgrep is not installed.")
    if config is None:
        return AnalyzerRun(
            "semgrep",
            "unavailable",
            [],
            0,
            "No .semgrep.yml or .semgrep.yaml configuration was found.",
        )
    return await _execute(
        name="semgrep",
        command=[
            executable,
            "scan",
            "--json",
            "--quiet",
            "--config",
            str(config),
            "--",
            *paths,
        ],
        repository=repository,
        parser=parse_semgrep_output,
        allowed_returncodes={0, 1},
    )


async def _run_gitleaks(repository: Path, paths: list[str]) -> AnalyzerRun:
    del paths  # Gitleaks applies its own ignore rules while scanning the directory.
    executable = shutil.which("gitleaks")
    if executable is None:
        return AnalyzerRun("gitleaks", "unavailable", [], 0, "Gitleaks is not installed.")

    descriptor, report_name = tempfile.mkstemp(prefix="revai-gitleaks-", suffix=".json")
    os.close(descriptor)
    report = Path(report_name)
    started = time.perf_counter()
    try:
        returncode, _stdout, stderr = await _process(
            [
                executable,
                "dir",
                str(repository),
                "--report-format",
                "json",
                "--report-path",
                str(report),
                "--no-banner",
                "--redact",
            ],
            repository,
        )
        duration = _duration_ms(started)
        if returncode not in {0, 1}:
            return AnalyzerRun(
                "gitleaks",
                "failed",
                [],
                duration,
                stderr.strip() or "Gitleaks failed.",
            )
        payload = report.read_text(encoding="utf-8") if report.is_file() else "[]"
        return AnalyzerRun(
            "gitleaks",
            "completed",
            parse_gitleaks_output(payload, repository),
            duration,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return AnalyzerRun("gitleaks", "failed", [], _duration_ms(started), str(exc))
    finally:
        report.unlink(missing_ok=True)


async def _tree_sitter_status() -> AnalyzerRun:
    if importlib.util.find_spec("tree_sitter_language_pack") is None:
        return AnalyzerRun(
            "treesitter",
            "unavailable",
            [],
            0,
            "Tree-sitter language pack is not installed; built-in Python AST fallback was used.",
        )
    return AnalyzerRun("treesitter", "completed", [], 0)


async def _unavailable(name: str, detail: str) -> AnalyzerRun:
    return AnalyzerRun(name, "unavailable", [], 0, detail)


async def _execute(
    *,
    name: str,
    command: list[str],
    repository: Path,
    parser,
    allowed_returncodes: set[int],
) -> AnalyzerRun:
    started = time.perf_counter()
    try:
        returncode, stdout, stderr = await _process(command, repository)
        duration = _duration_ms(started)
        if returncode not in allowed_returncodes:
            return AnalyzerRun(
                name,
                "failed",
                [],
                duration,
                stderr.strip() or f"{name} failed.",
            )
        return AnalyzerRun(name, "completed", parser(stdout, repository), duration)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return AnalyzerRun(name, "failed", [], _duration_ms(started), str(exc))


def _process_blocking(command: list[str], cwd: Path) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=120,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, "", "Analyzer did not finish within 120 seconds."
    return (
        completed.returncode,
        completed.stdout.decode("utf-8", errors="replace"),
        completed.stderr.decode("utf-8", errors="replace"),
    )


async def _process(command: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run analyzers on a thread so Windows selector loops can launch them."""
    return await asyncio.to_thread(
        _process_blocking,
        command,
        cwd=cwd,
    )


def _duration_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
