"""Settings read from environment variables (platform contract C11)."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from typing import Literal

import psycopg

ReportTarget = Literal["database", "blob"]

# Contract C16: the process exits within 25 s, inside Kubernetes' default 30 s grace period.
SHUTDOWN_BUDGET_SECONDS = 25
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


class ConfigError(ValueError):
    """Raised when an environment variable holds a value the application cannot use."""


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    app_version: str
    pod_name: str
    log_level: str
    report_target: ReportTarget
    report_container_url: str | None
    fault_error_rate: float
    fault_latency_ms: int
    port: int
    drain_seconds: float
    shutdown_timeout_seconds: int

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if env is None else env)

        report_target = env.get("REPORT_TARGET", "database")
        if report_target not in ("database", "blob"):
            raise ConfigError(f"REPORT_TARGET must be 'database' or 'blob', got {report_target!r}")
        report_container_url = env.get("REPORT_CONTAINER_URL") or None
        if report_target == "blob" and not report_container_url:
            raise ConfigError("REPORT_CONTAINER_URL is required when REPORT_TARGET=blob")

        fault_error_rate = _number(env, "FAULT_ERROR_RATE", 0.0, float)
        if not 0.0 <= fault_error_rate <= 1.0:
            raise ConfigError(f"FAULT_ERROR_RATE must be between 0 and 1, got {fault_error_rate}")
        fault_latency_ms = _number(env, "FAULT_LATENCY_MS", 0, int)
        if fault_latency_ms < 0:
            raise ConfigError(f"FAULT_LATENCY_MS must not be negative, got {fault_latency_ms}")

        log_level = env.get("LOG_LEVEL", "INFO").upper()
        if log_level not in _LOG_LEVELS:
            raise ConfigError(
                f"LOG_LEVEL must be one of {', '.join(_LOG_LEVELS)}, got {log_level!r}"
            )

        drain_seconds = _number(env, "DRAIN_SECONDS", 5.0, float)
        shutdown_timeout_seconds = _number(env, "SHUTDOWN_TIMEOUT_SECONDS", 15, int)
        if drain_seconds < 0 or shutdown_timeout_seconds < 0:
            raise ConfigError("DRAIN_SECONDS and SHUTDOWN_TIMEOUT_SECONDS must not be negative")
        if drain_seconds + shutdown_timeout_seconds > SHUTDOWN_BUDGET_SECONDS:
            raise ConfigError(
                "DRAIN_SECONDS + SHUTDOWN_TIMEOUT_SECONDS must fit in "
                f"{SHUTDOWN_BUDGET_SECONDS} s (contract C16), got "
                f"{drain_seconds + shutdown_timeout_seconds}"
            )

        database_url = env.get("DATABASE_URL", "")
        if database_url:
            try:
                psycopg.conninfo.conninfo_to_dict(database_url)
            except psycopg.ProgrammingError:
                # psycopg's message repeats the input, password included: never log it.
                raise ConfigError("DATABASE_URL is not a valid connection URI") from None

        return cls(
            database_url=database_url,
            app_version=env.get("APP_VERSION") or "dev",
            pod_name=env.get("POD_NAME") or socket.gethostname(),
            log_level=log_level,
            report_target=report_target,
            report_container_url=report_container_url,
            fault_error_rate=fault_error_rate,
            fault_latency_ms=fault_latency_ms,
            port=_number(env, "PORT", 8080, int),
            drain_seconds=drain_seconds,
            shutdown_timeout_seconds=shutdown_timeout_seconds,
        )

    def require_database_url(self) -> str:
        if not self.database_url:
            raise ConfigError("DATABASE_URL is not set")
        return self.database_url


def _number[T: (int, float)](env: dict[str, str], name: str, default: T, kind: type[T]) -> T:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        return kind(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
