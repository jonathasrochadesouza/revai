"""Command-line entry point for installed RevAI packages."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import stat
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import uvicorn

from revai import __version__
from revai.agents import collect_rules, compose_block, install, preview_document, render_report
from revai.agents.generator import provider_line
from revai.agents.renderer import inject_data, load_template, validate_payload
from revai.config import Settings, get_settings
from revai.domain.enums import ProviderId, ReviewMode, ReviewScope, ReviewStatus, Severity
from revai.domain.models import PipelineStageRecord, PromptOverride, Review, ReviewStats
from revai.errors import RevaiError
from revai.export.serializers import render_html, render_json, render_markdown, render_sarif
from revai.fixes.generator import generate_fix_patch
from revai.fixes.service import FixPreview, FixResult, apply_finding_fix
from revai.git.repo import GitError, current_branch, inspect_project
from revai.pipeline.ai import estimate_input_cost, merge_findings, run_ai_stage
from revai.pipeline.runner import StageRun, run_deterministic_pipeline
from revai.providers.registry import build_registry
from revai.sonarqube.local import resolve_sonar_token
from revai.storage import (
    ConfigRepository,
    CredentialsRepository,
    ProjectRepository,
    PromptRepository,
    ReviewRepository,
    StorageError,
)

PACKAGE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="revai",
        description="Local-first AI code review platform.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")

    serve = commands.add_parser("serve", help="start the local API server")
    serve.add_argument(
        "--port",
        type=_port,
        help="override REVAI_PORT for this process",
    )
    serve.add_argument(
        "--no-reload",
        action="store_true",
        help="disable development auto-reload",
    )

    doctor = commands.add_parser(
        "doctor",
        help="validate the local runtime and YAML data store without contacting a provider",
    )
    doctor.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    agent = commands.add_parser(
        "agent",
        help="install the RevAI review agent into a project or render an agent report",
    )
    agent_commands = agent.add_subparsers(dest="agent_command")
    agent_install = agent_commands.add_parser(
        "install",
        help="write the RevAI review block into AGENTS.md and ship the report template",
    )
    agent_install.add_argument("path", type=Path, help="path to the target project directory")
    agent_install.add_argument(
        "--provider",
        choices=[provider.value for provider in ProviderId],
        help="override the configured provider in the generated block",
    )
    agent_install.add_argument("--model", help="override the configured model")
    agent_install.add_argument(
        "--locale",
        choices=("en-US", "pt-BR"),
        help="persona language; defaults to the configured UI locale",
    )
    agent_install.add_argument(
        "--dry-run", action="store_true", help="print the merged AGENTS.md without writing"
    )
    agent_install.add_argument(
        "--yes", action="store_true", help="write without the interactive confirmation"
    )
    agent_render = agent_commands.add_parser(
        "render",
        help="render an agent report: inject review JSON into the report template",
    )
    agent_render.add_argument("json_file", type=Path, help="findings JSON (compact or full export)")
    agent_render.add_argument(
        "--name",
        required=True,
        help="report name, usually the branch (becomes <name>-revai.html)",
    )
    agent_render.add_argument(
        "--out",
        type=Path,
        help="destination directory; defaults to the JSON file's directory",
    )
    agent_render.add_argument(
        "--template", type=Path, help="override the template path (defaults to the packaged one)"
    )
    agent_render.add_argument(
        "--dry-run", action="store_true", help="print the report to stdout without writing"
    )

    review = commands.add_parser("review", help="run a headless review for CI or automation")
    review.add_argument("path", type=Path, help="path to a local Git repository")
    review.add_argument("--base", help="base branch; defaults to the detected base")
    review.add_argument("--head", help="head branch; defaults to the current branch")
    review.add_argument(
        "--scope",
        choices=[scope.value for scope in ReviewScope],
        default=ReviewScope.BRANCH_DIFF.value,
    )
    review.add_argument(
        "--file",
        dest="selected_files",
        action="append",
        default=[],
        help="tracked file to review; repeat with --scope selected_files",
    )
    review.add_argument(
        "--mode",
        choices=[mode.value for mode in ReviewMode],
        default=ReviewMode.BOTH.value,
    )
    review.add_argument("--provider", choices=[provider.value for provider in ProviderId])
    review.add_argument("--model", help="override the configured model for this run")
    review.add_argument(
        "--scenario",
        help="prompt scenario id or name to review with; defaults to the configured prompts",
    )
    review.add_argument("--format", choices=("json", "md", "html", "sarif"), default="json")
    review.add_argument("--output", type=Path, help="write the report to this file")
    review.add_argument(
        "--fail-on",
        choices=("none", "critical", "medium", "low"),
        default="critical",
    )
    review.add_argument("--no-persist", action="store_true", help="do not save history")

    fix = commands.add_parser(
        "fix",
        help="apply a stored finding fix to the working tree (unstaged)",
    )
    fix.add_argument("path", type=Path, help="path to the reviewed Git repository")
    fix.add_argument("--review", required=True, help="review id that produced the finding")
    fix.add_argument("--finding", required=True, help="finding id to fix")
    fix.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the fix and print the patch without touching the working tree",
    )
    fix.add_argument(
        "--generate",
        action="store_true",
        help="generate a fix with the configured model when the finding has no stored patch",
    )
    fix.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "serve":
        serve_api(port=args.port, no_reload=args.no_reload)
        return 0
    if args.command == "doctor":
        return doctor(json_output=args.json)
    if args.command == "agent":
        if args.agent_command == "install":
            return agent_install_command(args)
        if args.agent_command == "render":
            return agent_render_command(args)
        return agent_help()
    if args.command == "review":
        return review_command(args)
    if args.command == "fix":
        return fix_command(args)
    parser.error(f"unknown command: {args.command}")
    return 2


def _port_is_free(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
    except OSError:
        return False
    return True


def _first_free_port(host: str, requested: int, *, span: int = 50) -> int:
    """Return ``requested`` when bindable, otherwise the next free port."""
    for candidate in range(requested, requested + span):
        if _port_is_free(host, candidate):
            return candidate
    return requested


def serve_api(*, port: int | None = None, no_reload: bool = False) -> None:
    """Start uvicorn using the same settings contract as ``revai-api``."""
    settings = get_settings()
    if port is not None:
        # Keep the application lifespan and any reload worker on the same effective
        # port as uvicorn. Passing only ``uvicorn.run(port=...)`` made the startup
        # log incorrectly announce the configured default.
        os.environ["REVAI_PORT"] = str(port)
        get_settings.cache_clear()
        settings = get_settings()
    resolved_port = _first_free_port(settings.host, settings.port)
    if resolved_port != settings.port:
        # Another process owns the requested port, so fall forward to the first
        # free one and keep the application settings (lifespan, log lines) in
        # sync through the same REVAI_PORT override used above.
        print(
            f"Port {settings.port} is in use; starting the RevAI API on {resolved_port} instead",
            file=sys.stderr,
        )
        os.environ["REVAI_PORT"] = str(resolved_port)
        get_settings.cache_clear()
        settings = get_settings()
    reload_enabled = settings.environment == "development" and not no_reload
    uvicorn.run(
        "revai.main:app",
        host=settings.host,
        port=settings.port,
        reload=reload_enabled,
        reload_dirs=[str(PACKAGE_DIR)] if reload_enabled else None,
        log_level="info",
    )


def doctor(*, json_output: bool = False) -> int:
    """Validate a fresh or existing local installation without spending a request."""
    settings = get_settings()
    checks = [_python_check(), *_storage_checks(settings)]
    ok = all(check.status == "ok" for check in checks)
    payload = {
        "status": "ok" if ok else "error",
        "version": __version__,
        "data_dir": str(settings.data_dir),
        "checks": [asdict(check) for check in checks],
    }

    if json_output:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(f"RevAI {__version__}")
        for check in checks:
            print(f"[{check.status}] {check.name}: {check.detail}")
    return 0 if ok else 1


def agent_help() -> int:
    print("usage: revai agent {install,render} ...\n")
    print("  install  write the RevAI review block into a project's AGENTS.md")
    print("  render   inject review JSON into the agent report template")
    return 0


def agent_install_command(args: argparse.Namespace) -> int:
    """Write the managed RevAI block into the project's AGENTS.md."""
    settings = get_settings()
    settings.ensure_dirs()
    project_path = args.path.expanduser().resolve()
    if not project_path.is_dir():
        print(f"revai agent install failed: not a directory: {project_path}", file=sys.stderr)
        return 2

    config = ConfigRepository(settings).load().model_copy(deep=True)
    if args.provider:
        config.engine.provider_id = ProviderId(args.provider)
        config.engine.mode = config.engine.provider_id.kind.value
    if args.model:
        config.engine.model = args.model
    if args.locale:
        config.ui.locale = args.locale

    block = compose_block(config, rules=collect_rules(settings.rules_dir))
    if args.dry_run:
        document, _exists = preview_document(project_path, block)
        print(document)
        return 0
    if not args.yes and sys.stdin.isatty():
        answer = input(f"Write the RevAI block into {project_path / 'AGENTS.md'}? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Cancelled.")
            return 0
    if not args.yes and not sys.stdin.isatty():
        print(
            "revai agent install: refusing to write without confirmation;"
            " pass --yes for non-interactive use",
            file=sys.stderr,
        )
        return 2
    try:
        result = install(project_path, block)
    except OSError as exc:
        print(f"revai agent install failed: {exc}", file=sys.stderr)
        return 2
    print(f"AGENTS.md:  {result.agents_md}" + (" (created)" if result.agents_md_created else ""))
    print(f"Template:   {result.template}")
    if result.backup_created:
        print(f"Backup:     {result.agents_md.with_name('AGENTS.md.revai-bak')}")
    print(f"Engine:     {provider_line(config)}")
    return 0


def agent_render_command(args: argparse.Namespace) -> int:
    """Inject review JSON into the report template."""
    try:
        payload = args.json_file.expanduser().read_bytes()
    except OSError as exc:
        print(f"revai agent render failed: {exc}", file=sys.stderr)
        return 2
    template = args.template.read_text(encoding="utf-8") if args.template else load_template()
    try:
        data = validate_payload(payload)
    except ValueError as exc:
        print(f"revai agent render failed: {exc}", file=sys.stderr)
        return 2
    if args.dry_run:
        sys.stdout.buffer.write(inject_data(template, data).encode())
        return 0
    try:
        destination = render_report(
            payload,
            name=args.name,
            out_dir=args.out or args.json_file.expanduser().resolve().parent,
            template=template,
        )
    except (ValueError, OSError) as exc:
        print(f"revai agent render failed: {exc}", file=sys.stderr)
        return 2
    print(f"Report: {destination}")
    return 0


def review_command(args: argparse.Namespace) -> int:
    """Run the local pipeline without requiring the web server."""
    try:
        review, project = asyncio.run(_run_headless_review(args))
        content = {
            "json": render_json,
            "md": render_markdown,
            "html": render_html,
            "sarif": render_sarif,
        }[args.format](review, project)
        if args.output:
            args.output.expanduser().resolve().write_bytes(content)
        else:
            sys.stdout.buffer.write(content)
        if args.fail_on != "none":
            threshold = Severity(args.fail_on)
            if any(
                finding.is_actionable and finding.severity.rank <= threshold.rank
                for finding in review.findings
            ):
                return 1
        return 0
    except (GitError, StorageError, RuntimeError, ValueError, OSError) as exc:
        print(f"revai review failed: {exc}", file=sys.stderr)
        return 2


def fix_command(args: argparse.Namespace) -> int:
    """Apply one finding's fix from a stored review, without the web server.

    Exit 0 = applied (or a valid dry run). Exit 1 = the fix could not be
    applied (stale, branch mismatch, validation failed — a user-actionable
    outcome, matching ``--fail-on`` semantics). Exit 2 = configuration or
    execution error.
    """
    try:
        outcome = asyncio.run(_run_headless_fix(args))
    except RevaiError as exc:
        if args.json:
            print(
                json.dumps(
                    {"error": {"error_key": exc.error_key, "params": exc.params}},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            print(f"revai fix failed: {exc.error_key} {exc.params}", file=sys.stderr)
        return 1
    except (GitError, StorageError, RuntimeError, ValueError, OSError) as exc:
        print(f"revai fix failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(outcome.model_dump(), ensure_ascii=False, sort_keys=True))
    elif outcome.dry_run:
        print(f"Dry run — nothing applied. Files touched: {', '.join(outcome.files)}")
        print(outcome.patch)
    else:
        print(f"Applied fix to {', '.join(outcome.files)} (unstaged).")
        print(f"Validation: {outcome.validation}")
        print("Review with `git diff` before committing.")
    return 0


async def _run_headless_fix(args: argparse.Namespace) -> FixPreview | FixResult | None:
    """Locate project, review and finding, then run the fix service.

    Returns ``None`` when the outcome was an error the caller already printed
    and should surface as exit code 1 (a real user-actionable failure, not a
    configuration error).
    """
    settings = get_settings()
    settings.ensure_dirs()
    project_repo = ProjectRepository(settings)
    review_repo = ReviewRepository(settings)
    inspected = inspect_project(args.path.expanduser())
    project = next(
        (
            item
            for item in project_repo.list()
            if Path(item.path).resolve() == Path(inspected.path).resolve()
        ),
        None,
    )
    if project is None:
        raise ValueError(f"Unknown project path: {inspected.path}")
    review = review_repo.get(args.review, project.id)
    if review is None:
        raise ValueError(f"Unknown review id for this project: {args.review}")
    finding = next((item for item in review.findings if item.id == args.finding), None)
    if finding is None:
        raise ValueError(f"Unknown finding id in review {review.id}: {args.finding}")

    config = ConfigRepository(settings).load().model_copy(deep=True)
    patch = None
    if args.generate:
        provider = build_registry(config, CredentialsRepository(settings).load()).active()
        if provider is None:
            raise RuntimeError("The configured AI provider is not available.")
        health = await provider.health()
        if not health.is_usable:
            raise RuntimeError(health.detail or "The configured AI provider is not usable.")
        generated = await generate_fix_patch(provider, config, project, finding)
        patch = generated.patch

    result = await apply_finding_fix(project, review, finding, dry_run=args.dry_run, patch=patch)
    if isinstance(result, FixResult):
        review_repo.save(review)
    return result


async def _run_headless_review(args: argparse.Namespace):
    settings = get_settings()
    settings.ensure_dirs()
    project_repo = ProjectRepository(settings)
    review_repo = ReviewRepository(settings)
    inspected = inspect_project(args.path.expanduser())
    project = next(
        (
            item
            for item in project_repo.list()
            if Path(item.path).resolve() == Path(inspected.path).resolve()
        ),
        inspected,
    )
    if project is inspected and not args.no_persist:
        project_repo.save(project)

    config = ConfigRepository(settings).load().model_copy(deep=True)
    if args.provider:
        config.engine.provider_id = ProviderId(args.provider)
        config.engine.mode = config.engine.provider_id.kind.value
    if args.model:
        config.engine.model = args.model
    mode = ReviewMode(args.mode)
    scope = ReviewScope(args.scope)
    if scope is ReviewScope.SELECTED_FILES and not args.selected_files:
        raise ValueError("--scope selected_files requires at least one --file")
    base = args.base or project.base_branch
    head = args.head or current_branch(Path(project.path)) or base
    scenario = None
    if args.scenario:
        prompt_settings = PromptRepository(settings).load()
        scenario = next(
            (
                item
                for item in prompt_settings.scenarios
                if item.id == args.scenario or item.name.casefold() == args.scenario.casefold()
            ),
            None,
        )
        if scenario is None:
            raise ValueError(f"Unknown prompt scenario: {args.scenario}")
    prompt_override = (
        PromptOverride(
            system_prompt=scenario.system_prompt,
            user_prompt=scenario.user_prompt,
        )
        if scenario is not None
        else PromptRepository(settings).effective(config.ui.locale)
    )
    review = Review(
        project_id=project.id,
        scope=scope,
        mode=mode,
        base_branch=base,
        head_branch=head,
        provider_id=config.engine.provider_id if mode is not ReviewMode.STATIC else None,
        model=config.engine.model if mode is not ReviewMode.STATIC else None,
        scenario_id=scenario.id if scenario is not None else None,
        selected_files=args.selected_files,
    )
    started = time.perf_counter()
    result = await run_deterministic_pipeline(
        project,
        config,
        base=base,
        head=head,
        review=review,
        include_static=mode in {ReviewMode.STATIC, ReviewMode.BOTH},
        scope=scope,
        selected_files=args.selected_files,
        sonar_token=resolve_sonar_token(CredentialsRepository(settings).load()),
    )
    if mode is not ReviewMode.STATIC and result.chunks:
        provider = build_registry(config, CredentialsRepository(settings).load()).active()
        if provider is None:
            raise RuntimeError("The configured AI provider is not available.")
        health = await provider.health()
        if not health.is_usable:
            raise RuntimeError(health.detail or "The configured AI provider is not usable.")
        ai = await run_ai_stage(provider, config, result.chunks, prompt_override=prompt_override)
        result.review.findings = merge_findings(
            result.review.findings,
            ai.findings,
            dedupe=config.analyzers.dedupe_across_sources,
        )
        result.review.effective_model = ai.effective_model
        result.review.provider_version = health.version
        result.review.prompt_hash = ai.prompt_hash
        result.stages.extend(
            [
                StageRun(
                    "ai",
                    "completed",
                    ai.duration_ms,
                    f"{len(ai.findings)} AI findings.",
                ),
                StageRun(
                    "merge",
                    "completed",
                    0,
                    f"{len(result.review.findings)} findings.",
                ),
            ]
        )
        usage = ai.usage
        estimated = estimate_input_cost(result.chunks, provider_id=config.engine.provider_id)
        sent_paths = {chunk.path for chunk in result.chunks}
        analyzed_paths = {
            *(path for analyzer in result.analyzers for path in analyzer.files_analyzed),
            *sent_paths,
        }
        result.review.stats = ReviewStats(
            **result.review.stats.model_dump(
                exclude={
                    "files_analysed",
                    "hunks_sent_to_ai",
                    "chunks_sent_to_ai",
                    "files_sent_to_ai",
                    "secrets_redacted",
                    "tokens_input",
                    "tokens_output",
                    "tokens_cached",
                    "cost_usd",
                    "cost_is_estimated",
                    "duration_ms",
                }
            ),
            files_analysed=len(analyzed_paths),
            hunks_sent_to_ai=sum(hunk.path in sent_paths for hunk in result.hunks),
            chunks_sent_to_ai=len(result.chunks),
            files_sent_to_ai=len(sent_paths),
            secrets_redacted=ai.secrets_redacted,
            tokens_input=usage.input_tokens,
            tokens_output=usage.output_tokens,
            tokens_cached=usage.cached_tokens,
            cost_usd=usage.cost_usd if usage.cost_usd is not None else estimated,
            cost_is_estimated=usage.cost_usd is None or usage.is_estimated,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
    result.review.stages = [
        PipelineStageRecord(
            name=stage.name,
            status=stage.status,
            duration_ms=stage.duration_ms,
            detail=stage.detail,
        )
        for stage in result.stages
    ]
    result.review.status = (
        ReviewStatus.DEGRADED
        if any(
            analyzer.status in {"degraded", "unavailable", "failed"}
            for analyzer in result.analyzers
        )
        else ReviewStatus.COMPLETED
    )
    result.review.finished_at = datetime.now(UTC)
    result.review.stats.duration_ms = round((time.perf_counter() - started) * 1000)
    if not args.no_persist:
        review_repo.save(result.review)
        project.last_reviewed_at = datetime.now(UTC)
        project_repo.save(project)
    return result.review, project


def _python_check() -> DoctorCheck:
    version = sys.version_info
    supported = version >= (3, 12)
    rendered = f"{version.major}.{version.minor}.{version.micro}"
    return DoctorCheck(
        name="python",
        status="ok" if supported else "error",
        detail=f"{rendered} (requires 3.12+)",
    )


def _storage_checks(settings: Settings) -> list[DoctorCheck]:
    try:
        settings.ensure_dirs()
    except OSError as exc:
        return [DoctorCheck("data_dir", "error", f"could not initialize: {exc}")]

    checks = [
        DoctorCheck(
            "data_dir",
            "ok" if os.access(settings.data_dir, os.R_OK | os.W_OK) else "error",
            str(settings.data_dir),
        )
    ]
    checks.append(_document_check("config", ConfigRepository(settings).load))
    checks.append(_document_check("credentials", CredentialsRepository(settings).load))

    credentials = settings.credentials_file
    if credentials.is_file() and os.name != "nt":
        try:
            mode = stat.S_IMODE(credentials.stat().st_mode)
        except OSError as exc:
            checks.append(DoctorCheck("credential_permissions", "error", str(exc)))
            return checks
        private = mode & 0o077 == 0
        checks.append(
            DoctorCheck(
                "credential_permissions",
                "ok" if private else "error",
                f"{mode:04o} ({'private' if private else 'expected 0600'})",
            )
        )
    return checks


def _document_check(name: str, loader: Callable[[], object]) -> DoctorCheck:
    try:
        loader()
    except StorageError as exc:
        return DoctorCheck(name, "error", str(exc))
    return DoctorCheck(name, "ok", "valid or not created yet")


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


if __name__ == "__main__":
    raise SystemExit(main())
