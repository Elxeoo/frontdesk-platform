"""Night audit (platform contract C13, `night-audit` command): close one business day.

Closing day D marks the reservations that can no longer arrive as no-shows (rule R7) and writes a
report. A day is closed once: when a report for D already exists, a rerun returns it and changes
nothing, so a retried Job never produces a different answer. Only a day that has ended can be
closed; closing today or a future day would turn live bookings into no-shows for good.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Protocol

from psycopg.types.json import Jsonb

from frontdesk.clock import HOTEL_TIMEZONE
from frontdesk.config import Settings
from frontdesk.db import Database
from frontdesk.domain import no_show_cutoff

log = logging.getLogger(__name__)

Report = dict[str, Any]

_TZ = str(HOTEL_TIMEZONE)


class DayNotOver(ValueError):
    """The business day asked for has not ended yet."""


class ReportWriter(Protocol):
    def existing(self, business_date: date) -> Report | None:
        """The report already stored for this day, if any."""
        ...

    def write(self, report: Report) -> Report:
        """Store the report unless one exists for its day; return the stored report."""
        ...


def run_night_audit(
    db: Database, writer: ReportWriter, business_date: date, *, today: date
) -> Report:
    if business_date >= today:
        raise DayNotOver(
            f"{business_date.isoformat()} has not ended yet (today is {today.isoformat()})."
        )
    if (report := writer.existing(business_date)) is not None:
        log.info("business day already closed", extra={"business_date": str(business_date)})
        return report

    with db.transaction() as conn:
        conn.execute(
            """
            UPDATE reservations
            SET status = 'no_show', no_show_on = %(day)s, updated_at = now()
            WHERE status = 'booked' AND departure_date <= %(cutoff)s
            """,
            {"day": business_date, "cutoff": no_show_cutoff(business_date)},
        )
        counts = conn.execute(
            """
            SELECT
                count(*) FILTER (WHERE (checked_in_at AT TIME ZONE %(tz)s)::date = %(day)s)
                    AS checked_in,
                count(*) FILTER (WHERE (checked_out_at AT TIME ZONE %(tz)s)::date = %(day)s)
                    AS checked_out,
                count(DISTINCT room_number) FILTER (
                    WHERE (checked_in_at AT TIME ZONE %(tz)s)::date <= %(day)s
                      AND (checked_out_at IS NULL
                           OR (checked_out_at AT TIME ZONE %(tz)s)::date > %(day)s)
                ) AS in_house
            FROM reservations
            """,
            {"tz": _TZ, "day": business_date},
        ).fetchone()
        no_shows = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM reservations WHERE no_show_on = %s ORDER BY id", (business_date,)
            )
        ]
        # Room status is not kept per day, so the denominator is the inventory at close time.
        sellable = conn.execute(
            "SELECT count(*) AS n FROM rooms WHERE status <> 'out_of_order'"
        ).fetchone()["n"]

    occupancy = min(counts["in_house"] / sellable, 1.0) if sellable else 0.0
    report: Report = {
        "business_date": business_date.isoformat(),
        "checked_in": counts["checked_in"],
        "checked_out": counts["checked_out"],
        "no_shows": no_shows,
        "in_house": counts["in_house"],
        "occupancy_rate": round(occupancy, 3),
    }
    stored = writer.write(report)
    log.info("night audit finished", extra={"report": stored})
    return stored


class DatabaseReportWriter:
    def __init__(self, db: Database) -> None:
        self._db = db

    def existing(self, business_date: date) -> Report | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT report FROM night_audit_reports WHERE business_date = %s",
                (business_date,),
            ).fetchone()
        return None if row is None else row["report"]

    def write(self, report: Report) -> Report:
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO night_audit_reports (business_date, report) VALUES (%s, %s)
                ON CONFLICT (business_date) DO NOTHING
                """,
                (report["business_date"], Jsonb(report)),
            )
            return conn.execute(
                "SELECT report FROM night_audit_reports WHERE business_date = %s",
                (report["business_date"],),
            ).fetchone()["report"]


class BlobReportWriter:
    """Writes `night-audit/<date>.json` to Azure Blob Storage through Workload Identity (C12).

    `WorkloadIdentityCredential` is used on purpose instead of `DefaultAzureCredential`: the
    default chain would also accept a client secret from the environment, and C12 promises none.
    """

    def __init__(self, container_url: str) -> None:
        # Imported here so the API process never loads the Azure SDK.
        from azure.identity import WorkloadIdentityCredential
        from azure.storage.blob import ContainerClient

        self._credential = WorkloadIdentityCredential()
        self._container = ContainerClient.from_container_url(
            container_url, credential=self._credential
        )

    def _blob(self, business_date: str):
        return self._container.get_blob_client(f"night-audit/{business_date}.json")

    def existing(self, business_date: date) -> Report | None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return json.loads(self._blob(business_date.isoformat()).download_blob().readall())
        except ResourceNotFoundError:
            return None

    def write(self, report: Report) -> Report:
        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import ContentSettings

        blob = self._blob(report["business_date"])
        try:
            blob.upload_blob(
                json.dumps(report, indent=2).encode(),
                overwrite=False,
                content_settings=ContentSettings(content_type="application/json"),
            )
        except ResourceExistsError:
            return json.loads(blob.download_blob().readall())
        return report

    def close(self) -> None:
        self._container.close()
        self._credential.close()


def make_writer(settings: Settings, db: Database) -> ReportWriter:
    if settings.report_target == "blob":
        assert settings.report_container_url is not None  # checked in Settings.from_env
        return BlobReportWriter(settings.report_container_url)
    return DatabaseReportWriter(db)
