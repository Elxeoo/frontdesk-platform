"""Entry points: one image, three commands (platform contract C13).

frontdesk serve                       # HTTP server (default)
frontdesk migrate                     # apply database migrations, then exit
frontdesk night-audit [--date DAY]    # close a business day (default: yesterday), then exit
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

from frontdesk.clock import hotel_today
from frontdesk.config import ConfigError, Settings
from frontdesk.logs import configure_logging
from frontdesk.night_audit import DayNotOver

log = logging.getLogger("frontdesk")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="frontdesk", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="run the HTTP server")
    commands.add_parser("migrate", help="apply database migrations")
    audit = commands.add_parser("night-audit", help="close a business day")
    audit.add_argument(
        "--date",
        type=date.fromisoformat,
        help="business day to close, YYYY-MM-DD (default: yesterday in the hotel's time zone)",
    )
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
        configure_logging(settings.log_level)
        match args.command or "serve":
            case "serve":
                _serve(settings)
            case "migrate":
                _migrate(settings)
            case "night-audit":
                today = hotel_today()
                _night_audit(settings, args.date or today - timedelta(days=1), today)
    except ConfigError as exc:
        configure_logging("INFO")
        log.error("invalid configuration", extra={"reason": str(exc)})
        return 2
    except DayNotOver as exc:
        log.error("refusing to close the business day", extra={"reason": str(exc)})
        return 2
    except Exception:
        log.exception("command failed", extra={"command": args.command or "serve"})
        return 1
    return 0


def _serve(settings: Settings) -> None:
    from frontdesk.api import create_app
    from frontdesk.server import serve

    log.info("starting", extra={"version": settings.app_version, "port": settings.port})
    serve(create_app(settings), settings)


def _migrate(settings: Settings) -> None:
    from frontdesk.migrate import migrate

    migrate(settings.require_database_url())


def _night_audit(settings: Settings, business_date: date, today: date) -> None:
    from frontdesk.db import Database
    from frontdesk.night_audit import make_writer, run_night_audit

    db = Database(settings.require_database_url(), max_size=2)
    db.open()
    writer = make_writer(settings, db)
    try:
        run_night_audit(db, writer, business_date, today=today)
    finally:
        if close := getattr(writer, "close", None):
            close()
        db.close()
