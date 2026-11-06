# FrontDesk API

The hotel front desk API and night audit. It implements [docs/domain.md](../docs/domain.md) and
[docs/api.md](../docs/api.md), and keeps the application's side of
[docs/platform-contract.md](../docs/platform-contract.md).

Python 3.13, FastAPI, PostgreSQL through psycopg 3 with plain SQL, and OpenTelemetry metrics.

## Commands

One package, three commands (contract C13):

```sh
frontdesk serve                      # HTTP server on $PORT (default 8080)
frontdesk migrate                    # apply migrations, then exit; safe to run twice
frontdesk night-audit [--date DAY]   # close a business day (default: yesterday), then exit
```

Configuration comes only from environment variables; the table is in contract C11. The server
also reads `PORT`, `DRAIN_SECONDS` (default 5) and `SHUTDOWN_TIMEOUT_SECONDS` (default 15).

## Layout

| Path | Responsibility |
| --- | --- |
| `src/frontdesk/domain.py` | Business rules R1-R7 as pure functions; no I/O |
| `src/frontdesk/service.py` | Use cases: one transaction each, rows locked while a rule decides |
| `src/frontdesk/api/` | HTTP: routes, request and response models, errors, headers, access log |
| `src/frontdesk/migrations/` | Forward-only SQL, applied in name order |
| `src/frontdesk/migrate.py` | Applies migrations under an advisory lock, refuses edited history |
| `src/frontdesk/night_audit.py` | Closes a day (R7) and writes the report to the database or Blob |
| `src/frontdesk/metrics.py` | Request duration histogram, labels trimmed to the contract |
| `src/frontdesk/server.py` | Uvicorn with a drain-first shutdown on SIGTERM |
| `src/frontdesk/cli.py` | The three commands |
| `scripts/seed_demo.py` | Fills a fresh instance with a believable day through the API |
| `tests/` | Rule tests without a database, API and contract tests against PostgreSQL |

## Design notes

- **R2 lives in the database.** An exclusion constraint on room and date range rejects
  overlapping active stays. A check in application code would let two simultaneous requests
  both pass; `tests/test_reservations.py` fires ten at once and expects exactly one success.
- **Errors name the rule.** A refused request answers `{"error": {"code": "R5", ...}}`, so a
  receptionist, a test and a log search all speak the same language as docs/domain.md.
- **Liveness never touches the database.** `/healthz` answers as long as the process does;
  `/readyz` asks PostgreSQL. A database outage takes pods out of rotation instead of restarting
  them in a loop.
- **An outage stays small.** The probes are `async` and never queue behind business requests,
  readiness uses its own connection rather than the pool, and a request that cannot get a
  connection within three seconds answers `503 UNAVAILABLE` instead of holding a thread.
- **Bad input is a 4xx.** Control characters, oversized IDs and malformed room numbers are
  refused as `422 VALIDATION` before they reach PostgreSQL, so a hostile client cannot raise the
  5xx rate that the canary analysis watches.
- **A business day closes once.** `night-audit` refuses a day that has not ended, and a rerun
  for a closed day returns the stored report without touching any reservation.
- **Shutdown drains first.** On SIGTERM `/readyz` turns `503` for `DRAIN_SECONDS` while requests
  are still served, then Uvicorn stops accepting connections and finishes what is in flight.
- **Dependencies are pinned with hashes.** `requirements.txt` (runtime) and
  `requirements-dev.txt` (runtime and tools) are generated from `pyproject.toml`; the command
  is at the top of each file. Install with `pip install --require-hashes -r requirements.txt`.

## Local development

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r requirements-dev.txt && pip install --no-deps -e .
ruff check . && ruff format --check .
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/frontdesk_test pytest
```

Database tests need a PostgreSQL database whose name ends in `_test`; the tests empty it.
Without `TEST_DATABASE_URL` they are skipped and only the rule tests run.
