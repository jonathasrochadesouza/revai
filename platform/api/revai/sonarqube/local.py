"""Local SonarQube Community Build provisioning over the Docker CLI.

The one-screen local setup: resolve ``docker`` (falling back to a Windows
``docker.exe`` through WSL interop), run a pinned Community Build image with a
persistent volume on loopback, wait for the server to finish booting, then
provision a ready-to-use login — the default ``admin`` password is replaced by
a generated one, the configured project is created, and an analysis token is
generated. Both secrets land in ``credentials.yaml`` (chmod 600); nothing raw
ever reaches an API response or a stream event.

Every docker invocation follows the house pattern from
``revai.providers.detection``: an absolute executable path, a fixed argument
list, ``shell=False`` and a hard timeout, executed via ``subprocess.run`` on a
worker thread because uvicorn on Windows cannot spawn subprocesses from the
event loop.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import shutil
import sys
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from revai.domain.models import Credentials, SonarQubeCredential
from revai.providers.detection import (
    resolve_windows_executable_from_wsl,
    run_command,
    wsl_interop_available,
)
from revai.shell import resolve_command

# Pinned so the local server never changes under an existing data volume.
IMAGE = "sonarqube:26.9.0.129388-community"
CONTAINER_NAME = "revai-sonarqube"
VOLUME_NAME = "revai-sonarqube-data"
HOST_PORT = 9000

BOOT_TIMEOUT_S = 420.0
BOOT_POLL_INTERVAL_S = 2.0
DOCKER_TIMEOUT_S = 120.0
PULL_TIMEOUT_S = 1800.0

# SonarQube Community Build ships with admin/admin and forces a password change
# on first login, which is exactly what the provisioning step below performs.
DEFAULT_ADMIN_LOGIN = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"


class SonarProvisionError(Exception):
    """A provisioning fault, expressed through the error-key contract."""

    def __init__(self, error_key: str, params: dict[str, str] | None = None) -> None:
        super().__init__(error_key)
        self.error_key = error_key
        self.params = params or {}


# ===========================================================================
# Docker resolution and probes
# ===========================================================================


def resolve_docker(wsl: bool) -> str | None:
    """Find the Docker CLI, honouring the user-declared WSL setup.

    Without the flag the normal PATH lookup runs. With it, a Windows
    ``docker.exe`` is resolved through WSL interop first — the exact path a
    Docker Desktop-on-Windows user needs.
    """
    if wsl and not sys.platform.startswith("win"):
        resolved = resolve_windows_executable_from_wsl("docker.exe")
        if resolved:
            return resolved
    return resolve_command("docker") or shutil.which("docker") or shutil.which("docker.exe")


def _wsl_detected() -> bool:
    return wsl_interop_available()


@dataclass(frozen=True)
class ContainerState:
    exists: bool
    running: bool
    status: str | None = None


@dataclass(frozen=True)
class DockerDaemonStatus:
    installed: bool
    running: bool
    version: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class SonarServerStatus:
    up: bool
    version: str | None = None


async def _container_state(docker_path: str) -> ContainerState:
    result = await run_command(
        docker_path,
        ("inspect", "--format", "{{.State.Status}}", CONTAINER_NAME),
        timeout_s=DOCKER_TIMEOUT_S,
    )
    if result.exit_code != 0:
        return ContainerState(exists=False, running=False)
    status = result.stdout.strip()
    return ContainerState(exists=True, running=status == "running", status=status or None)


async def _docker_daemon(docker_path: str) -> DockerDaemonStatus:
    result = await run_command(
        docker_path,
        ("version", "--format", "{{.Server.Version}}"),
        timeout_s=DOCKER_TIMEOUT_S,
    )
    if result.ok:
        version = result.stdout.strip() or None
        return DockerDaemonStatus(True, True, version)
    detail = result.stderr.strip() or result.stdout.strip() or None
    return DockerDaemonStatus(True, False, None, detail)


async def probe_server(server_url: str) -> SonarServerStatus:
    """Ask ``/api/system/status`` whether a SonarQube server is up. Never raises."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{server_url.rstrip('/')}/api/system/status")
        if response.status_code == 200:
            payload = response.json()
            if payload.get("status") == "UP":
                version = payload.get("version")
                return SonarServerStatus(True, version if isinstance(version, str) else None)
    except (httpx.HTTPError, ValueError):
        pass
    return SonarServerStatus(False)


@dataclass(frozen=True)
class SonarLocalStatus:
    """Everything the Settings screen needs to explain the current state."""

    image: str
    wsl_detected: bool
    docker: DockerDaemonStatus
    container: ContainerState
    server: SonarServerStatus


async def local_status(server_url: str, wsl: bool) -> SonarLocalStatus:
    """Probe Docker, the RevAI container and the server without starting anything."""
    docker_path = resolve_docker(wsl)
    wsl_now = _wsl_detected()
    if docker_path is None:
        return SonarLocalStatus(
            IMAGE,
            wsl_now,
            DockerDaemonStatus(False, False),
            ContainerState(False, False),
            SonarServerStatus(False),
        )
    daemon = await _docker_daemon(docker_path)
    if not daemon.running:
        return SonarLocalStatus(
            IMAGE,
            wsl_now,
            daemon,
            ContainerState(False, False),
            SonarServerStatus(False),
        )
    container = await _container_state(docker_path)
    server = await probe_server(server_url)
    return SonarLocalStatus(IMAGE, wsl_now, daemon, container, server)


def resolve_sonar_token(credentials: Credentials | None) -> str | None:
    """Stored provisioning token first, ``SONAR_TOKEN`` env as the fallback."""
    if credentials is not None and credentials.sonarqube is not None:
        return credentials.sonarqube.token
    return os.environ.get("SONAR_TOKEN")


# ===========================================================================
# Lifecycle: start / stop
# ===========================================================================


def _port_conflict(detail: str) -> bool:
    lowered = detail.lower()
    return "port is already allocated" in lowered or "address already in use" in lowered


async def start_flow(
    server_url: str,
    wsl: bool,
    credentials: Credentials | None,
    project_key: str,
    save_credential,
) -> AsyncIterator[dict]:
    """Yield SSE-ready progress events until ``ready`` or ``failed``.

    Every step is idempotent: an existing container is started rather than
    recreated, an already-up server skips the boot wait, and an existing
    credential short-circuits straight to ``ready``.
    """
    docker_path = resolve_docker(wsl)
    if docker_path is None:
        yield {"type": "failed", "error_key": "sonarqube.docker_not_found", "params": {}}
        return

    daemon = await _docker_daemon(docker_path)
    if not daemon.running:
        yield {
            "type": "failed",
            "error_key": "sonarqube.docker_unavailable",
            "params": {"detail": daemon.detail or ""},
        }
        return
    yield {"type": "docker_checked", "docker_version": daemon.version}

    container = await _container_state(docker_path)
    server = await probe_server(server_url)

    if server.up and not container.exists:
        yield {
            "type": "failed",
            "error_key": "sonarqube.port_conflict",
            "params": {"server_url": server_url},
        }
        return

    if server.up and container.running:
        yield {"type": "server_already_up"}
    else:
        try:
            async for event in _ensure_container(docker_path, server_url):
                yield event
        except SonarProvisionError as exc:
            yield {"type": "failed", "error_key": exc.error_key, "params": exc.params}
            return
        yield {"type": "waiting_boot"}
        stored_password = (
            credentials.sonarqube.admin_password
            if credentials is not None and credentials.sonarqube is not None
            else None
        )
        server = await _wait_for_boot(server_url, stored_password)
        if not server.up:
            yield {
                "type": "failed",
                "error_key": "sonarqube.boot_timeout",
                "params": {"server_url": server_url},
            }
            return
        yield {"type": "boot_complete", "version": server.version}

    if credentials is not None and credentials.sonarqube is not None:
        yield {"type": "already_provisioned", "token_masked": credentials.sonarqube.masked()}
        yield {"type": "ready", "server_url": server_url, "project_key": project_key}
        return

    yield {"type": "provisioning"}
    try:
        token, admin_password = await _provision(server_url, project_key)
    except SonarProvisionError as exc:
        yield {"type": "failed", "error_key": exc.error_key, "params": exc.params}
        return
    credential = SonarQubeCredential(token=token, admin_password=admin_password)
    save_credential(credential)
    yield {
        "type": "ready",
        "token_masked": credential.masked(),
        "server_url": server_url,
        "project_key": project_key,
    }


async def _ensure_container(docker_path: str, server_url: str) -> AsyncIterator[dict]:
    """Pull/run/start the container until it exists and runs."""
    container = await _container_state(docker_path)
    if container.exists:
        yield {"type": "starting", "existing": True}
        start = await run_command(
            docker_path, ("start", CONTAINER_NAME), timeout_s=DOCKER_TIMEOUT_S
        )
        if not start.ok:
            raise SonarProvisionError(
                "sonarqube.container_start_failed", {"detail": (start.stderr or "").strip()}
            )
        return

    yield {"type": "pulling", "image": IMAGE}
    pull = await run_command(docker_path, ("pull", IMAGE), timeout_s=PULL_TIMEOUT_S)
    if not pull.ok:
        raise SonarProvisionError("sonarqube.pull_failed", {"detail": (pull.stderr or "").strip()})

    yield {"type": "starting", "existing": False}
    run = await run_command(
        docker_path,
        (
            "run",
            "-d",
            "--name",
            CONTAINER_NAME,
            "-p",
            f"127.0.0.1:{HOST_PORT}:{HOST_PORT}",
            "-v",
            f"{VOLUME_NAME}:/opt/sonarqube/data",
            "--restart",
            "unless-stopped",
            IMAGE,
        ),
        timeout_s=DOCKER_TIMEOUT_S,
    )
    if not run.ok:
        stderr = (run.stderr or "").strip()
        if _port_conflict(stderr):
            raise SonarProvisionError("sonarqube.port_conflict", {"server_url": server_url})
        raise SonarProvisionError("sonarqube.container_start_failed", {"detail": stderr})


async def _wait_for_boot(server_url: str, stored_password: str | None = None) -> SonarServerStatus:
    """Poll until the server is genuinely ready, not just reporting UP.

    ``/api/system/status`` flips to UP while migrations and the web layer are
    still settling — a provisioning call made in that window fails oddly. The
    signal that the flow can actually run is an authenticated probe answering
    ``200``: it proves both the web-service layer and a known admin login are
    live. On a fresh container the shipped ``admin/admin`` has to work; on a
    restarted one the previously provisioned password is what exists.
    """
    consecutive_up = 0
    deadline = time.monotonic() + BOOT_TIMEOUT_S
    while time.monotonic() < deadline:
        server = await probe_server(server_url)
        if server.up:
            consecutive_up += 1
            if consecutive_up >= 2 and await _admin_probe_ready(server_url, stored_password):
                return server
        else:
            consecutive_up = 0
        await asyncio.sleep(BOOT_POLL_INTERVAL_S)
    return SonarServerStatus(False)


async def _admin_probe_ready(server_url: str, stored_password: str | None) -> bool:
    """Whether a known admin password already reaches a protected endpoint."""
    passwords = [DEFAULT_ADMIN_PASSWORD] + ([stored_password] if stored_password else [])
    for password in passwords:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{server_url.rstrip('/')}/api/projects/search",
                    auth=(DEFAULT_ADMIN_LOGIN, password),
                )
        except httpx.HTTPError:
            continue
        if response.status_code == 200:
            return True
    return False


async def stop_container(server_url: str, wsl: bool) -> ContainerState:
    """Stop the local container if it exists; report the resulting state."""
    docker_path = resolve_docker(wsl)
    if docker_path is None:
        return ContainerState(exists=False, running=False)
    container = await _container_state(docker_path)
    if not container.exists or not container.running:
        return container
    await run_command(docker_path, ("stop", CONTAINER_NAME), timeout_s=DOCKER_TIMEOUT_S)
    return await _container_state(docker_path)


# ===========================================================================
# Provisioning: ready-made login, project and token
# ===========================================================================

_PROVISION_TIMEOUT_S = 60.0
_PROVISION_RETRIES = 3
_PROVISION_RETRY_PAUSE_S = 5.0


async def _provision_post(
    url: str,
    *,
    params: dict | None = None,
    auth: tuple[str, str] | None,
) -> httpx.Response:
    """POST on a fresh connection, with patience for the server's state.

    A freshly booted Community Build answers ``404 Unknown url`` or 503 for a
    short window even after ``/api/system/status`` reports ``UP``, and right
    after ``change_password`` it keeps rejecting basic auth for a while — both
    observed on a real server, both gone after a short pause.

    A fresh ``AsyncClient`` per call is load-bearing: SonarQube 26.x resolves
    authentication per HTTP connection, so reusing the connection that logged
    in with ``admin/admin`` still answers 401 for the new password moments
    later. Verified against a real server.
    """
    last = None
    for attempt in range(_PROVISION_RETRIES):
        async with httpx.AsyncClient(timeout=_PROVISION_TIMEOUT_S) as client:
            response = await client.post(url, params=params, auth=auth)
        if response.status_code not in {401, 404, 502, 503} or attempt == _PROVISION_RETRIES - 1:
            return response
        last = response
        await asyncio.sleep(_PROVISION_RETRY_PAUSE_S)
    return last


async def _provision(server_url: str, project_key: str) -> tuple[str, str]:
    """Turn a fresh server into a ready one: password, project, token.

    SonarQube ships ``admin/admin`` and forces a password change on first
    login. The generated password and a generated analysis token are both
    returned; the caller persists them. The flow is only ever run once per
    data volume — a second run on the same server would be blocked earlier by
    the stored-credential short-circuit.
    """
    base = server_url.rstrip("/")
    # Community Build policy: at least 12 characters with a special character,
    # so the suffix guarantees acceptance rather than guessing the policy.
    password = f"{secrets.token_urlsafe(18)}9A!"
    try:
        # Basic auth with the shipped admin/admin is the reliable way to
        # reach the forced-password-change endpoint: the cookie-based
        # session path adds CSRF header requirements we cannot rely on.
        changed = await _provision_post(
            f"{base}/api/users/change_password",
            params={
                "login": DEFAULT_ADMIN_LOGIN,
                "previousPassword": DEFAULT_ADMIN_PASSWORD,
                "password": password,
            },
            auth=(DEFAULT_ADMIN_LOGIN, DEFAULT_ADMIN_PASSWORD),
        )
        if changed.status_code == 401:
            raise SonarProvisionError(
                "sonarqube.admin_password_unknown", {"server_url": server_url}
            )
        if changed.status_code != 204:
            raise SonarProvisionError(
                "sonarqube.password_change_failed", {"server_url": server_url}
            )

        auth = (DEFAULT_ADMIN_LOGIN, password)
        created = await _provision_post(
            f"{base}/api/projects/create",
            params={"name": project_key, "project": project_key},
            auth=auth,
        )
        # 400 means "project already exists" on a reused data volume; 204 is
        # the No-Content success this build also answers with.
        if created.status_code not in {200, 204, 400}:
            raise SonarProvisionError(
                "sonarqube.project_create_failed",
                {
                    "project_key": project_key,
                    "status_code": created.status_code,
                    "detail": created.text[:300],
                },
            )

        generated = await _provision_post(
            f"{base}/api/user_tokens/generate",
            params={"name": "revai"},
            auth=auth,
        )
        if generated.status_code != 200:
            raise SonarProvisionError("sonarqube.token_failed", {"server_url": server_url})
        token = generated.json().get("token")
        if not isinstance(token, str) or not token:
            raise SonarProvisionError("sonarqube.token_failed", {"server_url": server_url})
        return token, password
    except httpx.HTTPError as exc:
        raise SonarProvisionError(
            "sonarqube.server_unreachable", {"server_url": server_url, "detail": str(exc)}
        ) from exc


def status_dict(
    status: SonarLocalStatus,
    *,
    provisioned: bool,
    token_masked: str | None,
    server_url: str,
) -> dict:
    """Flatten :class:`SonarLocalStatus` into the JSON contract for the route."""
    return {
        "image": status.image,
        "wsl_detected": status.wsl_detected,
        "docker": {
            "installed": status.docker.installed,
            "running": status.docker.running,
            "version": status.docker.version,
            "detail": status.docker.detail,
        },
        "container": {
            "exists": status.container.exists,
            "running": status.container.running,
            "state": status.container.status,
        },
        "server": {
            "up": status.server.up,
            "version": status.server.version,
            "url": server_url,
        },
        "provisioned": provisioned,
        "token_masked": token_masked,
    }


__all__ = [
    "CONTAINER_NAME",
    "HOST_PORT",
    "IMAGE",
    "ContainerState",
    "DockerDaemonStatus",
    "SonarLocalStatus",
    "SonarProvisionError",
    "SonarServerStatus",
    "local_status",
    "probe_server",
    "resolve_docker",
    "resolve_sonar_token",
    "start_flow",
    "status_dict",
    "stop_container",
]
