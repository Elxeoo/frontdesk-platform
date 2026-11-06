// Front desk panel: arrivals, departures and in-house lists with their markers, actions, tab counts and the guest or room filter.

import { byId, setText } from '../dom.js';
import { STATUS_LABEL } from '../domain.js';
import { daysBetween, formatShortDate, plural } from '../format.js';
import { createReservationList } from './reservation-list.js';
import { initTabs } from './tabs.js';

const lists = {};

function overdueTag(item, today) {
  const days = daysBetween(item.departure_date, today);
  return days > 0 ? { text: `Overdue ${plural(days, 'day')}`, tone: 'danger' } : null;
}

function arrivalTags(item, { room }) {
  const tags = [];
  if (item.late_arrival) tags.push({ text: `Late · due ${formatShortDate(item.arrival_date)}`, tone: 'warn' });
  if (room && room.status !== 'clean') tags.push({ text: `Room ${STATUS_LABEL[room.status].toLowerCase()}`, tone: 'warn' });
  return tags;
}

function departureTags(item, { today }) {
  return [overdueTag(item, today)].filter(Boolean);
}

function inHouseTags(item, { today }) {
  const overdue = overdueTag(item, today);
  if (overdue) return [overdue];
  return item.departure_date === today ? [{ text: 'Due out today' }] : [];
}

export function initDesk({ checkIn, cancel, checkOut }) {
  lists.arrivals = createReservationList({
    key: 'arrivals',
    noun: 'arrivals',
    emptyText: 'No arrivals expected today.',
    tags: arrivalTags,
    actions: [
      { label: 'Check in', primary: true, run: checkIn },
      { label: 'Cancel', run: cancel },
    ],
  });
  lists.departures = createReservationList({
    key: 'departures',
    noun: 'departures',
    emptyText: 'No departures due today.',
    tags: departureTags,
    actions: [{ label: 'Check out', primary: true, run: checkOut }],
  });
  lists.inHouse = createReservationList({
    key: 'inHouse',
    noun: 'guests',
    emptyText: 'No guests are checked in.',
    tags: inHouseTags,
    actions: [{ label: 'Check out', run: checkOut }],
  });

  byId('desk-filter').addEventListener('input', (event) => {
    for (const list of Object.values(lists)) list.setFilter(event.target.value);
  });
  initTabs(byId('desk-tabs'));
}

export function renderDesk(state) {
  for (const [key, list] of Object.entries(lists)) {
    list.render(state[key], state.today);
    setText(document.querySelector(`[data-count="${key}"]`), state[key].length);
  }
}
