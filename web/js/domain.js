// Hotel knowledge the screen needs (see docs/domain.md): room grouping, status labels, housekeeping transitions and rule titles.

export const ROOM_STATUSES = ['clean', 'occupied', 'dirty', 'out_of_order'];

export const STATUS_LABEL = {
  clean: 'Clean',
  occupied: 'Occupied',
  dirty: 'Dirty',
  out_of_order: 'Out of order',
};

const ROOM_TYPE_LABEL = {
  garden: 'Garden',
  economy: 'Economy',
  standard: 'Standard',
  side_sea_view: 'Side sea view',
  sea_view: 'Sea view',
  family: 'Family',
  king_suite: 'King suite',
};

// Manual changes PATCH /api/rooms/{number} accepts. Occupied is entered and left only by check-in and check-out.
const HOUSEKEEPING = {
  dirty: [
    { to: 'clean', label: 'Mark clean', hint: 'Ready for the next guest' },
    { to: 'out_of_order', label: 'Take out of order', hint: 'Close for maintenance' },
  ],
  clean: [{ to: 'out_of_order', label: 'Take out of order', hint: 'Close for maintenance' }],
  out_of_order: [{ to: 'dirty', label: 'Return to service', hint: 'Comes back as dirty for inspection' }],
  occupied: [],
};

export const RULE_TITLE = {
  R1: 'Invalid reservation',
  R2: 'Room already booked',
  R3: 'Outside the check-in window',
  R4: 'Party does not match the booking',
  R5: 'Room is not ready',
  R6: 'Not allowed in this status',
  R7: 'Decided by the night audit',
  ROOM_STATUS: 'Status change not allowed',
  VALIDATION: 'Request not accepted',
  NOT_FOUND: 'Not found',
  UNAVAILABLE: 'Service unavailable',
  BAD_RESPONSE: 'Unexpected response',
};

export function roomTypeLabel(type) {
  return ROOM_TYPE_LABEL[type] ?? String(type).replaceAll('_', ' ');
}

export function housekeepingActions(status) {
  return HOUSEKEEPING[status] ?? [];
}

/** "Sleeps 3" or "Sleeps 5, up to 3 adults" */
export function capacityLabel(room) {
  return room.max_adults < room.max_occupancy
    ? `Sleeps ${room.max_occupancy}, up to ${room.max_adults} adults`
    : `Sleeps ${room.max_occupancy}`;
}

/** Garden rooms (G01...) form their own building; main building rooms are grouped by the hundreds digit. */
export function roomGroup(number) {
  if (/^G/i.test(number)) return { key: 'garden', label: 'Garden', order: 0 };
  const floor = Math.floor(Number(number) / 100);
  if (Number.isInteger(floor) && floor > 0) {
    return { key: `floor-${floor}`, label: `Floor ${floor}`, order: floor };
  }
  return { key: 'other', label: 'Other', order: 99 };
}

export function compareRooms(a, b) {
  const byGroup = roomGroup(a.number).order - roomGroup(b.number).order;
  return byGroup || a.number.localeCompare(b.number, 'en', { numeric: true });
}
