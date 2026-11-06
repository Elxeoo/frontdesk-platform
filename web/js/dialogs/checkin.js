// Check-in dialog: shows the booking, takes the party at the desk and posts the check-in; rule errors (R3-R6) stay inside the dialog.

import { api } from '../api.js';
import { byId, el, roomChip, setText, slots } from '../dom.js';
import { STATUS_LABEL, roomTypeLabel } from '../domain.js';
import { daysBetween, formatParty, formatShortDate, formatStay, plural } from '../format.js';
import { roomByNumber } from '../state.js';
import { clearFormError, openDialog, runLocked, setupDialog, showFormError } from './dialog.js';

const dialog = byId('checkin-dialog');
const form = byId('checkin-form');
const parts = slots(dialog);
const adultsInput = byId('ci-adults');
const childrenInput = byId('ci-children');

let reservation = null;
let onCheckedIn = () => {};

function readCount(input) {
  const value = Number(input.value);
  return input.value.trim() !== '' && Number.isInteger(value) && value >= 0 ? value : null;
}

async function submit(event) {
  event.preventDefault();
  const adults = readCount(adultsInput);
  const children = readCount(childrenInput);
  if (adults === null || children === null) {
    showFormError(parts.error, { code: 'VALIDATION', message: 'Enter the number of adults and children as whole numbers.' });
    (adults === null ? adultsInput : childrenInput).focus();
    return;
  }
  const booking = reservation;
  const outcome = await runLocked(dialog, parts.submit, 'Checking in…', () => api.checkIn(booking.id, { adults, children }));
  if (outcome.ok) {
    if (outcome.current) dialog.close();
    onCheckedIn(outcome.value);
  } else if (outcome.current) {
    showFormError(parts.error, outcome.error);
  }
}

export function initCheckIn(options) {
  onCheckedIn = options.onCheckedIn;
  setupDialog(dialog);
  form.addEventListener('submit', submit);
  form.addEventListener('input', () => clearFormError(parts.error));
}

export function openCheckIn(booking) {
  reservation = booking;
  const room = roomByNumber(booking.room_number);
  const nights = daysBetween(booking.arrival_date, booking.departure_date);

  parts.guest.replaceChildren(booking.guest_name);
  if (booking.late_arrival) {
    parts.guest.append(' ', el('span', { className: 'tag', text: `Late · due ${formatShortDate(booking.arrival_date)}`, dataset: { tone: 'warn' } }));
  }
  parts.room.replaceChildren(roomChip(booking.room_number, room?.status, STATUS_LABEL[room?.status]));
  if (room) {
    parts.room.append(el('span', { className: 'summary-aside', text: `${roomTypeLabel(room.type)} · ${STATUS_LABEL[room.status]}` }));
  }
  setText(parts.stay, `${formatStay(booking.arrival_date, booking.departure_date)} · ${plural(nights, 'night')}`);
  setText(parts.party, formatParty(booking.adults, booking.children));
  setText(parts.notes, booking.notes ?? '');
  parts['notes-row'].hidden = !booking.notes;

  const notReady = room && room.status !== 'clean';
  parts.warning.hidden = !notReady;
  if (notReady) {
    setText(parts.warning, `Room ${room.number} is ${STATUS_LABEL[room.status].toLowerCase()}. Check-in needs a clean room (R5).`);
  }

  adultsInput.value = String(booking.adults);
  childrenInput.value = String(booking.children ?? 0);
  setText(byId('checkin-title'), `Check in ${booking.guest_name}`);
  clearFormError(parts.error);
  openDialog(dialog, adultsInput);
}
