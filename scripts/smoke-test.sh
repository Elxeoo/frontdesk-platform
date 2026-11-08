#!/usr/bin/env bash
# Smoke test for a running FrontDesk API.
# It only asks questions; it never stops or breaks anything, so it is safe on any environment.
# Usage: API_URL=http://127.0.0.1:18080 scripts/smoke-test.sh
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:18080}"
failures=0

# check NAME EXPECTED ACTUAL: compares two values, prints PASS or FAIL, counts failures.
check() {
  if [ "$2" = "$3" ]; then
    echo "PASS  $1"
  else
    echo "FAIL  $1 (expected $2, got $3)"
    failures=$((failures + 1))
  fi
}

# code METHOD PATH [JSON_BODY]: prints only the HTTP status code of the answer.
code() {
  curl -s -o /dev/null -w '%{http_code}' -X "$1" \
    -H 'Content-Type: application/json' ${3:+-d "$3"} "$API_URL$2"
}

# found TEXT PATTERN: prints yes if the pattern is in the text, no otherwise.
found() {
  if grep -qi -- "$2" <<<"$1"; then echo yes; else echo no; fi
}

# --- Health (C1, C2) ---
check "liveness /healthz is 200" 200 "$(code GET /healthz)"
# TODO 1: readiness /readyz is 200
check "readiness /readyz is 200" 200 "$(code GET  /readyz)"
# --- Rooms ---
# TODO 2: GET /api/rooms is 200
check "GET /api/rooms is 200" 200 "$(code GET /api/rooms)"
# --- Reservation rules (R2, R6) ---
# A date far in the future, different on every run, so runs never collide.
offset=$((RANDOM % 3000 + 400))
arrival="$(date -d "+$offset days" +%F)"
departure="$(date -d "+$((offset + 2)) days" +%F)"
booking="{\"room_number\": \"201\", \"guest_name\": \"Smoke Test\", \"arrival_date\": \"$arrival\", \"departure_date\": \"$departure\", \"adults\": 1}"

created="$(curl -s -w '\n%{http_code}' -X POST -H 'Content-Type: application/json' -d "$booking" "$API_URL/api/reservations")"
check "new reservation is 201" 201 "$(tail -n1 <<<"$created")"
id="$(head -n1 <<<"$created" | python3 -c 'import json, sys; print(json.load(sys.stdin)["id"])')"

# TODO 3: the same booking again is 409 (double booking, R2)
check "double booking is 409" 409 "$(code POST /api/reservations "$booking")"
# TODO 4: POST /api/reservations/$id/cancel is 200 (also cleans up after the test)
check "cancel reservation is 200" 200 "$(code POST /api/reservations/$id/cancel)"
# TODO 5: check-in on the cancelled reservation is 409 (order of operations, R6)
#         body: '{"adults": 1, "children": 0}'
check "check-in on cancelled reservation is 409" 409 "$(code POST "/api/reservations/$id/check-in" '{"adults": 1, "children": 0}')"
# --- Metrics and headers (C3, C4, C9, C10); after traffic, so the histogram has data ---
metrics="$(curl -s "$API_URL/metrics")"
check "metrics has the 0.5 s bucket" yes "$(found "$metrics" 'http_server_request_duration_seconds_bucket.*le="0.5"')"

headers="$(curl -s -D - -o /dev/null "$API_URL/healthz")"
check "version header is present" yes "$(found "$headers" '^x-app-version:')"
check "pod header is present" yes "$(found "$headers" '^x-served-by:')"

echo
if [ "$failures" -eq 0 ]; then
  echo "All checks passed."
else
  echo "$failures check(s) failed."
  exit 1
fi
