"""Builds the FastAPI application: routes, error handling, middleware and metrics."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from frontdesk import metrics
from frontdesk.api import platform, routes
from frontdesk.api.errors import install_error_handlers
from frontdesk.api.middleware import RequestContextMiddleware
from frontdesk.clock import Clock, hotel_today
from frontdesk.config import Settings
from frontdesk.db import Database
from frontdesk.service import FrontDesk


def create_app(
    settings: Settings, *, db: Database | None = None, clock: Clock = hotel_today
) -> FastAPI:
    db = db or Database(settings.require_database_url())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        db.open()
        try:
            yield
        finally:
            db.close()

    app = FastAPI(
        title="FrontDesk API",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.db = db
    app.state.front_desk = FrontDesk(db, clock)
    app.state.draining = False

    app.include_router(platform.router)
    app.include_router(routes.router)
    install_error_handlers(app)
    app.state.metrics_registry = metrics.instrument(app)
    app.add_middleware(
        RequestContextMiddleware, app_version=settings.app_version, pod_name=settings.pod_name
    )
    return app
