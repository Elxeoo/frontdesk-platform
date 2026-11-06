"""Migrations are idempotent and protect history; configuration fails early and clearly."""

from __future__ import annotations

import pytest

from frontdesk.config import ConfigError, Settings
from frontdesk.migrate import Migration, MigrationError, load_migrations, migrate


@pytest.mark.db
def test_second_run_applies_nothing(database_url):
    assert migrate(database_url) == []


@pytest.mark.db
def test_edited_migration_is_refused(database_url):
    first, *rest = load_migrations()
    edited = Migration(first.version, first.sql + "\n-- edited")
    with pytest.raises(MigrationError, match="changed after it was applied"):
        migrate(database_url, [edited, *rest])


def test_migrations_are_ordered():
    versions = [m.version for m in load_migrations()]
    assert versions == sorted(versions)
    assert versions[0] == "0001_init"


def test_defaults():
    settings = Settings.from_env({"POD_NAME": "p"})
    assert settings.app_version == "dev"
    assert settings.report_target == "database"
    assert settings.fault_error_rate == 0.0
    assert settings.port == 8080


@pytest.mark.parametrize(
    "env",
    [
        {"FAULT_ERROR_RATE": "1.5"},
        {"FAULT_ERROR_RATE": "lots"},
        {"FAULT_LATENCY_MS": "-1"},
        {"REPORT_TARGET": "ftp"},
        {"REPORT_TARGET": "blob"},  # without REPORT_CONTAINER_URL
    ],
)
def test_invalid_values_are_refused(env):
    with pytest.raises(ConfigError):
        Settings.from_env(env)
