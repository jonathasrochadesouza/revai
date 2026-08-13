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
from urllib.parse import urlsplit

import httpx

from revai.analyzers.eslint import parse_eslint_output
from revai.analyzers.gitleaks import parse_gitleaks_output
from revai.analyzers.ruff import parse_ruff_output
from revai.analyzers.security import find_security_issues
from revai.analyzers.semgrep import parse_semgrep_output
from revai.analyzers.sonarqube import parse_sonarqube_issues
from revai.domain.models import AnalyzerConfig, Finding, SonarQubeConfig
from revai.shell import command_for_execution, resolve_command

AnalyzerStatus = Literal["completed", "degraded", "unavailable", "failed", "skipped"]


@dataclass(frozen=True)
class AnalyzerRun:
    name: str
    status: AnalyzerStatus
    findings: list[Finding]
    duration_ms: int
    detail: str | None = None
    files_analyzed: tuple[str, ...] = ()
    metadata: dict[str, str | int | float | bool | None] | None = None


async def run_analyzers(
    repository: Path,
    paths: list[str],
    config: AnalyzerConfig,
    *,
    checkstyle_command: list[str] | None = None,
    test_command: list[str] | None = None,
    build_command: list[str] | None = None,
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
        jobs.append(_run_project_command("checkstyle", repository, checkstyle_command))
    if config.project_tests:
        jobs.append(_run_project_command("project_tests", repository, test_command))
    if config.project_build:
        jobs.append(_run_project_command("project_build", repository, build_command))
    if config.treesitter:
        jobs.append(_tree_sitter_status())
    if config.sonarqube.enabled:
        jobs.append(_run_sonarqube(repository, paths, config.sonarqube))
    return list(await asyncio.gather(*jobs))


async def _run_security(repository: Path, paths: list[str]) -> AnalyzerRun:
    """Run lightweight, dependency-free high-confidence security checks."""
    started = time.perf_counter()
    try:
        supported = tuple(
            path
            for path in paths
            if Path(path).suffix.lower()
            in {".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java"}
        )
        if not supported:
            return AnalyzerRun(
                "security",
                "skipped",
                [],
                0,
                "No changed Python, Java, or JavaScript/TypeScript files; built-in security "
                "rules do not cover this language.",
            )
        findings = await asyncio.to_thread(find_security_issues, repository, list(supported))
        detail = None
        unsupported = len(paths) - len(supported)
        status: AnalyzerStatus = "completed"
        if unsupported:
            status = "degraded"
            detail = (
                f"Analyzed {len(supported)} supported files; {unsupported} files "
                "use unsupported languages."
            )
        return AnalyzerRun(
            "security",
            status,
            findings,
            _duration_ms(started),
            detail,
            supported,
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return AnalyzerRun("security", "failed", [], _duration_ms(started), str(exc))


async def _run_ruff(repository: Path, paths: list[str]) -> AnalyzerRun:
    python_paths = [path for path in paths if Path(path).suffix.lower() in {".py", ".pyi"}]
    if not python_paths:
        return AnalyzerRun("ruff", "skipped", [], 0, "No changed Python files.")
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
        analyzed_files=python_paths,
    )


async def _run_eslint(repository: Path, paths: list[str]) -> AnalyzerRun:
    extensions = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue"}
    source_paths = [path for path in paths if Path(path).suffix.lower() in extensions]
    if not source_paths:
        return AnalyzerRun("eslint", "skipped", [], 0, "No changed JS/TS files.")
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
        analyzed_files=source_paths,
    )


async def _run_semgrep(repository: Path, paths: list[str]) -> AnalyzerRun:
    if not paths:
        return AnalyzerRun("semgrep", "skipped", [], 0, "No reviewable changed files.")
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
        analyzed_files=paths,
    )


async def _run_gitleaks(repository: Path, paths: list[str]) -> AnalyzerRun:
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
            files_analyzed=tuple(paths),
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
    return AnalyzerRun(
        "treesitter",
        "skipped",
        [],
        0,
        "Tree-sitter supplies chunk boundaries; it does not produce static findings.",
    )


async def _run_project_command(
    name: str,
    repository: Path,
    command: list[str] | None,
) -> AnalyzerRun:
    """Run an explicitly configured, shell-free project quality command."""
    if not command:
        return AnalyzerRun(
            name,
            "unavailable",
            [],
            0,
            f"Configure the project's {name.replace('_', ' ')} command first.",
        )
    started = time.perf_counter()
    returncode, stdout, stderr = await _process(command, repository)
    detail = (stderr or stdout).strip()
    if len(detail) > 600:
        detail = f"{detail[:600].rstrip()}…"
    if returncode == 0:
        return AnalyzerRun(
            name,
            "completed",
            [],
            _duration_ms(started),
            detail or "Command passed.",
        )
    return AnalyzerRun(
        name,
        "failed",
        [],
        _duration_ms(started),
        detail or f"Command exited with code {returncode}.",
    )


async def _run_sonarqube(
    repository: Path,
    paths: list[str],
    config: SonarQubeConfig,
) -> AnalyzerRun:
    """Run a local scanner, then retrieve its normalized server issues.

    SonarQube needs a whole-project scan, unlike changed-line linters. A scanner
    is therefore an explicit opt-in and its token is read only from SONAR_TOKEN.
    """
    if not config.project_key:
        return AnalyzerRun("sonarqube", "unavailable", [], 0, "Set a SonarQube project key.")
    token = os.environ.get("SONAR_TOKEN")
    if not token:
        return AnalyzerRun(
            "sonarqube", "unavailable", [], 0, "Set SONAR_TOKEN in the API environment."
        )
    started = time.perf_counter()
    selected = _sonar_command(repository, config)
    if selected is None:
        return AnalyzerRun(
            "sonarqube",
            "unavailable",
            [],
            0,
            "No supported Sonar scanner was found. Install Maven/Gradle for this "
            "project or sonar-scanner.",
        )
    scanner, command = selected
    previous_reports = {
        path: (path.stat().st_mtime_ns, path.stat().st_size)
        for path in _sonar_report_paths(repository)
        if path.is_file()
    }
    try:
        returncode, _stdout, stderr = await _process(
            command,
            repository,
            timeout_s=config.timeout_s,
        )
        if returncode != 0:
            return AnalyzerRun(
                "sonarqube",
                "failed",
                [],
                _duration_ms(started),
                stderr.strip() or "Sonar scanner failed.",
            )
        report = _sonar_report(repository, previous=previous_reports)
        async with httpx.AsyncClient(timeout=30, auth=(token, "")) as client:
            analysis_id = await _wait_for_sonar_analysis(
                client,
                config.server_url,
                report,
                config.quality_gate_timeout_s,
            )
            issues_payload = await _sonar_issues(
                client,
                config.server_url,
                config.project_key,
                new_code_only=config.new_code_only,
            )
            gate = await _sonar_quality_gate(
                client,
                config.server_url,
                config.project_key,
                analysis_id,
            )
        gate_status = str(gate.get("status") or "UNKNOWN")
        metadata: dict[str, str | int | float | bool | None] = {
            "scanner": scanner,
            "quality_gate": gate_status,
            "new_code_only": config.new_code_only,
            "issues_total": len(issues_payload.get("issues") or []),
        }
        run_status: AnalyzerStatus = "completed"
        detail = f"Quality gate: {gate_status}."
        if config.wait_for_quality_gate and gate_status not in {"OK", "NONE"}:
            run_status = "degraded"
            detail = f"Quality gate did not pass: {gate_status}."
        return AnalyzerRun(
            "sonarqube",
            run_status,
            parse_sonarqube_issues(issues_payload, repository),
            _duration_ms(started),
            detail,
            tuple(paths),
            metadata,
        )
    except (TimeoutError, OSError, httpx.HTTPError, ValueError) as exc:
        return AnalyzerRun("sonarqube", "failed", [], _duration_ms(started), str(exc))


def _sonar_command(
    repository: Path,
    config: SonarQubeConfig,
) -> tuple[str, list[str]] | None:
    """Prefer build-tool scanners so Java bytecode and dependencies are available."""
    common = [
        f"-Dsonar.host.url={config.server_url}",
        f"-Dsonar.projectKey={config.project_key}",
    ]
    scanner = config.scanner
    if scanner in {"auto", "maven"} and (repository / "pom.xml").is_file():
        executable = _project_executable(repository, ("mvnw", "mvnw.cmd")) or resolve_command("mvn")
        if executable:
            return "maven", [
                executable,
                "-B",
                "-DskipTests",
                *common,
                "verify",
                "org.sonarsource.scanner.maven:sonar-maven-plugin:sonar",
            ]
        if scanner == "maven":
            return None
    if scanner in {"auto", "gradle"} and any(
        (repository / name).is_file()
        for name in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
    ):
        executable = _project_executable(
            repository, ("gradlew", "gradlew.bat")
        ) or resolve_command("gradle")
        if executable:
            return "gradle", [executable, "sonar", *common]
        if scanner == "gradle":
            return None
    if scanner in {"auto", "cli"} and (executable := resolve_command("sonar-scanner")):
        return "cli", [executable, *common]
    return None


def _project_executable(repository: Path, names: tuple[str, ...]) -> str | None:
    for name in names:
        candidate = repository / name
        if candidate.is_file():
            return str(candidate)
    return None


def _sonar_report_paths(repository: Path) -> tuple[Path, ...]:
    return (
        repository / ".scannerwork" / "report-task.txt",
        repository / "target" / "sonar" / "report-task.txt",
        repository / "build" / "sonar" / "report-task.txt",
    )


def _sonar_report(
    repository: Path,
    *,
    previous: dict[Path, tuple[int, int]] | None = None,
) -> dict[str, str]:
    candidates = _sonar_report_paths(repository)
    report = next(
        (
            path
            for path in candidates
            if path.is_file()
            and (
                previous is None
                or previous.get(path) != (path.stat().st_mtime_ns, path.stat().st_size)
            )
        ),
        None,
    )
    if report is None:
        raise ValueError("Sonar scanner completed without a fresh report-task.txt.")
    values: dict[str, str] = {}
    for line in report.read_text(encoding="utf-8", errors="replace").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()
    return values


async def _wait_for_sonar_analysis(
    client: httpx.AsyncClient,
    server_url: str,
    report: dict[str, str],
    timeout_s: int,
) -> str | None:
    task_url = report.get("ceTaskUrl")
    task_id = report.get("ceTaskId")
    if not task_url and task_id:
        task_url = f"{server_url.rstrip('/')}/api/ce/task?id={task_id}"
    if not task_url:
        raise ValueError("Sonar report did not include a Compute Engine task.")
    expected = urlsplit(server_url)
    actual = urlsplit(task_url)
    if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
        raise ValueError("Sonar Compute Engine task URL did not match the configured server.")
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        response = await client.get(task_url)
        response.raise_for_status()
        task = response.json().get("task") or {}
        status = str(task.get("status") or "")
        if status == "SUCCESS":
            return str(task.get("analysisId")) if task.get("analysisId") else None
        if status in {"FAILED", "CANCELED"}:
            raise ValueError(f"Sonar Compute Engine task ended with {status}.")
        await asyncio.sleep(1)
    raise TimeoutError(f"Sonar Compute Engine did not finish within {timeout_s}s.")


async def _sonar_issues(
    client: httpx.AsyncClient,
    server_url: str,
    project_key: str,
    *,
    new_code_only: bool,
) -> dict[str, object]:
    issues: list[object] = []
    page = 1
    while True:
        params: dict[str, str | int | bool] = {
            "componentKeys": project_key,
            "resolved": "false",
            "ps": 500,
            "p": page,
        }
        if new_code_only:
            params["inNewCodePeriod"] = "true"
        response = await client.get(
            f"{server_url.rstrip('/')}/api/issues/search",
            params=params,
        )
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("issues") or []
        issues.extend(batch)
        paging = payload.get("paging") or {}
        total = int(paging.get("total") or len(issues))
        if len(issues) >= total or not batch:
            break
        page += 1
    return {"issues": issues, "paging": {"total": len(issues)}}


async def _sonar_quality_gate(
    client: httpx.AsyncClient,
    server_url: str,
    project_key: str,
    analysis_id: str | None,
) -> dict[str, object]:
    params = {"analysisId": analysis_id} if analysis_id else {"projectKey": project_key}
    response = await client.get(
        f"{server_url.rstrip('/')}/api/qualitygates/project_status",
        params=params,
    )
    response.raise_for_status()
    return response.json().get("projectStatus") or {}


async def _unavailable(name: str, detail: str) -> AnalyzerRun:
    return AnalyzerRun(name, "unavailable", [], 0, detail)


async def _execute(
    *,
    name: str,
    command: list[str],
    repository: Path,
    parser,
    allowed_returncodes: set[int],
    analyzed_files: list[str],
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
        return AnalyzerRun(
            name,
            "completed",
            parser(stdout, repository),
            duration,
            files_analyzed=tuple(analyzed_files),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return AnalyzerRun(name, "failed", [], _duration_ms(started), str(exc))


def _process_blocking(
    command: list[str], cwd: Path, timeout_s: int = 120
) -> tuple[int, str, str]:
    try:
        execution, environment = command_for_execution(command)
        completed = subprocess.run(
            execution,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout_s,
            shell=False,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return 124, "", f"Analyzer did not finish within {timeout_s} seconds."
    return (
        completed.returncode,
        completed.stdout.decode("utf-8", errors="replace"),
        completed.stderr.decode("utf-8", errors="replace"),
    )


async def _process(
    command: list[str], cwd: Path, *, timeout_s: int = 120
) -> tuple[int, str, str]:
    """Run analyzers on a thread so Windows selector loops can launch them."""
    return await asyncio.to_thread(
        _process_blocking,
        command,
        cwd=cwd,
        timeout_s=timeout_s,
    )


def _duration_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
