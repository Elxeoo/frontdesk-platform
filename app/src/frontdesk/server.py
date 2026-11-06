"""HTTP server with a graceful, drain-first shutdown (platform contract C16).

On SIGTERM the pod first reports "not ready" for `drain_seconds`, so Kubernetes can take it out of
the Service endpoints while it still serves requests that are already on their way. Only then does
Uvicorn stop accepting connections and wait for in-flight requests. A second signal, or Ctrl+C,
keeps Uvicorn's own behaviour.
"""

from __future__ import annotations

import logging
import signal
import threading
from types import FrameType

import uvicorn
from fastapi import FastAPI

from frontdesk.config import Settings

log = logging.getLogger(__name__)


class DrainingServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, app: FastAPI, drain_seconds: float) -> None:
        super().__init__(config)
        self._app = app
        self._drain_seconds = drain_seconds
        self._draining = False

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        if sig != signal.SIGTERM or self._draining:
            super().handle_exit(sig, frame)
            return
        self._draining = True
        self._app.state.draining = True
        log.info("SIGTERM received, draining", extra={"drain_seconds": self._drain_seconds})
        # Setting should_exit directly, not through super(), ends with exit code 0: Uvicorn would
        # otherwise re-raise the captured SIGTERM after shutdown and the process would die of it.
        timer = threading.Timer(self._drain_seconds, self._stop)
        timer.daemon = True
        timer.start()

    def _stop(self) -> None:
        log.info("drain finished, stopping")
        self.should_exit = True


def serve(app: FastAPI, settings: Settings) -> None:
    config = uvicorn.Config(
        app,
        host="0.0.0.0",  # noqa: S104 - inside a container the port is the boundary
        port=settings.port,
        log_config=None,
        access_log=False,
        timeout_graceful_shutdown=settings.shutdown_timeout_seconds,
        proxy_headers=True,
        server_header=False,
    )
    DrainingServer(config, app, settings.drain_seconds).run()
