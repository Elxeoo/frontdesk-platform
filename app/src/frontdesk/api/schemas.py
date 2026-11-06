"""Request and response bodies, matching docs/api.md field for field."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from frontdesk.domain import ReservationStatus, RoomStatus

# Control characters are refused here: PostgreSQL rejects NUL outright, and none belongs in a
# name. Notes may keep line breaks and tabs.
NO_CONTROL = r"^[^\x00-\x1f\x7f]*$"
NOTES_TEXT = r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*$"
ROOM_NUMBER = r"^[A-Za-z0-9]{1,10}$"

GuestName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=NO_CONTROL)
]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500, pattern=NOTES_TEXT)]
RoomNumber = Annotated[str, StringConstraints(strip_whitespace=True, pattern=ROOM_NUMBER)]
# Counts are bounded only loosely here; R1 and R4 judge them against the room and the booking.
Count = Annotated[int, Field(ge=0, le=20)]


class Room(BaseModel):
    number: str
    type: str
    max_adults: int
    max_occupancy: int
    status: RoomStatus


class Reservation(BaseModel):
    id: int
    room_number: str
    guest_name: str
    arrival_date: date
    departure_date: date
    adults: int
    children: int
    notes: str | None
    status: ReservationStatus


class Arrival(Reservation):
    late_arrival: bool


class Departure(Reservation):
    overdue: bool


class RoomList(BaseModel):
    items: list[Room]
    count: int


class ReservationList[T: Reservation](BaseModel):
    items: list[T]
    count: int


class ReservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_number: RoomNumber
    guest_name: GuestName
    arrival_date: date
    departure_date: date
    adults: Count
    children: Count = 0
    notes: Notes | None = None


class CheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adults: Count
    children: Count = 0


class RoomStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RoomStatus


class NightAuditReport(BaseModel):
    business_date: date
    checked_in: int
    checked_out: int
    no_shows: list[int]
    in_house: int
    occupancy_rate: float
