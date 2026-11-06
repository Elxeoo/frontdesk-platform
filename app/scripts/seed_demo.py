"""Fill a fresh FrontDesk with a believable day, using only the public API.

    python scripts/seed_demo.py http://localhost:8080

Dates are relative to today, so the front desk views are never empty. Going through the API
(instead of SQL) means the seed also proves that the API works. Guests are fictional.
Uses only the standard library, so it runs anywhere Python does.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HOTEL_TIMEZONE = ZoneInfo("Europe/Istanbul")

# room, guest, arrival (days from today), nights, adults, children, notes, checked in already
STAYS = [
    ("401", "Mila Hoffmann", -2, 5, 2, 0, "Honeymoon", True),
    ("403", "Okafor family", -1, 7, 2, 2, None, True),
    ("505", "Ines Carvalho", -3, 4, 4, 2, "Anniversary dinner booked", True),
    ("302", "Daniel Novak", -1, 2, 1, 0, None, True),
    ("G03", "Lukas Becker", -1, 3, 3, 0, None, False),  # did not come yesterday: a late arrival
    ("201", "Sara Lindqvist", 0, 3, 2, 0, "Arriving on a late flight", False),
    ("202", "Kenji Watanabe", 0, 4, 2, 1, None, False),
    ("404", "Elena Petrova", 0, 6, 3, 1, "Repeat guest", False),
    ("301", "Amira Haddad", 1, 3, 2, 0, None, False),
    ("102", "Tomas Ruiz", 2, 2, 1, 0, None, False),
]
HOUSEKEEPING = [("203", "out_of_order"), ("G02", "out_of_order")]


def call(base: str, method: str, path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(  # noqa: S310 - the base URL is the operator's own argument
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310
            return json.load(response)
    except urllib.error.HTTPError as exc:
        error = json.load(exc).get("error", {})
        raise SystemExit(
            f"{method} {path}: {exc.code} {error.get('code')} {error.get('message')}"
        ) from None


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    base = sys.argv[1].rstrip("/")
    today = datetime.now(HOTEL_TIMEZONE).date()

    if call(base, "GET", "/api/front-desk/in-house")["count"]:
        raise SystemExit("This FrontDesk already has guests; the demo seed is for a fresh one.")

    for room, guest, offset, nights, adults, children, notes, checked_in in STAYS:
        arrival: date = today + timedelta(days=offset)
        reservation = call(
            base,
            "POST",
            "/api/reservations",
            {
                "room_number": room,
                "guest_name": guest,
                "arrival_date": arrival.isoformat(),
                "departure_date": (arrival + timedelta(days=nights)).isoformat(),
                "adults": adults,
                "children": children,
                "notes": notes,
            },
        )
        if checked_in:
            call(
                base,
                "POST",
                f"/api/reservations/{reservation['id']}/check-in",
                {"adults": adults, "children": children},
            )
    for room, status in HOUSEKEEPING:
        call(base, "PATCH", f"/api/rooms/{room}", {"status": status})

    print(f"Seeded {len(STAYS)} reservations around {today.isoformat()}.")


if __name__ == "__main__":
    main()
