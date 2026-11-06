"""The promises in docs/platform-contract.md that can be checked in-process (C1-C10, C14)."""

from __future__ import annotations

import json
import logging
import re

import pytest
from fastapi.testclient import TestClient

from frontdesk.api import create_app
from frontdesk.db import Database
from frontdesk.logs import JsonFormatter
from tests.conftest import make_settings

pytestmark = pytest.mark.db

UNREACHABLE = "postgresql://nobody@127.0.0.1:1/nothing_test?connect_timeout=1"


@pytest.fixture
def client_without_database(clock):
    app = create_app(make_settings(), db=Database(UNREACHABLE), clock=clock)
    with TestClient(app) as client:
        yield client


def faulty_client(db, clock, **faults: str) -> TestClient:
    return TestClient(create_app(make_settings(**faults), db=db, clock=clock))


class TestHealth:
    def test_c1_c2_healthy(self, client):
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200

    def test_c1_c2_database_down(self, client_without_database):
        assert client_without_database.get("/healthz").status_code == 200
        assert client_without_database.get("/readyz").status_code == 503

    def test_business_requests_fail_fast_without_a_database(self, client_without_database):
        response = client_without_database.get("/api/rooms")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "UNAVAILABLE"
        assert response.headers["Retry-After"] == "5"

    def test_c16_draining_pod_is_not_ready(self, client):
        client.app.state.draining = True
        assert client.get("/readyz").json() == {"status": "draining"}
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.headers["Connection"] == "close"


class TestMetrics:
    def scrape(self, client) -> str:
        response = client.get("/metrics")
        assert response.status_code == 200
        return response.text

    def test_c4_histogram_with_contract_labels(self, client):
        client.get("/api/rooms")
        text = self.scrape(client)
        bucket = next(
            line
            for line in text.splitlines()
            if line.startswith("http_server_request_duration_seconds_bucket") and 'le="0.5"' in line
        )
        labels = set(re.findall(r'(\w+)="', bucket))
        assert labels == {"http_request_method", "http_route", "http_response_status_code", "le"}
        assert 'http_route="/api/rooms"' in bucket

    def test_c5_routes_are_templates(self, client, book):
        for _ in range(3):
            client.get(f"/api/reservations/{book(room='G0' + str(_ + 1))['id']}")
        routes = set(re.findall(r'http_route="([^"]+)"', self.scrape(client)))
        assert "/api/reservations/{reservation_id}" in routes
        assert not any(re.search(r"/\d+$", route) for route in routes)

    def test_c6_probes_are_not_traffic(self, client):
        for _ in range(5):
            client.get("/healthz")
            client.get("/readyz")
        self.scrape(client)
        text = self.scrape(client)  # the first scrape would show up in the second
        for probe in ("/healthz", "/readyz", "/metrics"):
            assert f'http_route="{probe}"' not in text

    def test_c6_exclusion_cannot_be_abused(self, client):
        # A Host header or a path that merely contains a probe name is still real traffic.
        client.get("/api/rooms", headers={"Host": "evil/metrics"})
        client.get("/api/rooms/metrics")
        text = self.scrape(client)
        assert re.search(r'http_server_request_duration_seconds_count\{[^}]*"/api/rooms"', text)
        assert 'http_route="/api/rooms/{number}"' in text

    def test_unused_size_histograms_are_dropped(self, client):
        client.get("/api/rooms")
        assert "body_size" not in self.scrape(client)

    def test_c7_injected_errors_are_recorded(self, db, clock):
        with faulty_client(db, clock, FAULT_ERROR_RATE="1") as client:
            client.get("/api/rooms")
            assert 'http_response_status_code="500"' in self.scrape(client)


class TestFaults:
    def test_c7_error_rate(self, db, clock):
        with faulty_client(db, clock, FAULT_ERROR_RATE="1") as client:
            response = client.get("/api/rooms")
            assert response.status_code == 500
            assert response.json()["error"]["code"] == "INTERNAL"

    def test_c7_error_rate_is_a_share(self, db, clock):
        with faulty_client(db, clock, FAULT_ERROR_RATE="0.3") as client:
            failures = sum(client.get("/api/rooms").status_code == 500 for _ in range(400))
        assert 80 <= failures <= 160  # 30 % of 400 is 120; the band is about five sigma wide

    def test_c8_platform_endpoints_ignore_faults(self, db, clock):
        with faulty_client(db, clock, FAULT_ERROR_RATE="1", FAULT_LATENCY_MS="2000") as client:
            for path in ("/healthz", "/readyz", "/metrics"):
                assert client.get(path).status_code == 200


class TestIdentification:
    @pytest.mark.parametrize("path", ["/healthz", "/api/rooms", "/api/rooms/nope", "/nowhere"])
    def test_c9_c10_headers_on_every_response(self, client, path):
        response = client.get(path)
        assert response.headers["X-App-Version"] == "1.2.3"
        assert response.headers["X-Served-By"] == "api-test-0"

    def test_request_id_is_echoed_or_generated(self, client):
        assert (
            client.get("/healthz", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"]
            == "abc-123"
        )
        generated = client.get("/healthz", headers={"X-Request-ID": "bad id\n"}).headers[
            "X-Request-ID"
        ]
        assert re.fullmatch(r"[0-9a-f]{32}", generated)

    def test_unknown_path_uses_the_error_shape(self, client):
        response = client.get("/nowhere")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


class TestHostileInput:
    """Bad input is the caller's fault (4xx), never a 5xx that would skew the canary."""

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("GET", "/api/rooms/%00", None),
            ("GET", "/api/reservations/99999999999999999999", None),
            (
                "POST",
                "/api/reservations",
                {
                    "room_number": "201",
                    "guest_name": "Null\x00Byte",
                    "arrival_date": "2026-11-08",
                    "departure_date": "2026-11-09",
                    "adults": 1,
                },
            ),
        ],
    )
    def test_rejected_as_validation(self, client, method, path, body):
        response = client.request(method, path, json=body)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION"

    def test_method_not_allowed_keeps_allow_header(self, client):
        response = client.delete("/api/rooms")
        assert response.status_code == 405
        assert "GET" in response.headers["Allow"]


def test_unexpected_error_keeps_shape_headers_and_metrics(client, monkeypatch):
    def explode(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(client.app.state.front_desk, "list_rooms", explode)
    response = client.get("/api/rooms")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL"
    assert response.headers["X-App-Version"] == "1.2.3"
    assert "boom" not in response.text
    assert 'http_response_status_code="500"' in client.get("/metrics").text


def test_c14_log_lines_are_json():
    record = logging.makeLogRecord(
        {"name": "frontdesk", "levelname": "INFO", "msg": "request", "status": 200}
    )
    entry = json.loads(JsonFormatter().format(record))
    assert entry["message"] == "request"
    assert entry["level"] == "INFO"
    assert entry["status"] == 200
    assert "timestamp" in entry
