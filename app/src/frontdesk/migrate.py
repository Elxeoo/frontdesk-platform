"""Forward-only SQL migrations (platform contract C13, `migrate` command).

Files in `migrations/` are applied in name order, each in its own transaction, and recorded in
`schema_migrations` with a checksum. Running the command again applies nothing new. An advisory
lock makes concurrent runs (two Job pods, a retry overlapping a slow first attempt) take turns.
A migration that was edited after it was applied stops the run, because history must not change.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from importlib import resources

import psycopg

log = logging.getLogger(__name__)

# Arbitrary but fixed: every `migrate` process must ask for the same lock.
_LOCK_KEY = 7_204_101


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode()).hexdigest()


def load_migrations() -> list[Migration]:
    folder = resources.files("frontdesk") / "migrations"
    files = sorted((f for f in folder.iterdir() if f.name.endswith(".sql")), key=lambda f: f.name)
    return [Migration(f.name.removesuffix(".sql"), f.read_text(encoding="utf-8")) for f in files]


def migrate(database_url: str, migrations: list[Migration] | None = None) -> list[str]:
    """Apply pending migrations and return the versions applied by this run."""
    migrations = load_migrations() if migrations is None else migrations
    applied_now: list[str] = []
    with psycopg.connect(
        database_url, autocommit=True, application_name="frontdesk-migrate"
    ) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (_LOCK_KEY,))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version    text        PRIMARY KEY,
                    checksum   text        NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            done = dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())
            for migration in migrations:
                recorded = done.get(migration.version)
                if recorded is not None:
                    if recorded != migration.checksum:
                        raise MigrationError(
                            f"Migration {migration.version} changed after it was applied. "
                            "Add a new migration instead of editing an old one."
                        )
                    continue
                with conn.transaction():
                    conn.execute(migration.sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                        (migration.version, migration.checksum),
                    )
                log.info("migration applied", extra={"version": migration.version})
                applied_now.append(migration.version)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))
    if not applied_now:
        log.info("database schema is up to date")
    return applied_now
