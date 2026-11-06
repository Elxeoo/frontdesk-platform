// Operator actions that change data: confirm where needed, call the API, report the outcome and refresh the screen.

import { api } from './api.js';
import { confirmAndRun } from './dialogs/confirm.js';
import { STATUS_LABEL } from './domain.js';
import { formatShortDate, formatStay } from './format.js';
import { state } from './state.js';
import { showErrorToast, showToast } from './views/toasts.js';

let refresh = async () => {};

export function initActions(options) {
  refresh = options.refresh;
}

export async function checkedIn(reservation) {
  showToast(`${reservation.guest_name} checked in to room ${reservation.room_number}.`);
  await refresh();
}

export async function reservationCreated(reservation) {
  showToast(
    `Reservation #${reservation.id} created for ${reservation.guest_name}, room ${reservation.room_number}, ${formatStay(reservation.arrival_date, reservation.departure_date)}.`,
  );
  await refresh();
}

export async function checkOut(reservation) {
  const room = reservation.room_number;
  const early = reservation.departure_date > state.today;
  const done = await confirmAndRun({
    title: `Check out ${reservation.guest_name}?`,
    body: early
      ? `The stay in room ${room} is booked until ${formatShortDate(reservation.departure_date)}; checking out now ends it early. The room goes to housekeeping as dirty.`
      : `Room ${room} goes to housekeeping as dirty.`,
    confirmLabel: early ? 'Check out early' : 'Check out',
    busyLabel: 'Checking out…',
    run: () => api.checkOut(reservation.id),
  });
  if (!done) return;
  showToast(`${reservation.guest_name} checked out of room ${room}. Room ${room} is now dirty.`);
  await refresh();
}

export async function cancelReservation(reservation) {
  const done = await confirmAndRun({
    title: `Cancel the reservation for ${reservation.guest_name}?`,
    body: `Room ${reservation.room_number}, ${formatStay(reservation.arrival_date, reservation.departure_date)}. A cancelled reservation cannot be reopened.`,
    confirmLabel: 'Cancel reservation',
    busyLabel: 'Cancelling…',
    danger: true,
    run: () => api.cancel(reservation.id),
  });
  if (!done) return;
  showToast(`Reservation #${reservation.id} for ${reservation.guest_name} is cancelled.`);
  await refresh();
}

export async function setRoomStatus(room, status) {
  try {
    await api.setRoomStatus(room.number, status);
    showToast(`Room ${room.number} is now ${STATUS_LABEL[status].toLowerCase()}.`);
  } catch (error) {
    showErrorToast(error);
  }
  await refresh();
}
