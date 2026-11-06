"""The business API under /api (docs/api.md). Handlers translate HTTP to service calls and back."""

from __future__ import annotations

import asyncio
import random
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status

from frontdesk.api import schemas
from frontdesk.api.errors import InjectedFault
from frontdesk.domain import Party, RoomStatus
from frontdesk.service import FrontDesk, NewReservation


def front_desk(request: Request) -> FrontDesk:
    return request.app.state.front_desk


async def fault_switch(request: Request) -> None:
    """Platform contract C7: slow down or fail business requests on purpose. Never C8 endpoints."""
    settings = request.app.state.settings
    if settings.fault_latency_ms:
        await asyncio.sleep(settings.fault_latency_ms / 1000)
    if settings.fault_error_rate and random.random() < settings.fault_error_rate:  # noqa: S311
        raise InjectedFault


router = APIRouter(prefix="/api", dependencies=[Depends(fault_switch)])

Desk = Annotated[FrontDesk, Depends(front_desk)]
OnDate = Annotated[date | None, Query(alias="date", description="Defaults to today.")]
RoomNumber = Annotated[str, Path(pattern=schemas.ROOM_NUMBER)]
ReservationId = Annotated[int, Path(ge=1, le=2**63 - 1)]  # a PostgreSQL bigint


# Rooms


@router.get("/rooms", response_model=schemas.RoomList)
def list_rooms(desk: Desk, room_status: Annotated[RoomStatus | None, Query(alias="status")] = None):
    rooms = desk.list_rooms(room_status)
    return {"items": rooms, "count": len(rooms)}


@router.get("/rooms/{number}", response_model=schemas.Room)
def get_room(number: RoomNumber, desk: Desk):
    return desk.get_room(number)


@router.patch("/rooms/{number}", response_model=schemas.Room)
def change_room_status(number: RoomNumber, body: schemas.RoomStatusChange, desk: Desk):
    return desk.set_room_status(number, body.status)


# Reservations


@router.post(
    "/reservations", response_model=schemas.Reservation, status_code=status.HTTP_201_CREATED
)
def create_reservation(body: schemas.ReservationCreate, desk: Desk, response: Response):
    reservation = desk.create_reservation(
        NewReservation(
            room_number=body.room_number,
            guest_name=body.guest_name,
            arrival_date=body.arrival_date,
            departure_date=body.departure_date,
            adults=body.adults,
            children=body.children,
            notes=body.notes or None,
        )
    )
    response.headers["Location"] = f"/api/reservations/{reservation['id']}"
    return reservation


@router.get("/reservations/{reservation_id}", response_model=schemas.Reservation)
def get_reservation(reservation_id: ReservationId, desk: Desk):
    return desk.get_reservation(reservation_id)


@router.post("/reservations/{reservation_id}/check-in", response_model=schemas.Reservation)
def check_in(reservation_id: ReservationId, body: schemas.CheckIn, desk: Desk):
    return desk.check_in(reservation_id, Party(body.adults, body.children))


@router.post("/reservations/{reservation_id}/check-out", response_model=schemas.Reservation)
def check_out(reservation_id: ReservationId, desk: Desk):
    return desk.check_out(reservation_id)


@router.post("/reservations/{reservation_id}/cancel", response_model=schemas.Reservation)
def cancel(reservation_id: ReservationId, desk: Desk):
    return desk.cancel(reservation_id)


# Front desk views


@router.get("/front-desk/arrivals", response_model=schemas.ReservationList[schemas.Arrival])
def arrivals(desk: Desk, on: OnDate = None):
    rows = desk.arrivals(on or desk.today())
    return {"items": rows, "count": len(rows)}


@router.get("/front-desk/departures", response_model=schemas.ReservationList[schemas.Departure])
def departures(desk: Desk, on: OnDate = None):
    rows = desk.departures(on or desk.today())
    return {"items": rows, "count": len(rows)}


@router.get("/front-desk/in-house", response_model=schemas.ReservationList[schemas.Reservation])
def in_house(desk: Desk):
    rows = desk.in_house()
    return {"items": rows, "count": len(rows)}


# Night audit


@router.get("/night-audit/reports/latest", response_model=schemas.NightAuditReport)
def latest_night_audit(desk: Desk):
    return desk.latest_night_audit()
