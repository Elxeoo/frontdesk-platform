"""Creating, checking in, checking out and cancelling reservations through the API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from frontdesk.db import Database
from frontdesk.domain import RuleViolation
from frontdesk.service import FrontDesk, NewReservation

pytestmark = pytest.mark.db


def error_code(response) -> str:
    return response.json()["error"]["code"]


class TestCreate:
    def test_created_reservation_is_booked(self, client, book):
        reservation = book(notes="Honeymoon")
        assert reservation["status"] == "booked"
        assert reservation["notes"] == "Honeymoon"
        response = client.get(f"/api/reservations/{reservation['id']}")
        assert response.json() == reservation

    def test_location_header_points_to_the_reservation(self, client):
        response = client.post(
            "/api/reservations",
            json={
                "room_number": "201",
                "guest_name": "Test Guest",
                "arrival_date": "2026-11-08",
                "departure_date": "2026-11-09",
                "adults": 1,
            },
        )
        assert response.headers["Location"] == f"/api/reservations/{response.json()['id']}"

    def test_r1_too_many_guests(self, client):
        response = client.post(
            "/api/reservations",
            json={
                "room_number": "G01",
                "guest_name": "Test Guest",
                "arrival_date": "2026-11-08",
                "departure_date": "2026-11-10",
                "adults": 2,
                "children": 1,
            },
        )
        assert response.status_code == 422
        assert error_code(response) == "R1"

    def test_malformed_body_is_a_validation_error(self, client):
        response = client.post("/api/reservations", json={"room_number": "201"})
        assert response.status_code == 422
        assert error_code(response) == "VALIDATION"

    def test_unknown_room(self, client):
        response = client.post(
            "/api/reservations",
            json={
                "room_number": "999",
                "guest_name": "Test Guest",
                "arrival_date": "2026-11-08",
                "departure_date": "2026-11-10",
                "adults": 1,
            },
        )
        assert response.status_code == 404
        assert error_code(response) == "NOT_FOUND"


class TestDoubleBooking:
    def test_r2_overlap_is_refused(self, client, book):
        book(arrival="2026-11-08", departure="2026-11-12")
        response = client.post(
            "/api/reservations",
            json={
                "room_number": "201",
                "guest_name": "Second Guest",
                "arrival_date": "2026-11-11",
                "departure_date": "2026-11-13",
                "adults": 1,
            },
        )
        assert response.status_code == 409
        assert error_code(response) == "R2"

    def test_same_day_turnover_is_not_an_overlap(self, book):
        book(arrival="2026-11-08", departure="2026-11-10")
        book(arrival="2026-11-10", departure="2026-11-12")

    def test_cancelled_stay_frees_the_room(self, client, book):
        first = book()
        client.post(f"/api/reservations/{first['id']}/cancel")
        book()

    @pytest.mark.parametrize("night", range(1, 9))
    def test_r2_holds_under_concurrent_requests(self, database_url, db, clock, night):
        """Twelve simultaneous bookings for one room and night: exactly one gets in, every
        other one is told R2. With this many at once PostgreSQL also aborts some of them to
        break deadlocks; those must be retried, never reported as an outage. Eight rounds,
        because a race that passes once can still fail the next time."""
        racing = Database(database_url, max_size=12)
        racing.open()
        desk = FrontDesk(racing, clock)
        arrival = date(2026, 12, night)
        request = NewReservation("301", "Racer", arrival, date(2026, 12, night + 1), 1, 0, None)

        def attempt(_: int) -> str:
            try:
                desk.create_reservation(request)
            except RuleViolation as exc:
                return exc.code
            return "created"

        try:
            with ThreadPoolExecutor(max_workers=12) as pool:
                outcomes = list(pool.map(attempt, range(12)))
        finally:
            racing.close()
        assert outcomes.count("created") == 1
        assert outcomes.count("R2") == 11


class TestCheckInAndOut:
    def test_full_stay(self, client, book):
        reservation = book(adults=2, children=1)
        checked_in = client.post(
            f"/api/reservations/{reservation['id']}/check-in", json={"adults": 2, "children": 1}
        )
        assert checked_in.status_code == 200
        assert checked_in.json()["status"] == "checked_in"
        assert client.get("/api/rooms/201").json()["status"] == "occupied"

        checked_out = client.post(f"/api/reservations/{reservation['id']}/check-out")
        assert checked_out.json()["status"] == "checked_out"
        assert client.get("/api/rooms/201").json()["status"] == "dirty"

    def test_r3_too_early(self, client, book):
        reservation = book(arrival="2026-11-09", departure="2026-11-11")
        response = client.post(
            f"/api/reservations/{reservation['id']}/check-in", json={"adults": 2}
        )
        assert response.status_code == 409
        assert error_code(response) == "R3"

    def test_r3_late_arrival_next_day(self, client, book, clock):
        reservation = book(arrival="2026-11-08", departure="2026-11-10")
        clock.today = date(2026, 11, 9)
        response = client.post(
            f"/api/reservations/{reservation['id']}/check-in", json={"adults": 2}
        )
        assert response.status_code == 200

    def test_r4_party_mismatch(self, client, book):
        reservation = book(adults=2)
        response = client.post(
            f"/api/reservations/{reservation['id']}/check-in", json={"adults": 3}
        )
        assert error_code(response) == "R4"

    @pytest.mark.parametrize("path", [["out_of_order"], ["out_of_order", "dirty"]])
    def test_r5_room_not_ready(self, client, book, path):
        reservation = book()
        for room_status in path:
            client.patch("/api/rooms/201", json={"status": room_status})
        response = client.post(
            f"/api/reservations/{reservation['id']}/check-in", json={"adults": 2}
        )
        assert error_code(response) == "R5"

    def test_r5_room_still_occupied_by_an_overstaying_guest(self, client, book, clock):
        overstaying = book(arrival="2026-11-06", departure="2026-11-08")
        clock.today = date(2026, 11, 6)
        client.post(f"/api/reservations/{overstaying['id']}/check-in", json={"adults": 2})
        clock.today = date(2026, 11, 8)
        arriving = book(arrival="2026-11-08", departure="2026-11-10")
        response = client.post(f"/api/reservations/{arriving['id']}/check-in", json={"adults": 2})
        assert error_code(response) == "R5"

    def test_r6_check_out_before_check_in(self, client, book):
        reservation = book()
        response = client.post(f"/api/reservations/{reservation['id']}/check-out")
        assert response.status_code == 409
        assert error_code(response) == "R6"

    def test_r6_cannot_cancel_an_arrived_guest(self, client, book):
        reservation = book()
        client.post(f"/api/reservations/{reservation['id']}/check-in", json={"adults": 2})
        response = client.post(f"/api/reservations/{reservation['id']}/cancel")
        assert error_code(response) == "R6"

    def test_unknown_reservation(self, client):
        response = client.post("/api/reservations/4242/check-out")
        assert response.status_code == 404
