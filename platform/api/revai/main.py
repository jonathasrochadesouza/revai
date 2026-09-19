"""FastAPI application factory and route wiring."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from revai.api.routes import agent as agent_routes
from revai.api.routes import config as config_routes
from revai.api.routes import exports as export_routes
from revai.api.routes import health
from revai.api.routes import projects as project_routes
from revai.api.routes import prompts as prompt_routes
from revai.api.routes import providers as provider_routes
from revai.api.routes import reviews as review_routes
from revai.api.routes import sonarqube as sonarqube_routes
from revai.config import Settings, get_settings
from revai.domain.enums import ReviewStatus
from revai.errors import RevaiError
from revai.pipeline.limiter import ReviewLimiter
from revai.storage import ReviewRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("revai")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start-up and shut-down hooks."""
    settings: Settings = app.state.settings
    settings.ensure_dirs()

    logger.info("%s %s starting", settings.app_name, settings.version)
    logger.info("data directory: %s", settings.data_dir)
    logger.info("listening on http://%s:%s", settings.host, settings.port)

    # Jobs survive browser disconnects, but this local process is their execution
    # boundary. After an unclean restart, never leave stale "running" history that
    # implies work still exists; make the interruption explicit and retryable.
    review_repo = ReviewRepository(settings)
    recovered = 0
    for review in review_repo.list():
        if review.status not in {ReviewStatus.QUEUED, ReviewStatus.RUNNING}:
            continue
        review.status = ReviewStatus.ABORTED
        review.error = "Review interrupted because the RevAI process restarted. Retry it."
        review.finished_at = datetime.now(UTC)
        review_repo.save(review)
        recovered += 1
    if recovered:
        logger.warning("marked %s interrupted review job(s) as aborted", recovered)

    try:
        yield
    finally:
        tasks = list(getattr(app.state, "review_tasks", {}).values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("shutting down")


def create_app(settings_override: Settings | None = None) -> FastAPI:
    """Build the application.

    A factory rather than a module-level instance so tests can construct an app
    with overridden settings.
    """
    settings = settings_override or get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        summary="Local-first AI code review. No account, no cloud, no telemetry.",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    # A single local process owns the queue. Each job persists its own state in
    # YAML; this object only coordinates live execution slots.
    app.state.review_limiter = ReviewLimiter()
    app.state.settings = settings
    # Strong references keep background reviews alive after an SSE client leaves.
    # The map is also the explicit cancellation boundary.
    app.state.review_tasks = {}

    # The web app is served from a different port during development, so CORS is
    # required. Restricted to explicit loopback origins — never "*".
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(agent_routes.router, prefix="/api")
    app.include_router(config_routes.router, prefix="/api")
    app.include_router(prompt_routes.router, prefix="/api")
    app.include_router(provider_routes.router, prefix="/api")
    app.include_router(project_routes.router, prefix="/api")
    app.include_router(review_routes.router, prefix="/api")
    app.include_router(export_routes.router, prefix="/api")
    app.include_router(sonarqube_routes.router, prefix="/api")

    app.add_exception_handler(RevaiError, _handle_revai_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)

    return app


async def _handle_revai_error(_request: Request, exc: RevaiError) -> JSONResponse:
    """The single place that renders the structured error contract for `RevaiError`."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"error_key": exc.error_key, "params": exc.params}},
    )


async def _handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Render every pydantic validation failure through the same contract.

    A `PydanticCustomError` raised inside a `@field_validator`/`@model_validator`
    carries its `error_key` as pydantic's `type` and its `params` as `ctx` — both
    survive into `exc.errors()`. Anything pydantic raised itself (a bare
    `min_length` violation, a type mismatch FastAPI caught before a custom
    validator ran) has no such key, so it maps to a generic, still-structured
    fallback that names the offending field instead of pydantic's own `msg` text.
    """
    details: list[dict[str, Any]] = []
    for error in exc.errors():
        ctx = error.get("ctx") or {}
        error_key = error.get("type", "")
        if "." in error_key:
            # A namespaced key means this came from our own PydanticCustomError.
            details.append({"error_key": error_key, "params": ctx})
        else:
            field = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
            details.append({"error_key": "validation.invalid_field", "params": {"field": field}})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": details if len(details) > 1 else details[0]},
    )


async def _handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    """Never let a raw traceback or exception message reach the client."""
    logger.exception("unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": {"error_key": "internal.unexpected_error", "params": {}}},
    )


app = create_app()
