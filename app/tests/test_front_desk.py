"""Rooms and the lists a receptionist checks at the start of a shift."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.db


class TestRooms:
    def test_seed_inventory(self, client):
        body = client.get("/api/rooms").json()
        assert body["count"] == 22
        assert body["items"][0] == {
            "number": "101",
            "type": "economy",
            "max_adults": 3,
            "max_occupancy": 3,
            "status": "clean",
        }

    def test_filter_by_status(self, client):
        client.patch("/api/rooms/G01", json={"status": "out_of_order"})
        body = client.get("/api/rooms", params={"status": "out_of_order"}).json()
        assert [room["number"] for room in body["items"]] == ["G01"]

    def test_housekeeping_cycle(self, client):
        assert client.patch("/api/rooms/202", json={"status": "out_of_order"}).status_code == 200
        assert client.patch("/api/rooms/202", json={"status": "dirty"}).status_code == 200
        assert client.patch("/api/rooms/202", json={"status": "clean"}).json()["status"] == "clean"

    def test_occupied_is_not_set_by_hand(self, client):
        response = client.patch("/api/rooms/202", json={"status": "occupied"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ROOM_STATUS"


class TestViews:
    def test_arrivals_put_late_guests_first(self, client, book):
        book(room="402", arrival="2026-11-08", departure="2026-11-10")
        book(room="101", arrival="2026-11-07", departure="2026-11-10")  # did not come yesterday
        book(room="102", arrival="2026-11-09", departure="2026-11-10")  # tomorrow

        items = client.get("/api/front-desk/arrivals").json()["items"]
        assert [(i["room_number"], i["late_arrival"]) for i in items] == [
            ("101", True),
            ("402", False),
        ]

    def test_arrivals_for_another_date(self, client, book):
        book(room="102", arrival="2026-11-09", departure="2026-11-10")
        body = client.get("/api/front-desk/arrivals", params={"date": "2026-11-09"}).json()
        assert body["count"] == 1

    def test_departures_and_overdue(self, client, book, clock):
        from datetime import date

        early = book(room="201", arrival="2026-11-06", departure="2026-11-07")
        today = book(room="202", arrival="2026-11-08", departure="2026-11-09")
        clock.today = date(2026, 11, 6)
        client.post(f"/api/reservations/{early['id']}/check-in", json={"adults": 2})
        clock.today = date(2026, 11, 8)
        client.post(f"/api/reservations/{today['id']}/check-in", json={"adults": 2})

        departures = client.get("/api/front-desk/departures", params={"date": "2026-11-09"}).json()
        assert [(d["room_number"], d["overdue"]) for d in departures["items"]] == [
            ("201", True),
            ("202", False),
        ]
        assert client.get("/api/front-desk/in-house").json()["count"] == 2
