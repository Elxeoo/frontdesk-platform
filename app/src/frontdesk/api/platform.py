"""Endpoints the platform relies on: liveness, readiness and metrics (platform contract C1-C3).

They sit outside /api, so the fault switches never reach them (C8). All three are `async` and
never wait for a worker thread: when slow business requests occupy every thread during a
database outage, the probes still answer at once.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(include_in_schema=False)


@router.get("/healthz")
async def healthz() -> JSONResponse:
    # Deliberately checks nothing else: a database outage must not restart the process.
    return JSONResponse({"status": "ok"})


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    if request.app.state.draining:
        return JSONResponse({"status": "draining"}, status_code=503)
    if not await request.app.state.db.is_ready():
        return JSONResponse({"status": "database unavailable"}, status_code=503)
    return JSONResponse({"status": "ready"})


@router.get("/metrics")
async def metrics(request: Request) -> Response:
    return PlainTextResponse(
        generate_latest(request.app.state.metrics_registry), media_type=CONTENT_TYPE_LATEST
    )
