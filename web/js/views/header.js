// Top bar: business date, hotel clock and the four KPIs (arrivals, departures, in-house, occupancy).

import { byId, setAttr, setText } from '../dom.js';
import { formatClock, formatLongDate, formatPercent, hotelToday, plural } from '../format.js';
import { occupancy } from '../state.js';

const dateEl = byId('business-date');
const clockEl = byId('hotel-clock');

const kpi = {
  arrivals: byId('kpi-arrivals'),
  arrivalsSub: byId('kpi-arrivals-sub'),
  departures: byId('kpi-departures'),
  departuresSub: byId('kpi-departures-sub'),
  inHouse: byId('kpi-inhouse'),
  inHouseSub: byId('kpi-inhouse-sub'),
  occupancy: byId('kpi-occupancy'),
  occupancySub: byId('kpi-occupancy-sub'),
};

function setSub(node, text, tone) {
  setText(node, text);
  setAttr(node, 'data-tone', tone ?? null);
}

function renderClock() {
  const today = hotelToday();
  setText(dateEl, formatLongDate(today));
  setAttr(dateEl, 'datetime', today);
  setText(clockEl, formatClock(new Date()));
}

export function initHeader() {
  renderClock();
  setInterval(renderClock, 15_000);
}

export function renderHeader(state) {
  const late = state.arrivals.filter((item) => item.late_arrival).length;
  setText(kpi.arrivals, state.arrivals.length);
  setSub(kpi.arrivalsSub, late ? `${late} late` : 'none late', late ? 'warn' : null);

  const overdue = state.departures.filter((item) => item.departure_date < state.today).length;
  setText(kpi.departures, state.departures.length);
  setSub(kpi.departuresSub, overdue ? `${overdue} overdue` : 'none overdue', overdue ? 'danger' : null);

  const guests = state.inHouse.reduce((sum, item) => sum + item.adults + (item.children ?? 0), 0);
  setText(kpi.inHouse, state.inHouse.length);
  setSub(kpi.inHouseSub, plural(guests, 'guest'));

  const { occupied, sellable, ratio } = occupancy();
  setText(kpi.occupancy, formatPercent(ratio));
  setSub(kpi.occupancySub, `${occupied} of ${sellable} rooms`);
}
