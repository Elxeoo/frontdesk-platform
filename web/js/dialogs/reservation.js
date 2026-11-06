// New reservation dialog: room picker and stay fields, R1 checks before sending, and the API's answer (R1, R2) shown in the dialog.

import { api } from '../api.js';
import { byId, el, setAttr, setText, slots } from '../dom.js';
import { STATUS_LABEL, capacityLabel, compareRooms, roomGroup, roomTypeLabel } from '../domain.js';
import { addDays, daysBetween, formatParty, hotelToday, plural } from '../format.js';
import { roomByNumber, state } from '../state.js';
import { clearFormError, openDialog, runLocked, setupDialog, showFormError } from './dialog.js';

const dialog = byId('reservation-dialog');
const form = byId('reservation-form');
const parts = slots(dialog);
const field = {
  room: byId('nr-room'),
  guest: byId('nr-guest'),
  arrival: byId('nr-arrival'),
  departure: byId('nr-departure'),
  adults: byId('nr-adults'),
  children: byId('nr-children'),
  notes: byId('nr-notes'),
};
const message = {
  room: byId('nr-room-error'),
  guest: byId('nr-guest-error'),
  departure: byId('nr-departure-error'),
  party: byId('nr-party-error'),
};
const roomInfo = byId('nr-room-info');
const summary = byId('nr-summary');

let attempted = false;
let onCreated = () => {};

function count(input) {
  const value = Number(input.value);
  return input.value.trim() !== '' && Number.isInteger(value) ? value : null;
}

/** Client-side mirror of R1. The API stays the source of truth and repeats these checks. */
function validate() {
  const room = roomByNumber(field.room.value);
  const adults = count(field.adults);
  const children = field.children.value.trim() === '' ? 0 : count(field.children);
  const errors = {};

  if (!room) errors.room = 'Choose a room.';
  if (!field.guest.value.trim()) errors.guest = 'Enter the name of the main guest.';
  if (!field.arrival.value || !field.departure.value) {
    errors.departure = 'Enter arrival and departure dates.';
  } else if (field.departure.value <= field.arrival.value) {
    errors.departure = 'Departure must be after arrival (R1).';
  }
  if (adults === null || adults < 1) {
    errors.party = 'At least one adult is required (R1).';
  } else if (children === null || children < 0) {
    errors.party = 'Children must be zero or more.';
  } else if (room && adults > room.max_adults) {
    errors.party = `Room ${room.number} takes up to ${plural(room.max_adults, 'adult')} (R1).`;
  } else if (room && adults + children > room.max_occupancy) {
    errors.party = `Room ${room.number} sleeps at most ${plural(room.max_occupancy, 'guest')} (R1).`;
  }

  const invalidFields = {
    room: [field.room],
    guest: [field.guest],
    departure: [field.departure],
    party: [field.adults, field.children],
  };
  for (const [key, inputs] of Object.entries(invalidFields)) {
    const text = attempted ? errors[key] : undefined;
    setText(message[key], text ?? '');
    message[key].hidden = !text;
    for (const input of inputs) setAttr(input, 'aria-invalid', text ? 'true' : null);
  }
  return { valid: Object.keys(errors).length === 0, adults, children, firstInvalid: Object.keys(errors)[0] };
}

function updateInfo() {
  const room = roomByNumber(field.room.value);
  if (room) {
    const status = room.status === 'clean' ? '' : ` · now ${STATUS_LABEL[room.status].toLowerCase()}`;
    setText(roomInfo, `${roomTypeLabel(room.type)} · ${capacityLabel(room)}${status}`);
  } else {
    setText(roomInfo, '');
  }

  const nights = field.arrival.value && field.departure.value ? daysBetween(field.arrival.value, field.departure.value) : 0;
  const adults = count(field.adults);
  const children = count(field.children) ?? 0;
  setText(summary, nights > 0 && adults > 0 ? `${plural(nights, 'night')} · ${formatParty(adults, children)}` : '');
}

function fillRooms(selected) {
  const groups = new Map();
  for (const room of [...state.rooms].sort(compareRooms)) {
    const group = roomGroup(room.number);
    if (!groups.has(group.key)) groups.set(group.key, el('optgroup', { attrs: { label: group.label } }));
    const unavailable = room.status === 'out_of_order' ? ' · out of order' : '';
    groups.get(group.key).append(
      el('option', {
        text: `${room.number} · ${roomTypeLabel(room.type)} · sleeps ${room.max_occupancy}${unavailable}`,
        attrs: { value: room.number },
      }),
    );
  }
  const placeholder = el('option', { text: 'Choose a room', attrs: { value: '', disabled: '' } });
  field.room.replaceChildren(placeholder, ...groups.values());
  field.room.value = selected && roomByNumber(selected) ? selected : '';
}

async function submit(event) {
  event.preventDefault();
  attempted = true;
  const check = validate();
  if (!check.valid) {
    const focusTarget = { room: field.room, guest: field.guest, departure: field.departure, party: field.adults };
    focusTarget[check.firstInvalid].focus();
    return;
  }

  const body = {
    room_number: field.room.value,
    guest_name: field.guest.value.trim(),
    arrival_date: field.arrival.value,
    departure_date: field.departure.value,
    adults: check.adults,
    children: check.children,
  };
  const notes = field.notes.value.trim();
  if (notes) body.notes = notes;

  const outcome = await runLocked(dialog, parts.submit, 'Creating…', () => api.createReservation(body));
  if (outcome.ok) {
    if (outcome.current) dialog.close();
    onCreated(outcome.value);
  } else if (outcome.current) {
    showFormError(parts.error, outcome.error);
  }
}

export function initNewReservation(options) {
  onCreated = options.onCreated;
  setupDialog(dialog);
  form.addEventListener('submit', submit);

  field.arrival.addEventListener('change', () => {
    // Keep the stay valid while the operator moves the arrival date.
    if (field.arrival.value && field.departure.value <= field.arrival.value) {
      field.departure.value = addDays(field.arrival.value, 1);
    }
    // The input handler validated the old departure; check again so a stale R1 message clears.
    validate();
  });
  form.addEventListener('input', () => {
    clearFormError(parts.error);
    validate();
    updateInfo();
  });
  form.addEventListener('change', updateInfo);
}

export function openNewReservation(roomNumber) {
  attempted = false;
  fillRooms(roomNumber);
  const room = roomByNumber(field.room.value);
  const today = hotelToday();

  field.guest.value = '';
  field.arrival.value = today;
  field.departure.value = addDays(today, 1);
  field.adults.value = String(Math.min(2, room?.max_adults ?? 2));
  field.children.value = '0';
  field.notes.value = '';

  clearFormError(parts.error);
  validate();
  updateInfo();
  openDialog(dialog, room ? field.guest : field.room);
}
