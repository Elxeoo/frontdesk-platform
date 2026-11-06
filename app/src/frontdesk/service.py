"""Front desk use cases: each method is one transaction that reads, checks the rules and writes.

Rows that a decision depends on are locked with `FOR UPDATE`, so two receptionists acting on the
same reservation or room at the same moment are applied one after the other, never interleaved.
Every SQL statement is a literal with bound parameters; no SQL is built from strings.
"""

from __future__ import annotations

import functools
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg
from psycopg import errors
from psycopg.rows import DictRow

from frontdesk import domain
from frontdesk.clock import Clock
from frontdesk.db import Database, DatabaseUnavailable, aborted_by_database
from frontdesk.domain import NotFound, Party, ReservationStatus, Room, RoomStatus, RuleViolation

log = logging.getLogger(__name__)

Row = dict[str, Any]
Connection = psycopg.Connection[DictRow]

_ATTEMPTS = 5


def retry_when_aborted[**P, R](method: Callable[P, R]) -> Callable[P, R]:
    """Run a write transaction again when PostgreSQL aborts it to resolve a conflict.

    Row locks keep the common races in a queue, but two transactions can still wait on each other
    in a circle, for example a check-in and a new booking for the same room and overlapping
    nights. PostgreSQL breaks the circle by aborting one of them (SQLSTATE class 40). The abort
    is transient: run again, the transaction sees the other's committed work and gets the right
    answer. A short random pause keeps the retries from colliding again.
    """

    @functools.wraps(method)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        for attempt in range(1, _ATTEMPTS + 1):
            try:
                return method(*args, **kwargs)
            except psycopg.OperationalError as exc:
                if not aborted_by_database(exc):
                    raise
                log.info(
                    "transaction aborted by the database, retrying",
                    extra={
                        "operation": method.__name__,
                        "attempt": attempt,
                        "reason": exc.sqlstate,
                    },
                )
                time.sleep(random.uniform(0.01, 0.05) * attempt)  # noqa: S311 - jitter, not security
        raise DatabaseUnavailable(f"{method.__name__} was aborted {_ATTEMPTS} times in a row")

    return wrapper


@dataclass(frozen=True, slots=True)
class NewReservation:
    room_number: str
    guest_name: str
    arrival_date: date
    departure_date: date
    adults: int
    children: int
    notes: str | None


class FrontDesk:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def today(self) -> date:
        return self._clock()

    # Rooms

    def list_rooms(self, status: RoomStatus | None = None) -> list[Row]:
        with self._db.transaction() as conn:
            return conn.execute(
                "SELECT * FROM rooms WHERE %(status)s::text IS NULL OR status = %(status)s "
                "ORDER BY number",
                {"status": status},
            ).fetchall()

    def get_room(self, number: str) -> Row:
        with self._db.transaction() as conn:
            return _find_room(conn, number)

    @retry_when_aborted
    def set_room_status(self, number: str, target: RoomStatus) -> Row:
        with self._db.transaction() as conn:
            room = _to_room(_find_room(conn, number, lock=True))
            domain.check_room_transition(room, target)
            return conn.execute(
                "UPDATE rooms SET status = %s WHERE number = %s RETURNING *", (target, number)
            ).fetchone()

    # Reservations

    @retry_when_aborted
    def create_reservation(self, new: NewReservation) -> Row:
        party = Party(new.adults, new.children)
        with self._db.transaction() as conn:
            # Locking the room makes bookings for one room take turns. Without it, simultaneous
            # bookings all insert first and then wait on each other inside the R2 constraint
            # check, which ends in deadlocks. The constraint stays the guarantee; the lock only
            # puts the contenders in a queue. Bookings for different rooms still run in parallel.
            room = _to_room(_find_room(conn, new.room_number, lock=True))
            domain.check_new_reservation(room, new.arrival_date, new.departure_date, party)
            try:
                with conn.transaction():
                    return conn.execute(
                        """
                        INSERT INTO reservations (room_number, guest_name, arrival_date,
                                                  departure_date, adults, children, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING *
                        """,
                        (
                            new.room_number,
                            new.guest_name,
                            new.arrival_date,
                            new.departure_date,
                            new.adults,
                            new.children,
                            new.notes,
                        ),
                    ).fetchone()
            except errors.ExclusionViolation:
                raise RuleViolation(
                    "R2",
                    f"Room {new.room_number} is already booked for part of "
                    f"{new.arrival_date.isoformat()} to {new.departure_date.isoformat()}.",
                ) from None

    def get_reservation(self, reservation_id: int) -> Row:
        with self._db.transaction() as conn:
            return _find_reservation(conn, reservation_id)

    @retry_when_aborted
    def check_in(self, reservation_id: int, arrived: Party) -> Row:
        with self._db.transaction() as conn:
            reservation = _find_reservation(conn, reservation_id, lock=True)
            room = _to_room(_find_room(conn, reservation["room_number"], lock=True))
            domain.check_check_in(
                status=ReservationStatus(reservation["status"]),
                arrival=reservation["arrival_date"],
                departure=reservation["departure_date"],
                booked=Party(reservation["adults"], reservation["children"]),
                arrived=arrived,
                room=room,
                today=self.today(),
            )
            conn.execute("UPDATE rooms SET status = 'occupied' WHERE number = %s", (room.number,))
            return conn.execute(
                """
                UPDATE reservations
                SET status = 'checked_in', checked_in_at = now(), updated_at = now()
                WHERE id = %s RETURNING *
                """,
                (reservation_id,),
            ).fetchone()

    @retry_when_aborted
    def check_out(self, reservation_id: int) -> Row:
        with self._db.transaction() as conn:
            reservation = _find_reservation(conn, reservation_id, lock=True)
            domain.check_check_out(ReservationStatus(reservation["status"]))
            conn.execute(
                "UPDATE rooms SET status = 'dirty' WHERE number = %s", (reservation["room_number"],)
            )
            return conn.execute(
                """
                UPDATE reservations
                SET status = 'checked_out', checked_out_at = now(), updated_at = now()
                WHERE id = %s RETURNING *
                """,
                (reservation_id,),
            ).fetchone()

    @retry_when_aborted
    def cancel(self, reservation_id: int) -> Row:
        with self._db.transaction() as conn:
            reservation = _find_reservation(conn, reservation_id, lock=True)
            domain.check_cancel(ReservationStatus(reservation["status"]))
            return conn.execute(
                """
                UPDATE reservations SET status = 'cancelled', updated_at = now()
                WHERE id = %s RETURNING *
                """,
                (reservation_id,),
            ).fetchone()

    # Front desk views

    def arrivals(self, on: date) -> list[Row]:
        """Expected arrivals; late ones, carried over from earlier days by R3, come first."""
        with self._db.transaction() as conn:
            return conn.execute(
                """
                SELECT *, arrival_date < %(on)s AS late_arrival
                FROM reservations
                WHERE status = 'booked' AND arrival_date <= %(on)s AND departure_date > %(on)s
                ORDER BY late_arrival DESC, room_number
                """,
                {"on": on},
            ).fetchall()

    def departures(self, on: date) -> list[Row]:
        """Checked-in guests due to leave; a departure date before `on` means overdue."""
        with self._db.transaction() as conn:
            return conn.execute(
                """
                SELECT *, departure_date < %(on)s AS overdue
                FROM reservations
                WHERE status = 'checked_in' AND departure_date <= %(on)s
                ORDER BY room_number
                """,
                {"on": on},
            ).fetchall()

    def in_house(self) -> list[Row]:
        with self._db.transaction() as conn:
            return conn.execute(
                "SELECT * FROM reservations WHERE status = 'checked_in' ORDER BY room_number"
            ).fetchall()

    def latest_night_audit(self) -> Row:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT report FROM night_audit_reports ORDER BY business_date DESC LIMIT 1"
            ).fetchone()
        if row is None:
            raise NotFound("No night audit has run yet.")
        return row["report"]


def _find_room(conn: Connection, number: str, *, lock: bool = False) -> Row:
    if lock:
        query = "SELECT * FROM rooms WHERE number = %s FOR UPDATE"
    else:
        query = "SELECT * FROM rooms WHERE number = %s"
    row = conn.execute(query, (number,)).fetchone()
    if row is None:
        raise NotFound(f"Room {number} does not exist.")
    return row


def _find_reservation(conn: Connection, reservation_id: int, *, lock: bool = False) -> Row:
    if lock:
        query = "SELECT * FROM reservations WHERE id = %s FOR UPDATE"
    else:
        query = "SELECT * FROM reservations WHERE id = %s"
    row = conn.execute(query, (reservation_id,)).fetchone()
    if row is None:
        raise NotFound(f"Reservation {reservation_id} does not exist.")
    return row


def _to_room(row: Row) -> Room:
    return Room(
        number=row["number"],
        type=row["type"],
        max_adults=row["max_adults"],
        max_occupancy=row["max_occupancy"],
        status=RoomStatus(row["status"]),
    )
