// Connection health: the "updated Xs ago" indicator in the top bar and the red banner, with a retry countdown, while refreshes fail.

import { byId, setText } from '../dom.js';
import { formatAgo, formatClock } from '../format.js';

const indicator = byId('sync-state');
const indicatorText = byId('sync-text');
const banner = byId('connection-banner');
const bannerTitle = byId('banner-title');
const bannerDetail = byId('banner-detail');
// The visible countdown ticks every second, so it is hidden from screen readers; they get one static note per delay.
const countdown = byId('banner-countdown');
const retryNote = byId('banner-retry-note');

let lastSuccess = 0;
let failure = null;
let nextRetryAt = 0;

function describeFailure(error) {
  if (error.status === 0) return 'The FrontDesk API cannot be reached.';
  if (error.code === 'UNAVAILABLE') return `The FrontDesk API is temporarily unavailable (HTTP ${error.status}).`;
  if (error.code === 'BAD_RESPONSE') return 'The FrontDesk API sent a response this screen cannot read.';
  if (error.status >= 500) return `The FrontDesk API is failing (HTTP ${error.status}).`;
  return `The FrontDesk API answered HTTP ${error.status} (${error.code}).`;
}

function render() {
  if (failure) {
    indicator.dataset.state = 'offline';
    setText(indicatorText, lastSuccess ? `Offline · data from ${formatClock(new Date(lastSuccess))}` : 'Offline');
    const seconds = Math.ceil((nextRetryAt - Date.now()) / 1000);
    setText(countdown, seconds > 0 ? `Retrying in ${seconds} s.` : 'Retrying now.');
  } else if (lastSuccess) {
    indicator.dataset.state = 'live';
    setText(indicatorText, `Live · updated ${formatAgo(Date.now() - lastSuccess)}`);
  }
}

export function initConnection({ onRetry }) {
  byId('banner-retry').addEventListener('click', onRetry);
  setInterval(() => {
    if (document.visibilityState === 'visible') render();
  }, 1000);
}

export function reportSuccess() {
  lastSuccess = Date.now();
  failure = null;
  banner.hidden = true;
  render();
}

/** @param {number} retryInMs  When the next attempt is scheduled (Retry-After or backoff). */
export function reportFailure(error, retryInMs) {
  failure = error;
  nextRetryAt = Date.now() + retryInMs;
  setText(bannerTitle, describeFailure(error));
  setText(bannerDetail, lastSuccess ? `Showing data from ${formatClock(new Date(lastSuccess), true)}.` : '');
  setText(retryNote, `Next attempt in ${Math.round(retryInMs / 1000)} seconds.`);
  banner.hidden = false;
  render();
}
