// Entry point: wires views, dialogs and actions together and runs the 5-second refresh loop, backing off while the API fails.

import * as actions from './actions.js';
import { ApiError, api, onResponse } from './api.js';
import { initCheckIn, openCheckIn } from './dialogs/checkin.js';
import { initConfirm } from './dialogs/confirm.js';
import { initNewReservation, openNewReservation } from './dialogs/reservation.js';
import { byId } from './dom.js';
import { hotelToday } from './format.js';
import { createPoller } from './poller.js';
import { applySnapshot, state } from './state.js';
import { renderAudit } from './views/audit.js';
import { recordResponse } from './views/badge.js';
import { initConnection, reportFailure, reportSuccess } from './views/connection.js';
import { initDesk, renderDesk } from './views/desk.js';
import { initHeader, renderHeader } from './views/header.js';
import { initRack, renderRack } from './views/rack.js';
import { initRoomMenu, openRoomMenu, refreshRoomMenu } from './views/room-menu.js';

const REFRESH_MS = 5000;
const MAX_BACKOFF_MS = 30_000;
// The night audit report changes once a day, so it is fetched once a minute rather than on every refresh.
const AUDIT_REFRESH_MS = 60_000;

let auditFetchedAt = 0;
let failures = 0;

function loadAudit() {
  if (auditFetchedAt && Date.now() - auditFetchedAt < AUDIT_REFRESH_MS) return state.audit;
  return api.latestAudit().then((report) => {
    auditFetchedAt = Date.now();
    return report;
  });
}

/** Loads every view's data; api.js has validated each body, so state is only touched when all of it is good. */
async function loadSnapshot() {
  const [rooms, arrivals, departures, inHouse, audit] = await Promise.all([
    api.rooms(),
    api.arrivals(),
    api.departures(),
    api.inHouse(),
    loadAudit(),
  ]);
  return { today: hotelToday(), rooms, arrivals, departures, inHouse, audit };
}

/** How long to wait after a failed refresh: the API's Retry-After, else exponential backoff for outages. */
function retryDelay(error) {
  if (error.retryAfter !== null) return Math.min(error.retryAfter * 1000, 5 * 60_000);
  const outage = error.status === 0 || error.status >= 500;
  return outage ? Math.min(REFRESH_MS * 2 ** (failures - 1), MAX_BACKOFF_MS) : REFRESH_MS;
}

/** One refresh; resolves to the delay the poller should wait before the next one. */
async function refresh() {
  try {
    applySnapshot(await loadSnapshot());
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    failures += 1;
    const delay = Math.max(REFRESH_MS, retryDelay(error));
    reportFailure(error, delay);
    return delay;
  }
  failures = 0;
  renderHeader(state);
  renderRack(state);
  refreshRoomMenu();
  renderDesk(state);
  renderAudit(state.audit);
  reportSuccess();
  return REFRESH_MS;
}

const poller = createPoller(refresh, REFRESH_MS);

onResponse(recordResponse);
initHeader();
initConnection({ onRetry: () => poller.run() });
initRack({ onOpen: openRoomMenu });
initRoomMenu({
  setStatus: actions.setRoomStatus,
  checkIn: openCheckIn,
  checkOut: actions.checkOut,
  newReservation: openNewReservation,
});
initDesk({ checkIn: openCheckIn, cancel: actions.cancelReservation, checkOut: actions.checkOut });
initCheckIn({ onCheckedIn: actions.checkedIn });
initNewReservation({ onCreated: actions.reservationCreated });
initConfirm();
actions.initActions({ refresh: () => poller.run() });

byId('new-reservation').addEventListener('click', () => openNewReservation());

poller.run();
