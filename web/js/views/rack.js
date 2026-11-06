// Room rack: one tile per room grouped by building and floor, plus the status legend; tiles are updated in place on every refresh.

import { byId, el, fromTemplate, placeInOrder, replayClass, setAttr, setText, slots, statusSwatch } from '../dom.js';
import { ROOM_STATUSES, STATUS_LABEL, compareRooms, roomGroup, roomTypeLabel } from '../domain.js';
import { formatShortDate, plural } from '../format.js';
import { arrivalFor, occupantOf } from '../state.js';

const rackEl = byId('rack');
const legendEl = byId('rack-legend');

const tiles = new Map(); // room number -> { tile, parts, status }
const floors = new Map(); // group key -> { section, parts }
const legendCounts = new Map(); // status -> count element

export function initRack({ onOpen }) {
  rackEl.addEventListener('click', (event) => {
    const tile = event.target.closest('.tile');
    if (tile) onOpen(tile.dataset.room, tile);
  });
}

function floorFor(group) {
  let floor = floors.get(group.key);
  if (!floor) {
    const section = fromTemplate('tpl-floor');
    const parts = slots(section);
    parts.label.textContent = group.label;
    floor = { section, parts };
    floors.set(group.key, floor);
  }
  return floor;
}

function tileFor(number) {
  let entry = tiles.get(number);
  if (!entry) {
    const tile = fromTemplate('tpl-tile');
    tile.dataset.room = number;
    entry = { tile, parts: slots(tile), status: null };
    tiles.set(number, entry);
  }
  return entry;
}

/** What a tile says besides number and type: a detail line, an optional flag line and its tone. */
function describe(room, today) {
  const status = STATUS_LABEL[room.status] ?? room.status;
  const spoken = [`Room ${room.number}`, roomTypeLabel(room.type), status];
  const occupant = room.status === 'occupied' ? occupantOf(room.number) : undefined;
  const arrival = arrivalFor(room.number);

  if (occupant) {
    let flag = `Until ${formatShortDate(occupant.departure_date)}`;
    let tone = null;
    if (occupant.departure_date < today) {
      flag = 'Overdue';
      tone = 'danger';
    } else if (occupant.departure_date === today) {
      flag = 'Due out today';
    }
    spoken.push(occupant.guest_name, flag);
    return { detail: occupant.guest_name, flag, tone, label: spoken.join(', ') };
  }

  if (arrival) {
    const ready = room.status === 'clean';
    spoken.push(`arrival expected: ${arrival.guest_name}`);
    if (!ready) spoken.push('room not ready');
    return { detail: status, flag: `Arr. ${arrival.guest_name}`, tone: ready ? null : 'warn', label: spoken.join(', ') };
  }

  return { detail: status, flag: '', tone: null, label: spoken.join(', ') };
}

function updateTile(entry, room, today) {
  const { tile, parts } = entry;
  const view = describe(room, today);

  if (entry.status && entry.status !== room.status) replayClass(tile, 'is-changed');
  entry.status = room.status;

  setAttr(tile, 'data-status', room.status);
  setAttr(tile, 'data-flag', view.tone);
  setAttr(tile, 'aria-label', view.label);
  setAttr(tile, 'title', view.label);
  setAttr(parts.icon, 'href', `#i-${room.status}`);
  setText(parts.number, room.number);
  setText(parts.type, roomTypeLabel(room.type));
  setText(parts.detail, view.detail);
  setText(parts.flag, view.flag);
}

function renderLegend(rooms) {
  if (!legendCounts.size) {
    for (const status of ROOM_STATUSES) {
      const count = el('span', { className: 'legend-count tabular' });
      legendEl.append(
        el('li', { className: 'legend-item' }, [statusSwatch(status), el('span', { text: STATUS_LABEL[status] }), count]),
      );
      legendCounts.set(status, count);
    }
  }
  for (const status of ROOM_STATUSES) {
    setText(legendCounts.get(status), rooms.filter((room) => room.status === status).length);
  }
}

export function renderRack(state) {
  renderLegend(state.rooms);

  if (!state.rooms.length) {
    tiles.clear();
    floors.clear();
    rackEl.replaceChildren(el('p', { className: 'placeholder', text: 'The API returned no rooms.' }));
    return;
  }

  const tilesByFloor = new Map();
  for (const room of [...state.rooms].sort(compareRooms)) {
    const floor = floorFor(roomGroup(room.number));
    const entry = tileFor(room.number);
    updateTile(entry, room, state.today);
    if (!tilesByFloor.has(floor)) tilesByFloor.set(floor, []);
    tilesByFloor.get(floor).push(entry.tile);
  }

  for (const [floor, floorTiles] of tilesByFloor) {
    setText(floor.parts.count, plural(floorTiles.length, 'room'));
    placeInOrder(floor.parts.rooms, floorTiles);
  }
  placeInOrder(rackEl, [...tilesByFloor.keys()].map((floor) => floor.section));

  const present = new Set(state.rooms.map((room) => room.number));
  for (const number of tiles.keys()) {
    if (!present.has(number)) tiles.delete(number);
  }
  for (const [key, floor] of floors) {
    if (!tilesByFloor.has(floor)) floors.delete(key);
  }
}
