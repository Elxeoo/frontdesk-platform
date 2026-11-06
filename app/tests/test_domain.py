"""The rules in docs/domain.md, tested without a database."""

from __future__ import annotations

from datetime import date

import pytest

from frontdesk import domain
from frontdesk.domain import Party, ReservationStatus, Room, RoomStatus, RuleViolation

STANDARD = Room("201", "standard", max_adults=3, max_occupancy=3, status=RoomStatus.CLEAN)
FAMILY = Room("403", "family", max_adults=3, max_occupancy=5, status=RoomStatus.CLEAN)


def nov(day: int) -> date:
    return date(2026, 11, day)


ARRIVAL_DAY = nov(8)
TWO_ADULTS = Party(2, 0)


def rule(exc: pytest.ExceptionInfo[RuleViolation]) -> str:
    return exc.value.code


class TestNewReservation:
    def test_valid_reservation_passes(self):
        domain.check_new_reservation(STANDARD, nov(8), nov(10), Party(2, 1))

    @pytest.mark.parametrize(
        ("arrival", "departure", "party"),
        [
            (nov(10), nov(10), Party(2, 0)),  # no night
            (nov(10), nov(8), Party(2, 0)),  # departure before arrival
            (nov(8), nov(10), Party(0, 2)),  # children alone
            (nov(8), nov(10), Party(4, 0)),  # more adults than the room takes
            (nov(8), nov(10), Party(2, 2)),  # more guests than the room takes
        ],
    )
    def test_r1_refuses(self, arrival, departure, party):
        with pytest.raises(RuleViolation) as exc:
            domain.check_new_reservation(STANDARD, arrival, departure, party)
        assert rule(exc) == "R1"
        assert exc.value.status == 422

    def test_family_room_takes_two_adults_and_three_children(self):
        domain.check_new_reservation(FAMILY, nov(8), nov(10), Party(2, 3))


class TestCheckIn:
    def check(
        self,
        *,
        today=ARRIVAL_DAY,
        status=ReservationStatus.BOOKED,
        arrived=TWO_ADULTS,
        room=STANDARD,
    ):
        domain.check_check_in(
            status=status,
            arrival=ARRIVAL_DAY,
            departure=nov(10),
            booked=TWO_ADULTS,
            arrived=arrived,
            room=room,
            today=today,
        )

    def test_on_arrival_day(self):
        self.check()

    def test_late_arrival_is_still_welcome(self):
        self.check(today=nov(9))

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            ({"today": nov(7)}, "R3"),
            ({"today": nov(10)}, "R3"),
            ({"arrived": Party(3, 0)}, "R4"),
            ({"arrived": Party(1, 1)}, "R4"),
            ({"room": Room("201", "standard", 3, 3, RoomStatus.DIRTY)}, "R5"),
            ({"room": Room("201", "standard", 3, 3, RoomStatus.OUT_OF_ORDER)}, "R5"),
            ({"status": ReservationStatus.CANCELLED}, "R6"),
        ],
    )
    def test_refusals(self, kwargs, expected):
        with pytest.raises(RuleViolation) as exc:
            self.check(**kwargs)
        assert rule(exc) == expected
        assert exc.value.status == 409

    def test_status_is_checked_before_dates(self):
        # A cancelled reservation outside its window is refused for being cancelled, not for R3.
        with pytest.raises(RuleViolation) as exc:
            self.check(status=ReservationStatus.CANCELLED, today=nov(1))
        assert rule(exc) == "R6"


class TestLifecycle:
    def test_only_checked_in_can_check_out(self):
        domain.check_check_out(ReservationStatus.CHECKED_IN)
        with pytest.raises(RuleViolation):
            domain.check_check_out(ReservationStatus.BOOKED)

    def test_only_booked_can_be_cancelled(self):
        domain.check_cancel(ReservationStatus.BOOKED)
        with pytest.raises(RuleViolation):
            domain.check_cancel(ReservationStatus.CHECKED_IN)


class TestRoomTransitions:
    @pytest.mark.parametrize(
        ("source", "target"),
        [
            (RoomStatus.DIRTY, RoomStatus.CLEAN),
            (RoomStatus.CLEAN, RoomStatus.OUT_OF_ORDER),
            (RoomStatus.DIRTY, RoomStatus.OUT_OF_ORDER),
            (RoomStatus.OUT_OF_ORDER, RoomStatus.DIRTY),
        ],
    )
    def test_housekeeping_moves(self, source, target):
        domain.check_room_transition(Room("201", "standard", 3, 3, source), target)

    @pytest.mark.parametrize(
        ("source", "target"),
        [
            (RoomStatus.CLEAN, RoomStatus.OCCUPIED),
            (RoomStatus.OCCUPIED, RoomStatus.DIRTY),
            (RoomStatus.OUT_OF_ORDER, RoomStatus.CLEAN),  # must be inspected first
        ],
    )
    def test_forbidden_moves(self, source, target):
        with pytest.raises(domain.RoomStatusConflict):
            domain.check_room_transition(Room("201", "standard", 3, 3, source), target)


def test_no_show_cutoff_waits_for_the_last_check_in_day():
    # Stay 8-10 November: closing the 8th leaves the 9th open; closing the 9th leaves nothing.
    assert nov(10) > domain.no_show_cutoff(nov(8))
    assert nov(10) <= domain.no_show_cutoff(nov(9))
