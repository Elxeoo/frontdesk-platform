"""Business rules from docs/domain.md, as pure functions with no I/O.

Each check raises `RuleViolation` carrying the rule ID, so the API can tell the caller which rule
was broken. The database enforces R2 on its own; the service layer translates that error.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
import os


class RoomStatus(StrEnum):
    CLEAN = "clean"
    OCCUPIED = "occupied"
    DIRTY = "dirty"
    OUT_OF_ORDER = "out_of_order"


class ReservationStatus(StrEnum):
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


ACTIVE_STATUSES = frozenset({ReservationStatus.BOOKED, ReservationStatus.CHECKED_IN})

# Housekeeping may only make these changes; occupied is entered and left through check-in/out.
MANUAL_ROOM_TRANSITIONS: dict[RoomStatus, frozenset[RoomStatus]] = {
    RoomStatus.DIRTY: frozenset({RoomStatus.CLEAN, RoomStatus.OUT_OF_ORDER}),
    RoomStatus.CLEAN: frozenset({RoomStatus.OUT_OF_ORDER}),
    RoomStatus.OUT_OF_ORDER: frozenset({RoomStatus.DIRTY}),
    RoomStatus.OCCUPIED: frozenset(),
}


class DomainError(Exception):
    """A request the hotel's rules do not allow. `status` is the HTTP status it maps to."""

    status: int = 409

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class RuleViolation(DomainError):
    def __init__(self, rule: str, message: str) -> None:
        super().__init__(rule, message)
        self.status = 422 if rule == "R1" else 409


class RoomStatusConflict(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__("ROOM_STATUS", message)


class NotFound(DomainError):
    status = 404

    def __init__(self, message: str) -> None:
        super().__init__("NOT_FOUND", message)


@dataclass(frozen=True, slots=True)
class Room:
    number: str
    type: str
    max_adults: int
    max_occupancy: int
    status: RoomStatus


@dataclass(frozen=True, slots=True)
class Party:
    adults: int
    children: int


def check_new_reservation(room: Room, arrival: date, departure: date, party: Party) -> None:
    """R1: valid dates, at least one adult, and a party that fits the room."""
    if departure <= arrival:
        raise RuleViolation("R1", "The departure date must be after the arrival date.")
    if party.adults < 1:
        raise RuleViolation("R1", "A reservation needs at least one adult.")
    if party.children < 0:
        raise RuleViolation("R1", "The number of children cannot be negative.")
    if party.adults > room.max_adults:
        raise RuleViolation(
            "R1", f"Room {room.number} takes at most {room.max_adults} adults, not {party.adults}."
        )
    if party.adults + party.children > room.max_occupancy:
        raise RuleViolation(
            "R1",
            f"Room {room.number} takes at most {room.max_occupancy} guests, "
            f"not {party.adults + party.children}.",
        )


def check_check_in(
    *,
    status: ReservationStatus,
    arrival: date,
    departure: date,
    booked: Party,
    arrived: Party,
    room: Room,
    today: date,
) -> None:
    """R6, R3, R4 and R5, in rule order after the status check that makes the others meaningful."""
    if status is not ReservationStatus.BOOKED:
        raise RuleViolation(
            "R6", f"Only a booked reservation can be checked in; this one is {status}."
        )
    if today < arrival:
        raise RuleViolation("R3", f"Check-in opens on the arrival date, {arrival.isoformat()}.")
    if today >= departure:
        raise RuleViolation("R3", f"The stay ended on {departure.isoformat()}; check-in is closed.")
    if arrived != booked:
        raise RuleViolation(
            "R4",
            f"The reservation is for {booked.adults} adults and {booked.children} children; "
            f"{arrived.adults} adults and {arrived.children} children arrived. "
            "Change the reservation first.",
        )
    if room.status is not RoomStatus.CLEAN:
        raise RuleViolation("R5", f"Room {room.number} is {room.status}, not clean.")


def check_check_out(status: ReservationStatus) -> None:
    """R6: only a checked-in guest can check out."""
    if status is not ReservationStatus.CHECKED_IN:
        raise RuleViolation(
            "R6", f"Only a checked-in reservation can be checked out; this one is {status}."
        )


def check_cancel(status: ReservationStatus) -> None:
    """R6: only a reservation that has not arrived can be cancelled."""
    if status is not ReservationStatus.BOOKED:
        raise RuleViolation(
            "R6", f"Only a booked reservation can be cancelled; this one is {status}."
        )


def check_room_transition(room: Room, target: RoomStatus) -> None:
    if target not in MANUAL_ROOM_TRANSITIONS[room.status]:
        raise RoomStatusConflict(f"Room {room.number} cannot go from {room.status} to {target}.")


def no_show_cutoff(business_date: date) -> date:
    """R7: closing day D leaves no check-in day for stays that depart on or before D + 1."""
    return business_date + timedelta(days=1)
