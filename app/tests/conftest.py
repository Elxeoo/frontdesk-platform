"""Shared fixtures. Database tests run against a real PostgreSQL named in TEST_DATABASE_URL.

The database name must end in `_test`: the fixtures empty its tables before every test.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date

import psycopg
import pytest
from fastapi.testclient import TestClient

from frontdesk.api import create_app
from frontdesk.config import Settings
from frontdesk.db import Database
from frontdesk.migrate import migrate

TODAY = date(2026, 11, 8)


class FixedClock:
    """A clock the test controls, so date rules (R3, R7) are tested on exact days."""

    def __init__(self, today: date) -> None:
        self.today = today

    def __call__(self) -> date:
        return self.today


def make_settings(**overrides: str) -> Settings:
    env = {
        "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", ""),
        "APP_VERSION": "1.2.3",
        "POD_NAME": "api-test-0",
    }
    env.update(overrides)
    return Settings.from_env(env)


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    name = psycopg.conninfo.conninfo_to_dict(url).get("dbname", "")
    if not str(name).endswith("_test"):
        pytest.fail(f"Refusing to use database {name!r}: its name must end in '_test'.")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    migrate(url)
    return url


@pytest.fixture
def db(database_url: str) -> Iterator[Database]:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("TRUNCATE reservations, night_audit_reports RESTART IDENTITY")
        conn.execute("UPDATE rooms SET status = 'clean'")
    database = Database(database_url, max_size=4)
    database.open()
    yield database
    database.close()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(TODAY)


@pytest.fixture
def client(db: Database, clock: FixedClock) -> Iterator[TestClient]:
    app = create_app(make_settings(), db=db, clock=clock)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def book(client: TestClient):
    """Create a reservation through the API and return its JSON."""

    def _book(
        room: str = "201",
        arrival: str = "2026-11-08",
        departure: str = "2026-11-10",
        adults: int = 2,
        children: int = 0,
        **extra: object,
    ) -> dict:
        response = client.post(
            "/api/reservations",
            json={
                "room_number": room,
                "guest_name": "Test Guest",
                "arrival_date": arrival,
                "departure_date": departure,
                "adults": adults,
                "children": children,
                **extra,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _book
