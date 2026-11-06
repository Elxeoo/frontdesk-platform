# Platform Contract

This document is the agreement between the application (`app/`) and the platform that runs it:
Kubernetes, Prometheus and Argo Rollouts. The application keeps these promises; the platform relies on
them. Each clause has a stable ID (`C1` to `C16`) and a check that proves it.

In the checks, `$API` is the application's base URL, for example `http://localhost:8080`.

## Health

- **C1. Liveness.** `GET /healthz` returns `200` while the process can serve HTTP. It checks no
  dependency, so a database outage never restarts the application.
  Check: stop the database, then `curl -s -o /dev/null -w '%{http_code}' $API/healthz` prints `200`.
- **C2. Readiness.** `GET /readyz` returns `200` when the database answers a trivial query within one
  second, and `503` otherwise. Kubernetes stops sending traffic to a pod that is not ready, without
  restarting it.
  Check: stop the database, then the same `curl` against `/readyz` prints `503`.

## Metrics

- **C3. Endpoint.** `GET /metrics` serves metrics in the Prometheus text format.
  Check: `curl -s $API/metrics | head` shows `# HELP` and `# TYPE` lines.
- **C4. Request duration.** Every request is recorded in the histogram
  `http_server_request_duration_seconds`, following the OpenTelemetry HTTP semantic conventions
  (`OTEL_SEMCONV_STABILITY_OPT_IN=http`). The unit is seconds. The labels are `http_request_method`,
  `http_route` and `http_response_status_code`. The bucket boundaries include `0.5`, the latency
  objective.
  Check: `curl -s $API/metrics | grep 'http_server_request_duration_seconds_bucket' | grep 'le="0.5"'`
  returns lines.
- **C5. Route templates.** `http_route` holds the route template, such as `/api/reservations/{id}`,
  never a concrete ID. This keeps the number of series small.
  Check: after a few requests to different reservations, `curl -s $API/metrics | grep http_route`
  shows `{id}` and no numeric IDs.
- **C6. Probes are not traffic.** Requests to `/healthz`, `/readyz` and `/metrics` are not recorded,
  so probes do not dilute the service level indicators.
  Check: call `/healthz` ten times; `curl -s $API/metrics | grep 'http_route="/healthz"'` returns nothing.

## Fault injection

- **C7. Fault switches.** Two environment variables make the application fail on purpose, so the canary
  analysis can be tested. They are read at startup and default to `0`.
  - `FAULT_ERROR_RATE`: share of requests (`0.0` to `1.0`) that return `500`.
  - `FAULT_LATENCY_MS`: delay in milliseconds added to every request.

  Faulty responses are recorded in the metrics exactly like real ones.
  Check: with `FAULT_ERROR_RATE=1`, `GET $API/api/rooms` returns `500`.
- **C8. Faults never touch the platform endpoints.** `/healthz`, `/readyz` and `/metrics` ignore both
  switches. A fault test must exercise the canary analysis, not trigger restarts or hide the evidence.
  Check: with `FAULT_ERROR_RATE=1` and `FAULT_LATENCY_MS=2000`, `/healthz` returns `200` at once.

## Identification

- **C9. Version header.** Every response carries `X-App-Version` with the version set at build time
  (`APP_VERSION`; `dev` when unset).
  Check: `curl -sI $API/healthz | grep -i x-app-version`.
- **C10. Pod header.** Every response carries `X-Served-By` with the pod name (`POD_NAME`, filled by the
  Kubernetes Downward API; the host name when unset). During a canary this shows which pods answer.
  Check: `curl -sI $API/healthz | grep -i x-served-by`.

## Configuration

- **C11. Environment only.** All configuration comes from environment variables. No secret is stored in
  the image or in Git.

  | Variable | Purpose | Source on the platform |
  | --- | --- | --- |
  | `DATABASE_URL` | PostgreSQL connection URI | CloudNativePG `<cluster>-app` Secret, key `uri` |
  | `APP_VERSION` | Version shown in `X-App-Version` | Image build argument |
  | `POD_NAME` | Pod shown in `X-Served-By` | Downward API |
  | `LOG_LEVEL` | `INFO` by default | Deployment manifest |
  | `REPORT_TARGET` | `database` or `blob` | Deployment manifest |
  | `REPORT_CONTAINER_URL` | Blob container for night audit reports | Deployment manifest |
  | `FAULT_ERROR_RATE`, `FAULT_LATENCY_MS` | Fault switches (C7) | Deployment manifest |

- **C12. No keys for Azure.** With `REPORT_TARGET=blob`, the night audit authenticates to Azure Storage
  through Workload Identity. No account key or connection string is used.
  Check: the night audit Job's spec and environment contain no storage key.

## Entry points

- **C13. One image, three commands.**
  - `serve` (default): runs the HTTP server on port `8080`.
  - `migrate`: applies database migrations and exits `0`. Running it twice is safe.
  - `night-audit`: closes the business day (rule R7 in [domain.md](domain.md)), writes the report and
    exits `0`. It exits non-zero on failure, so the Job shows the failure. Running it twice for the same
    business day gives the same result.

  Check: `migrate` twice in a row exits `0` both times.

## Runtime

- **C14. Logs.** Logs go to standard output, one JSON object per line, with at least `timestamp`,
  `level` and `message`. Logs never contain the database URL or guest names.
  Check: `docker logs <container> | head -1 | python3 -m json.tool` parses.
- **C15. Unprivileged and read-only.** The process runs as a non-root user and writes nothing to the
  image filesystem (`PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`), so it works with
  `readOnlyRootFilesystem: true`.
  Check: `docker run --read-only <image>` serves `/healthz`, and `id -u` inside the container is not `0`.
- **C16. Graceful shutdown.** On `SIGTERM`, `/readyz` turns `503` at once so no new traffic arrives,
  requests already in progress finish, and the process exits within 25 seconds, inside the default
  30-second Kubernetes grace period.
  Check: with `FAULT_LATENCY_MS=3000`, start `curl $API/api/rooms` and send `SIGTERM` while it waits;
  the request completes with `200` and the process then exits `0`.
