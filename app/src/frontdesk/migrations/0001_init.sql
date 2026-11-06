-- Rooms, reservations and night audit reports. Rules refer to docs/domain.md.

-- btree_gist lets one exclusion constraint compare a room number (=) and a date range (&&).
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE rooms (
    number        text     PRIMARY KEY,
    type          text     NOT NULL,
    max_adults    smallint NOT NULL CHECK (max_adults >= 1),
    max_occupancy smallint NOT NULL CHECK (max_occupancy >= max_adults),
    status        text     NOT NULL DEFAULT 'clean'
                  CHECK (status IN ('clean', 'occupied', 'dirty', 'out_of_order'))
);

CREATE TABLE reservations (
    id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_number    text        NOT NULL REFERENCES rooms (number),
    guest_name     text        NOT NULL CHECK (char_length(btrim(guest_name)) BETWEEN 1 AND 200),
    arrival_date   date        NOT NULL,
    departure_date date        NOT NULL,
    adults         smallint    NOT NULL CHECK (adults >= 1),
    children       smallint    NOT NULL DEFAULT 0 CHECK (children >= 0),
    notes          text        CHECK (char_length(notes) <= 500),
    status         text        NOT NULL DEFAULT 'booked'
                   CHECK (status IN ('booked', 'checked_in', 'checked_out', 'cancelled', 'no_show')),
    checked_in_at  timestamptz,
    checked_out_at timestamptz,
    no_show_on     date,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),

    -- R1: a stay covers at least one night.
    CONSTRAINT stay_has_nights CHECK (departure_date > arrival_date),

    -- R2: two active stays in one room never overlap. The database, not the application, is the
    -- guarantee: two requests that arrive in the same millisecond cannot both pass this check.
    CONSTRAINT no_double_booking EXCLUDE USING gist (
        room_number WITH =,
        daterange(arrival_date, departure_date) WITH &&
    ) WHERE (status IN ('booked', 'checked_in'))
);

CREATE INDEX reservations_arrivals_idx   ON reservations (status, arrival_date);
CREATE INDEX reservations_departures_idx ON reservations (status, departure_date);

CREATE TABLE night_audit_reports (
    business_date date        PRIMARY KEY,
    report        jsonb       NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);
