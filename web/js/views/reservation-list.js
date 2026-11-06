// One front desk list (arrivals, departures or in-house): rows keyed by reservation ID and updated in place, so a refresh never flickers or steals focus.

import { el, fromTemplate, placeInOrder, replayClass, roomChip, setAttr, setText, slots } from '../dom.js';
import { STATUS_LABEL } from '../domain.js';
import { daysBetween, formatParty, formatStay, plural } from '../format.js';
import { roomByNumber } from '../state.js';

/**
 * @param {object}   config
 * @param {string}   config.key        List name used in the markup: arrivals, departures or inHouse.
 * @param {string}   config.noun       Plural noun for the "no match" message.
 * @param {string}   config.emptyText  Shown when the API returns no items.
 * @param {(item, context: {today: string, room?: object}) => Array<{text: string, tone?: string}>} config.tags  Markers after the guest name.
 * @param {Array<{label: string, primary?: boolean, run: (item) => void}>} config.actions  Row buttons.
 */
export function createReservationList({ key, noun, emptyText, tags, actions }) {
  const tbody = document.querySelector(`tbody[data-list="${key}"]`);
  const table = tbody.closest('table');
  const panel = tbody.closest('[role="tabpanel"]');
  const empty = document.querySelector(`[data-empty="${key}"]`);
  const rows = new Map(); // reservation id -> { row, parts, buttons, item, signature }
  let rendered = false;
  let query = '';

  function createEntry() {
    const row = fromTemplate('tpl-row');
    const parts = slots(row);
    const entry = { row, parts, buttons: [], item: null, signature: '' };
    for (const action of actions) {
      const button = el('button', {
        className: action.primary ? 'btn btn-small btn-primary' : 'btn btn-small',
        text: action.label,
        attrs: { type: 'button' },
      });
      // Handlers read entry.item at click time, so they always act on the latest data.
      button.addEventListener('click', () => action.run(entry.item));
      parts.actions.append(button);
      entry.buttons.push({ button, label: action.label });
    }
    return entry;
  }

  function fill(entry, item, room, markers) {
    const { row, parts } = entry;
    const nights = daysBetween(item.arrival_date, item.departure_date);

    parts.room.replaceChildren(roomChip(item.room_number, room?.status, STATUS_LABEL[room?.status]));
    setText(parts.guest, item.guest_name);
    parts.tags.replaceChildren(
      ...markers.map((marker) => el('span', { className: 'tag', text: marker.text, dataset: marker.tone ? { tone: marker.tone } : {} })),
    );
    setText(parts.stay, formatStay(item.arrival_date, item.departure_date));
    setText(parts.nights, plural(nights, 'night'));
    setText(parts.party, formatParty(item.adults, item.children));
    setText(parts.notes, item.notes || '—');
    parts.notes.parentElement.classList.toggle('is-empty', !item.notes);
    setAttr(parts.notes, 'title', item.notes || null);
    setAttr(row, 'data-tone', markers.find((marker) => marker.tone)?.tone ?? null);
    for (const { button, label } of entry.buttons) {
      setAttr(button, 'aria-label', `${label}: ${item.guest_name}, room ${item.room_number}`);
    }
  }

  function matches(item) {
    return !query || item.guest_name.toLowerCase().includes(query) || item.room_number.toLowerCase().includes(query);
  }

  function applyFilter() {
    let visible = 0;
    for (const { row, item } of rows.values()) {
      const show = matches(item);
      row.hidden = !show;
      if (show) visible += 1;
    }
    table.hidden = visible === 0;
    empty.hidden = visible > 0;
    setText(empty, rows.size === 0 ? emptyText : `No ${noun} match “${query}”.`);
  }

  function render(items, today) {
    const present = new Set(items.map((item) => item.id));
    for (const [id, entry] of rows) {
      if (present.has(id)) continue;
      // Keep keyboard users in the list when the row they are on disappears (checked in, cancelled...).
      if (entry.row.contains(document.activeElement)) panel.focus({ preventScroll: true });
      rows.delete(id);
    }

    const ordered = items.map((item) => {
      let entry = rows.get(item.id);
      const isNew = !entry;
      if (isNew) {
        entry = createEntry();
        rows.set(item.id, entry);
      }
      const room = roomByNumber(item.room_number);
      const markers = tags(item, { today, room });
      const signature = JSON.stringify([item, room?.status, markers]);
      if (signature !== entry.signature) {
        fill(entry, item, room, markers);
        if (rendered) replayClass(entry.row, 'is-flash');
        entry.signature = signature;
      }
      entry.item = item;
      return entry.row;
    });

    placeInOrder(tbody, ordered);
    applyFilter();
    rendered = true;
  }

  function setFilter(text) {
    query = text.trim().toLowerCase();
    applyFilter();
  }

  return { render, setFilter };
}
