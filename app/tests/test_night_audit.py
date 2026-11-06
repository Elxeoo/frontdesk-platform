"""Closing a business day: rule R7, a day closed only once, and only after it has ended."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from frontdesk.clock import hotel_today
from frontdesk.night_audit import DatabaseReportWriter, DayNotOver, run_night_audit

pytestmark = pytest.mark.db

NOV_8 = date(2026, 11, 8)
NOV_9 = date(2026, 11, 9)
LATER = date(2026, 12, 1)


def status_of(client, reservation) -> str:
    return client.get(f"/api/reservations/{reservation['id']}").json()["status"]


def test_r7_a_late_guest_is_carried_over_then_marked(client, book, db):
    # The example from docs/domain.md: due 8 November, leaving 10 November, never arrives.
    absent = book(room="201", arrival="2026-11-08", departure="2026-11-10")
    writer = DatabaseReportWriter(db)

    run_night_audit(db, writer, NOV_8, today=LATER)
    assert status_of(client, absent) == "booked"  # the 9th is still a check-in day

    report = run_night_audit(db, writer, NOV_9, today=LATER)
    assert status_of(client, absent) == "no_show"
    assert report["no_shows"] == [absent["id"]]


def test_report_counts_the_day(client, book, db, clock):
    # Check-in times come from the database clock, so this test closes the real current day.
    clock.today = today = hotel_today()
    stayed = book(arrival=today.isoformat(), departure=(today + timedelta(days=3)).isoformat())
    client.post(f"/api/reservations/{stayed['id']}/check-in", json={"adults": 2})

    report = run_night_audit(db, DatabaseReportWriter(db), today, today=today + timedelta(days=1))
    assert report["business_date"] == today.isoformat()
    assert report["checked_in"] == 1
    assert report["in_house"] == 1
    assert report["occupancy_rate"] == round(1 / 22, 3)
    assert client.get("/api/night-audit/reports/latest").json() == report


def test_a_closed_day_is_never_reopened(client, book, db):
    book(room="201", arrival="2026-11-08", departure="2026-11-09")
    writer = DatabaseReportWriter(db)
    first = run_night_audit(db, writer, NOV_8, today=LATER)

    # Booked after the day was closed; a rerun must neither report nor touch it.
    late_entry = book(room="202", arrival="2026-11-08", departure="2026-11-09")
    second = run_night_audit(db, writer, NOV_8, today=LATER)
    assert second == first
    assert status_of(client, late_entry) == "booked"


@pytest.mark.parametrize("day", [NOV_8, NOV_9])
def test_a_day_that_has_not_ended_is_refused(client, book, db, day):
    reservation = book(room="201", arrival="2026-11-08", departure="2026-11-09")
    with pytest.raises(DayNotOver):
        run_night_audit(db, DatabaseReportWriter(db), day, today=NOV_8)
    assert status_of(client, reservation) == "booked"


def test_latest_report_before_any_audit(client):
    response = client.get("/api/night-audit/reports/latest")
    assert response.status_code == 404
