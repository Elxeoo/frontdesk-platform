// Popover for a room tile: the housekeeping changes the room allows, check-in or check-out of its guest, and a new booking for it.

import { byId, el, icon, statusSwatch } from '../dom.js';
import { STATUS_LABEL, capacityLabel, housekeepingActions, roomTypeLabel } from '../domain.js';
import { formatParty, formatShortDate, formatStay } from '../format.js';
import { arrivalFor, occupantOf, roomByNumber, state } from '../state.js';

const menu = byId('room-menu');
let handlers = null;
let current = null; // { number, anchor, signature }

function signatureOf(room) {
  return [room.status, occupantOf(room.number)?.id, arrivalFor(room.number)?.id].join('|');
}

function item({ leading, label, hint, run }) {
  const button = el('button', { className: 'menu-item', attrs: { type: 'button' } }, [
    leading,
    el('span', { className: 'menu-item-text' }, [
      el('span', { className: 'menu-item-label', text: label }),
      el('span', { className: 'menu-item-hint', text: hint }),
    ]),
  ]);
  button.addEventListener('click', () => {
    close();
    run();
  });
  return button;
}

function iconSlot(name) {
  return el('span', { className: 'menu-item-icon' }, [icon(name)]);
}

function build(room) {
  const occupant = room.status === 'occupied' ? occupantOf(room.number) : undefined;
  const arrival = arrivalFor(room.number);

  const head = el('div', { className: 'menu-head' }, [
    el('p', { className: 'menu-title', attrs: { id: 'room-menu-title' } }, [
      el('span', { text: `Room ${room.number}` }),
      el('span', { className: 'menu-status', dataset: { status: room.status } }, [
        icon(room.status),
        el('span', { text: STATUS_LABEL[room.status] ?? room.status }),
      ]),
    ]),
    el('p', { className: 'menu-sub', text: `${roomTypeLabel(room.type)} · ${capacityLabel(room)}` }),
  ]);
  if (occupant) {
    head.append(el('p', { className: 'menu-sub', text: `${occupant.guest_name} · ${formatStay(occupant.arrival_date, occupant.departure_date)}` }));
  }

  const content = [head];
  const housekeeping = housekeepingActions(room.status);
  if (housekeeping.length) {
    content.push(el('p', { className: 'menu-group eyebrow', text: 'Housekeeping' }));
    for (const action of housekeeping) {
      content.push(item({
        leading: statusSwatch(action.to),
        label: action.label,
        hint: action.hint,
        run: () => handlers.setStatus(room, action.to),
      }));
    }
  }

  content.push(el('p', { className: 'menu-group eyebrow', text: 'Front desk' }));
  if (occupant) {
    const due = occupant.departure_date <= state.today ? 'Due out' : `Booked until ${formatShortDate(occupant.departure_date)}`;
    content.push(item({
      leading: iconSlot('occupied'),
      label: `Check out ${occupant.guest_name}`,
      hint: due,
      run: () => handlers.checkOut(occupant),
    }));
  }
  if (arrival && room.status === 'clean') {
    content.push(item({
      leading: iconSlot('clean'),
      label: `Check in ${arrival.guest_name}`,
      hint: formatParty(arrival.adults, arrival.children),
      run: () => handlers.checkIn(arrival),
    }));
  } else if (arrival) {
    head.append(el('p', { className: 'menu-sub menu-warn', text: `${arrival.guest_name} is arriving. Check-in needs a clean room (R5).` }));
  }
  content.push(item({
    leading: iconSlot('plus'),
    label: 'New reservation',
    hint: `Book room ${room.number}`,
    run: () => handlers.newReservation(room.number),
  }));

  menu.replaceChildren(...content);
}

function position(anchor) {
  const edge = 8;
  const gap = 6;
  const viewportWidth = document.documentElement.clientWidth;
  const viewportHeight = document.documentElement.clientHeight;
  const target = anchor.getBoundingClientRect();
  const box = menu.getBoundingClientRect();

  const left = Math.min(Math.max(target.left, edge), viewportWidth - box.width - edge);
  let top = target.bottom + gap;
  if (top + box.height > viewportHeight - edge) top = Math.max(edge, target.top - gap - box.height);

  menu.style.setProperty('--menu-left', `${Math.round(left)}px`);
  menu.style.setProperty('--menu-top', `${Math.round(top)}px`);
}

function items() {
  return [...menu.querySelectorAll('.menu-item')];
}

function close({ restoreFocus = true } = {}) {
  if (!current) return;
  const { anchor } = current;
  current = null;
  const focusWasInside = menu.contains(document.activeElement);
  menu.hidePopover();
  anchor.setAttribute('aria-expanded', 'false');
  if (restoreFocus && focusWasInside && anchor.isConnected) anchor.focus();
}

function onKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault();
    close();
    return;
  }
  const list = items();
  const index = list.indexOf(document.activeElement);
  const moves = { ArrowDown: index + 1, ArrowUp: index - 1, Home: 0, End: list.length - 1 };
  if (event.key in moves) {
    event.preventDefault();
    list[(moves[event.key] + list.length) % list.length]?.focus();
  }
}

export function initRoomMenu(actionHandlers) {
  handlers = actionHandlers;
  // The popover is manual: dismissal is handled here, so clicking the same tile again toggles the menu.
  menu.addEventListener('keydown', onKeydown);
  menu.addEventListener('focusout', (event) => {
    if (current && event.relatedTarget && !menu.contains(event.relatedTarget) && event.relatedTarget !== current.anchor) {
      close({ restoreFocus: false });
    }
  });
  document.addEventListener('pointerdown', (event) => {
    if (current && !menu.contains(event.target) && !current.anchor.contains(event.target)) close({ restoreFocus: false });
  });
  window.addEventListener('resize', () => close({ restoreFocus: false }));
  window.addEventListener('scroll', () => close({ restoreFocus: false }), { passive: true });
}

export function openRoomMenu(number, anchor) {
  if (current?.number === number) {
    close();
    return;
  }
  close({ restoreFocus: false });
  const room = roomByNumber(number);
  if (!room) return;

  current = { number, anchor, signature: signatureOf(room) };
  build(room);
  menu.showPopover();
  position(anchor);
  anchor.setAttribute('aria-expanded', 'true');
  items()[0]?.focus();
}

/** Called after each refresh: rebuilds an open menu whose room changed, or closes it if the room is gone. */
export function refreshRoomMenu() {
  if (!current) return;
  const room = roomByNumber(current.number);
  if (!room || !current.anchor.isConnected) {
    close({ restoreFocus: false });
    return;
  }
  const signature = signatureOf(room);
  if (signature === current.signature) return;

  const focusIndex = items().indexOf(document.activeElement);
  current.signature = signature;
  build(room);
  position(current.anchor);
  const list = items();
  if (focusIndex >= 0) list[Math.min(focusIndex, list.length - 1)]?.focus();
}
