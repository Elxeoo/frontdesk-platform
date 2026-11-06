"""The real process: command exit codes (C13) and the drain-first shutdown (C16)."""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

from frontdesk.cli import main

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def restore_logging():
    """`main()` installs its JSON handler on the root logger; put pytest's setup back after."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def test_migrate_twice_exits_zero(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    assert main(["migrate"]) == 0
    assert main(["migrate"]) == 0


def test_night_audit_refuses_a_day_that_has_not_ended(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    assert main(["night-audit", "--date", "2999-01-01"]) == 2


def test_bad_configuration_exits_two_without_echoing_secrets(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "app:S3cretPw@db/app")
    assert main(["migrate"]) == 2
    assert "S3cretPw" not in capsys.readouterr().out


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _get(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 - local test server
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_c16_sigterm_drains_then_exits_zero(database_url):
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = os.environ | {
        "DATABASE_URL": database_url,
        "PORT": str(port),
        "DRAIN_SECONDS": "1",
        "FAULT_LATENCY_MS": "1500",
    }
    server = subprocess.Popen(
        [sys.executable, "-m", "frontdesk", "serve"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                if _get(f"{base}/healthz") == 200:
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("server did not start")

        in_flight: list[int] = []
        slow = threading.Thread(target=lambda: in_flight.append(_get(f"{base}/api/rooms")))
        slow.start()
        time.sleep(0.3)  # the slow request is now being served
        server.send_signal(signal.SIGTERM)
        time.sleep(0.2)
        assert _get(f"{base}/readyz") == 503  # out of rotation at once, still answering

        slow.join(timeout=10)
        assert in_flight == [200]  # the request that was in flight completed
        assert server.wait(timeout=20) == 0
    finally:
        if server.poll() is None:
            server.kill()
        output = server.stdout.read() if server.stdout else ""

    messages = [json.loads(line)["message"] for line in output.splitlines() if line.startswith("{")]
    assert "SIGTERM received, draining" in messages
