"""Concurrent execution of optional deterministic analyzers."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from revai.analyzers.eslint import parse_eslint_output
from revai.analyzers.gitleaks import parse_gitleaks_output
from revai.analyzers.ruff import parse_ruff_output
from revai.analyzers.security import find_security_issues
from revai.analyzers.semgrep import parse_semgrep_output
from revai.analyzers.sonarqube import parse_sonarqube_issues
from revai.domain.models import AnalyzerConfig, Finding
from revai.shell import command_for_execution, resolve_command

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
    if config.security:
        jobs.append(_run_security(repository, paths))
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
    if config.sonarqube.enabled:
        jobs.append(
            _run_sonarqube(
                repository,
                config.sonarqube.timeout_s,
                config.sonarqube.server_url,
                config.sonarqube.project_key,
            )
        )
    return list(await asyncio.gather(*jobs))


async def _run_security(repository: Path, paths: list[str]) -> AnalyzerRun:
    """Run lightweight, dependency-free high-confidence security checks."""
    started = time.perf_counter()
    try:
        findings = await asyncio.to_thread(find_security_issues, repository, paths)
        return AnalyzerRun("security", "completed", findings, _duration_ms(started))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return AnalyzerRun("security", "failed", [], _duration_ms(started), str(exc))


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
    node = resolve_command("node")
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
    executable = resolve_command("semgrep")
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
    executable = resolve_command("gitleaks")
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


async def _run_sonarqube(
    repository: Path, timeout_s: int, server_url: str, project_key: str | None
) -> AnalyzerRun:
    """Run a local scanner, then retrieve its normalized server issues.

    SonarQube needs a whole-project scan, unlike changed-line linters. A scanner
    is therefore an explicit opt-in and its token is read only from SONAR_TOKEN.
    """
    executable = resolve_command("sonar-scanner")
    if executable is None:
        return AnalyzerRun("sonarqube", "unavailable", [], 0, "sonar-scanner is not installed.")
    if not project_key:
        return AnalyzerRun("sonarqube", "unavailable", [], 0, "Set a SonarQube project key.")
    token = os.environ.get("SONAR_TOKEN")
    if not token:
        return AnalyzerRun(
            "sonarqube", "unavailable", [], 0, "Set SONAR_TOKEN in the API environment."
        )
    started = time.perf_counter()
    command = [
        executable,
        f"-Dsonar.host.url={server_url}",
        f"-Dsonar.projectKey={project_key}",
    ]
    try:
        returncode, _stdout, stderr = await asyncio.wait_for(
            _process(command, repository), timeout=timeout_s
        )
        duration = _duration_ms(started)
        if returncode != 0:
            return AnalyzerRun(
                "sonarqube", "failed", [], duration, stderr.strip() or "SonarScanner failed."
            )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{server_url.rstrip('/')}/api/issues/search",
                params={"componentKeys": project_key, "resolved": "false", "ps": 500},
                auth=(token, ""),
            )
            response.raise_for_status()
        return AnalyzerRun(
            "sonarqube", "completed", parse_sonarqube_issues(response.json(), repository), duration
        )
    except (TimeoutError, OSError, httpx.HTTPError, ValueError) as exc:
        return AnalyzerRun("sonarqube", "failed", [], _duration_ms(started), str(exc))


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
        execution, environment = command_for_execution(command)
        completed = subprocess.run(
            execution,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=120,
            shell=False,
            check=False,
            env=environment,
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
