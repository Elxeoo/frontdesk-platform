// Formatting of dates, times, counts and party sizes; "today" is always the hotel's date in Europe/Istanbul.

const HOTEL_TIME_ZONE = 'Europe/Istanbul';

const DAY_MS = 86_400_000;

const hotelDateParts = new Intl.DateTimeFormat('en-GB', {
  timeZone: HOTEL_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

const hotelClock = new Intl.DateTimeFormat('en-GB', {
  timeZone: HOTEL_TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
});

const hotelClockSeconds = new Intl.DateTimeFormat('en-GB', {
  timeZone: HOTEL_TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
});

// Calendar dates (YYYY-MM-DD) have no time of day, so they are formatted in UTC to never shift by a day.
const shortDate = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short' });
const longDate = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'UTC',
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
});

function toUtc(isoDate) {
  const [year, month, day] = isoDate.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

/** Today's date at the hotel as YYYY-MM-DD. */
export function hotelToday(now = new Date()) {
  const parts = Object.fromEntries(hotelDateParts.formatToParts(now).map((p) => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function addDays(isoDate, days) {
  const date = toUtc(isoDate);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function daysBetween(fromIso, toIso) {
  return Math.round((toUtc(toIso) - toUtc(fromIso)) / DAY_MS);
}

/** "6 Nov" */
export function formatShortDate(isoDate) {
  return shortDate.format(toUtc(isoDate));
}

/** "Fri, 6 Nov 2026" */
export function formatLongDate(isoDate) {
  return longDate.format(toUtc(isoDate));
}

/** "6 Nov → 9 Nov" */
export function formatStay(arrival, departure) {
  return `${formatShortDate(arrival)} → ${formatShortDate(departure)}`;
}

export function formatClock(date, withSeconds = false) {
  return (withSeconds ? hotelClockSeconds : hotelClock).format(date);
}

export function plural(count, one, many = `${one}s`) {
  return `${count} ${count === 1 ? one : many}`;
}

/** "2 adults, 1 child" */
export function formatParty(adults, children = 0) {
  const parts = [plural(adults, 'adult')];
  if (children > 0) parts.push(plural(children, 'child', 'children'));
  return parts.join(', ');
}

export function formatPercent(ratio) {
  return `${Math.round(ratio * 100)}%`;
}

/** "just now", "12 s ago", "3 min ago" */
export function formatAgo(milliseconds) {
  const seconds = Math.max(0, Math.round(milliseconds / 1000));
  if (seconds < 3) return 'just now';
  if (seconds < 60) return `${seconds} s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  return `${Math.round(minutes / 60)} h ago`;
}
