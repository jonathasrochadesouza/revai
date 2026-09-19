"""Local SonarQube provisioning endpoints.

Three verbs back the Settings card: a status probe, an SSE start stream and a
stop action. The start stream runs as a background task with a bounded queue —
the same shape as the review stream — so a slow image pull or server boot
never blocks the request handler and a disconnected browser cannot stall the
provisioning loop. Every provisioning step is idempotent, so a second start
resumes from wherever the flow got to (existing container, stored credential).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse

from revai.api.deps import ConfigRepo, CredentialsRepo
from revai.api.routes.reviews import _enqueue_latest
from revai.domain.models import Credentials, SonarQubeCredential
from revai.errors import RevaiError
from revai.sonarqube import local

router = APIRouter(tags=["sonarqube"])


def _start_lock(app: Any) -> asyncio.Lock:
    """One provisioning at a time per process — a second request is a 409."""
    if not hasattr(app.state, "sonar_start_lock"):
        app.state.sonar_start_lock = asyncio.Lock()
    return app.state.sonar_start_lock


def _forget_when_done(app: Any, name: str, task: asyncio.Task[None]) -> None:
    """Mirror the review-task bookkeeping: drop the entry once it completes."""

    def forget(completed: asyncio.Task[None]) -> None:
        tasks = app.state.sonar_tasks
        if tasks.get(name) is completed:
            tasks.pop(name, None)

    task.add_done_callback(forget)


@router.get("/sonarqube/status", summary="Local SonarQube provisioning status")
async def sonar_status(
    config_repo: ConfigRepo,
    credentials_repo: CredentialsRepo,
) -> dict:
    config = config_repo.load().analyzers.sonarqube
    credential = credentials_repo.load().sonarqube
    report = await local.local_status(config.server_url, config.wsl)
    return local.status_dict(
        report,
        provisioned=credential is not None,
        token_masked=credential.masked() if credential else None,
        server_url=config.server_url,
    )


@router.post("/sonarqube/start", summary="Start and provision the local SonarQube (SSE)")
async def start_sonar(
    http_request: Request,
    config_repo: ConfigRepo,
    credentials_repo: CredentialsRepo,
) -> StreamingResponse:
    config = config_repo.load().analyzers.sonarqube
    credentials = credentials_repo.load()
    project_key = config.project_key or "revai-local"

    lock = _start_lock(http_request.app)
    if lock.locked():
        raise RevaiError(status.HTTP_409_CONFLICT, "sonarqube.start_in_progress")
    await lock.acquire()

    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=64)

    async def run() -> None:
        try:
            async for event in local.start_flow(
                config.server_url,
                config.wsl,
                credentials,
                project_key,
                save_credential=_credential_saver(credentials_repo),
            ):
                _enqueue_latest(queue, event)
        finally:
            _enqueue_latest(queue, None)
            lock.release()

    task = asyncio.create_task(run(), name="revai-sonar-start")
    app_state = http_request.app.state
    app_state.sonar_tasks = getattr(app_state, "sonar_tasks", {})
    app_state.sonar_tasks[task.get_name()] = task
    _forget_when_done(http_request.app, task.get_name(), task)

    async def events() -> AsyncIterator[str]:
        while (event := await queue.get()) is not None:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sonarqube/stop", summary="Stop the local SonarQube container")
async def stop_sonar(
    config_repo: ConfigRepo,
    credentials_repo: CredentialsRepo,
) -> dict:
    config = config_repo.load().analyzers.sonarqube
    await local.stop_container(config.server_url, config.wsl)
    credential = credentials_repo.load().sonarqube
    report = await local.local_status(config.server_url, config.wsl)
    return local.status_dict(
        report,
        provisioned=credential is not None,
        token_masked=credential.masked() if credential else None,
        server_url=config.server_url,
    )


@router.delete("/sonarqube/credentials", summary="Forget the provisioned SonarQube credentials")
async def delete_sonar_credentials(
    credentials_repo: CredentialsRepo,
) -> dict:
    credentials = credentials_repo.load()
    if credentials.sonarqube is None:
        raise RevaiError(status.HTTP_404_NOT_FOUND, "sonarqube.no_credentials")
    credentials.sonarqube = None
    credentials_repo.save(credentials)
    return {"deleted": True}


def _credential_saver(repo) -> Callable[[SonarQubeCredential], None]:
    """Persist the provisioning secrets without returning them to the caller."""

    def save(credential: SonarQubeCredential) -> None:
        document: Credentials = repo.load()
        document.sonarqube = credential
        repo.save(document)

    return save
