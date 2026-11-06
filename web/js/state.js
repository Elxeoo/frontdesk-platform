// The latest successful snapshot of API data, plus the lookups by room number that several views share.

export const state = {
  today: '',
  rooms: [],
  arrivals: [],
  departures: [],
  inHouse: [],
  audit: null,
};

const roomsByNumber = new Map();
const occupantsByRoom = new Map();
const arrivalsByRoom = new Map();

export function applySnapshot(snapshot) {
  Object.assign(state, snapshot);

  roomsByNumber.clear();
  occupantsByRoom.clear();
  arrivalsByRoom.clear();
  for (const room of state.rooms) roomsByNumber.set(room.number, room);
  for (const stay of state.inHouse) occupantsByRoom.set(stay.room_number, stay);
  for (const booking of state.arrivals) {
    if (!arrivalsByRoom.has(booking.room_number)) arrivalsByRoom.set(booking.room_number, booking);
  }
}

export function roomByNumber(number) {
  return roomsByNumber.get(number);
}

/** The checked-in reservation in a room, if any. */
export function occupantOf(number) {
  return occupantsByRoom.get(number);
}

/** The expected (booked) arrival for a room, if any. */
export function arrivalFor(number) {
  return arrivalsByRoom.get(number);
}

/** Occupied rooms divided by rooms that are not out of order, as in the night audit. */
export function occupancy() {
  const sellable = state.rooms.filter((room) => room.status !== 'out_of_order').length;
  const occupied = state.rooms.filter((room) => room.status === 'occupied').length;
  return { occupied, sellable, ratio: sellable ? occupied / sellable : 0 };
}
