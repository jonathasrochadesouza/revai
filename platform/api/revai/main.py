"""FastAPI application factory and route wiring."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from revai.api.routes import config as config_routes
from revai.api.routes import exports as export_routes
from revai.api.routes import health
from revai.api.routes import projects as project_routes
from revai.api.routes import providers as provider_routes
from revai.api.routes import reviews as review_routes
from revai.config import Settings, get_settings
from revai.pipeline.limiter import ReviewLimiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("revai")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start-up and shut-down hooks."""
    settings: Settings = get_settings()
    settings.ensure_dirs()

    logger.info("%s %s starting", settings.app_name, settings.version)
    logger.info("data directory: %s", settings.data_dir)
    logger.info("listening on http://%s:%s", settings.host, settings.port)

    yield

    logger.info("shutting down")


def create_app() -> FastAPI:
    """Build the application.

    A factory rather than a module-level instance so tests can construct an app
    with overridden settings.
    """
    settings = get_settings()

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
    app.include_router(config_routes.router, prefix="/api")
    app.include_router(provider_routes.router, prefix="/api")
    app.include_router(project_routes.router, prefix="/api")
    app.include_router(review_routes.router, prefix="/api")
    app.include_router(export_routes.router, prefix="/api")

    return app


app = create_app()
