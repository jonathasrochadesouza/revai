"""Command-line entry point for installed RevAI packages."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import uvicorn

from revai import __version__
from revai.config import Settings, get_settings
from revai.storage import ConfigRepository, CredentialsRepository, StorageError

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
    parser.error(f"unknown command: {args.command}")
    return 2


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
