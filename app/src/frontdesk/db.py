"""PostgreSQL access: a connection pool for requests and a separate readiness check."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

READINESS_TIMEOUT_SECONDS = 1.0
# A request waits this long for a free connection, then fails fast (503) instead of holding a
# worker thread while the database is away.
POOL_WAIT_SECONDS = 3.0


class DatabaseUnavailable(Exception):
    """No connection could be had in time: the database is down, failing over or saturated."""


def aborted_by_database(exc: BaseException) -> bool:
    """True for SQLSTATE class 40, "transaction rollback": a deadlock or serialization failure.

    Checked by code, not class: psycopg models `DeadlockDetected` (40P01) as a sibling of
    `TransactionRollback` (40000), not a subclass, so `isinstance` alone would miss it.
    """
    return isinstance(exc, psycopg.Error) and (exc.sqlstate or "").startswith("40")


class Database:
    def __init__(self, url: str, *, min_size: int = 1, max_size: int = 10) -> None:
        self._url = url
        self._pool: ConnectionPool[psycopg.Connection[DictRow]] = ConnectionPool(
            url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row, "application_name": "frontdesk"},
            # Do not block startup: the API must come up (and report not ready) while the
            # database is still starting, instead of crashing in a restart loop.
            open=False,
            timeout=POOL_WAIT_SECONDS,
            check=ConnectionPool.check_connection,
        )

    def open(self) -> None:
        self._pool.open(wait=False)

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def transaction(self) -> Iterator[psycopg.Connection[DictRow]]:
        """A connection inside one transaction: committed on success, rolled back on error.

        A pool timeout or a lost connection (both `OperationalError`) becomes
        `DatabaseUnavailable`. A transaction PostgreSQL aborted to break a deadlock is also an
        `OperationalError`, but the database is fine and a retry succeeds, so it passes through
        unchanged for the caller to retry, like rule violations and every other error.
        """
        try:
            with self._pool.connection() as conn, conn.transaction():
                yield conn
        except psycopg.OperationalError as exc:
            if aborted_by_database(exc):
                raise
            raise DatabaseUnavailable from exc

    async def is_ready(self) -> bool:
        """True when the database answers within one second (contract C2).

        Uses its own short-lived connection, not the pool or a worker thread, so a busy or
        exhausted pool can never make a healthy pod look unready, or the other way round.
        """
        try:
            async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
                conn = await psycopg.AsyncConnection.connect(
                    self._url, connect_timeout=1, application_name="frontdesk-readiness"
                )
                async with conn:
                    await conn.execute("SELECT 1")
        except (psycopg.Error, TimeoutError, OSError):
            return False
        return True
