# API

The HTTP API of the FrontDesk application. Business rules (`R1` to `R7`) are defined in
[domain.md](domain.md); platform endpoints (`/healthz`, `/readyz`, `/metrics`) in
[platform-contract.md](platform-contract.md).

## Conventions

- Base path: `/api`. Request and response bodies are JSON (`Content-Type: application/json`).
- Dates use `YYYY-MM-DD`. "Today" is the current date in `Europe/Istanbul`.
- Room numbers are strings, because some rooms are not numeric (`G01`).
- Lists return an object, so fields can be added later without breaking clients:
  `{"items": [...], "count": 2}`.
- There is no authentication. The API is meant for a lab and is listed as a known limitation.

### Errors

Every error has the same shape:

```json
{"error": {"code": "R2", "message": "Room 201 is already booked for 2026-11-08 to 2026-11-10."}}
```

| Status | When | `code` |
| --- | --- | --- |
| `404` | The room or reservation does not exist. | `NOT_FOUND` |
| `422` | The body is malformed, or the new reservation breaks R1. | `VALIDATION` or `R1` |
| `409` | The request conflicts with the current state: double booking or a check-in, check-out or cancel that a rule forbids. | `R2` to `R6` |
| `409` | A room status change that the room status diagram does not allow. | `ROOM_STATUS` |
| `503` | The database cannot be reached right now. Comes with `Retry-After`. | `UNAVAILABLE` |

When a request breaks several rules, one is reported. The reservation's status (R6) is checked
first, because the other check-in rules mean nothing for a cancelled or finished stay; the rest
follow rule order.

## Resources

**Room**

```json
{"number": "201", "type": "standard", "max_adults": 3, "max_occupancy": 3, "status": "clean"}
```

**Reservation**

```json
{
  "id": 17,
  "room_number": "201",
  "guest_name": "Ayse Demir",
  "arrival_date": "2026-11-08",
  "departure_date": "2026-11-10",
  "adults": 2,
  "children": 1,
  "notes": "Honeymoon",
  "status": "booked"
}
```

`notes` is optional free text for special requests, such as a honeymoon or a late arrival.

## Rooms

| Method and path | Purpose | Success |
| --- | --- | --- |
| `GET /api/rooms` | All rooms. Optional filter `?status=clean`. | `200` |
| `GET /api/rooms/{number}` | One room. | `200` |
| `PATCH /api/rooms/{number}` | Housekeeping status change, body `{"status": "clean"}`. | `200` |

`PATCH` accepts only the manual transitions in the room status diagram: `dirty` to `clean`, `clean` or
`dirty` to `out_of_order`, and `out_of_order` to `dirty`. A room becomes `occupied` or leaves it only
through check-in and check-out.

## Reservations

| Method and path | Purpose | Success | Rules checked |
| --- | --- | --- | --- |
| `POST /api/reservations` | Create a reservation. | `201` + `Location` header | R1, R2 |
| `GET /api/reservations/{id}` | One reservation. | `200` | |
| `POST /api/reservations/{id}/check-in` | Check in, body `{"adults": 2, "children": 1}`. | `200` | R3, R4, R5, R6 |
| `POST /api/reservations/{id}/check-out` | Check out. The room becomes `dirty`. | `200` | R6 |
| `POST /api/reservations/{id}/cancel` | Cancel a reservation that has not arrived. | `200` | R6 |

Create request body:

```json
{
  "room_number": "201",
  "guest_name": "Ayse Demir",
  "arrival_date": "2026-11-08",
  "departure_date": "2026-11-10",
  "adults": 2,
  "children": 1,
  "notes": "Honeymoon"
}
```

`children` defaults to `0`; `notes` is optional. Every successful call returns the full reservation.

## Front desk views

These are the lists a receptionist checks at the start of a shift. Arrivals and departures take an
optional `?date=` (default: today); in-house always shows who is in the hotel now.

| Method and path | Shows | Order |
| --- | --- | --- |
| `GET /api/front-desk/arrivals` | Expected arrivals: `booked` and `arrival_date <= date < departure_date`. Includes late arrivals carried over from earlier days (R3); these carry `"late_arrival": true`. | Late arrivals first, then room number |
| `GET /api/front-desk/departures` | `checked_in` with `departure_date <= date`. A date before `date` means the guest is overdue. | Room number |
| `GET /api/front-desk/in-house` | `checked_in` guests. | Room number |

## Night audit

The night audit runs as a command (`night-audit`, see the platform contract), not as an endpoint.
It closes a business day and writes a report:

```json
{
  "business_date": "2026-11-08",
  "checked_in": 6,
  "checked_out": 4,
  "no_shows": [21],
  "in_house": 14,
  "occupancy_rate": 0.7
}
```

`occupancy_rate` is the rooms occupied that night divided by the rooms not `out_of_order` when the
audit runs. A day is closed once: running the audit again for the same day returns the stored
report and changes nothing. Only a day that has ended can be closed.

| Method and path | Purpose | Success |
| --- | --- | --- |
| `GET /api/night-audit/reports/latest` | The most recent report, when `REPORT_TARGET=database`. | `200`, or `404` before the first audit |

## Seed data

`migrate` creates the schema and, when the rooms table is empty, inserts this inventory: a small
resort with a garden building and a six-floor main building.

| Rooms | Type | Max adults | Max occupancy | Notes |
| --- | --- | --- | --- | --- |
| G01, G02 | `garden` | 2 | 2 | Separate older building, two beds |
| G03, G04 | `garden` | 3 | 3 | With a sofa bed |
| 101 to 103 | `economy` | 3 | 3 | No view |
| 201 to 204 | `standard` | 3 | 3 | Garden or roof view |
| 301 to 303 | `side_sea_view` | 3 | 3 | Partial sea view |
| 401, 402 | `sea_view` | 3 | 3 | Full sea view |
| 403, 404, 501, 502 | `family` | 3 | 5 | Double bed, two single beds and a sofa bed |
| 505, 605 | `king_suite` | 6 | 8 | Corner suite, two rooms joined |

Every room starts `clean`. In the main building, every room except family rooms and suites has two
single beds or one double bed, plus a sofa bed that fits an adult or a child.

Demo reservations are not part of the migration. They are created through this API by a seed script,
with dates relative to the day it runs, so the front desk views are never empty and the seed also
exercises the API.
