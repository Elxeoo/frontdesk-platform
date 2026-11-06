"""Cross-cutting HTTP behaviour: identification headers, request IDs and the access log.

Written as plain ASGI middleware so it adds headers to every response, including errors, without
buffering bodies.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from frontdesk.api.errors import error_response
from frontdesk.logs import request_id_var

log = logging.getLogger("frontdesk.access")

# A caller may pass its own request ID; anything unusual is replaced rather than logged as is.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
_PROBES = frozenset({"/healthz", "/readyz", "/metrics"})


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, *, app_version: str, pod_name: str) -> None:
        self.app = app
        self.app_version = app_version
        self.pod_name = pod_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        status_sent = False

        async def send_with_headers(message: Message) -> None:
            nonlocal status, status_sent
            if message["type"] == "http.response.start":
                status, status_sent = message["status"], True
                headers = MutableHeaders(scope=message)
                headers["X-App-Version"] = self.app_version
                headers["X-Served-By"] = self.pod_name
                headers["X-Request-ID"] = request_id
                if scope["app"].state.draining:
                    # Ask keep-alive clients (the gateway) to reconnect, so their next request
                    # goes to a pod that is staying.
                    headers["Connection"] = "close"
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            # Starlette answers unhandled errors outside this middleware, without our headers.
            # Answer here instead, so even a crash carries the version and request ID.
            log.exception("unhandled error")
            if status_sent:
                raise
            await error_response(500, "INTERNAL", "Something went wrong on our side.")(
                scope, receive, send_with_headers
            )
        finally:
            route = scope.get("route")
            path = scope["path"]
            log.log(
                logging.DEBUG if path in _PROBES else logging.INFO,
                "request",
                extra={
                    "method": scope["method"],
                    "route": getattr(route, "path", None),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_var.reset(token)
