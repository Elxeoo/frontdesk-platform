"""The hotel's notion of "today". Every business date is taken in the hotel's time zone."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

HOTEL_TIMEZONE = ZoneInfo("Europe/Istanbul")

Clock = Callable[[], date]


def hotel_today() -> date:
    return datetime.now(HOTEL_TIMEZONE).date()
