// Toast notifications in an aria-live region: neutral for results, red with the rule code for errors; they wait while hovered or focused.

import { byId, fromTemplate, slots } from '../dom.js';

const region = byId('toasts');
const MAX_VISIBLE = 4;
const RESUME_MS = 2500;

/** Removes a toast; if it held keyboard focus, focus moves to the next toast or to the main region. */
function dismiss(toastEl) {
  if (toastEl.classList.contains('is-leaving')) return;
  if (toastEl.contains(document.activeElement)) {
    const next = [...region.querySelectorAll('.toast:not(.is-leaving) .toast-close')].find((button) => !toastEl.contains(button));
    if (next) next.focus();
    else byId('main').focus({ preventScroll: true });
  }
  toastEl.classList.add('is-leaving');
  const remove = () => toastEl.remove();
  toastEl.addEventListener('animationend', remove, { once: true });
  // Fallback for reduced motion or an interrupted animation.
  setTimeout(remove, 400);
}

function addToast({ message, code, tone, timeout }) {
  const toastEl = fromTemplate('tpl-toast');
  const parts = slots(toastEl);
  toastEl.dataset.tone = tone;
  parts.message.textContent = message;
  if (code && !code.startsWith('HTTP_') && code !== 'NETWORK') {
    parts.code.textContent = code;
    parts.code.hidden = false;
  }
  toastEl.querySelector('.toast-close').addEventListener('click', () => dismiss(toastEl));

  // One "held" state: the timer runs only while neither the pointer nor keyboard focus is on the toast.
  let hovered = false;
  let focused = false;
  let timer = setTimeout(() => dismiss(toastEl), timeout);
  const update = () => {
    clearTimeout(timer);
    if (!hovered && !focused) timer = setTimeout(() => dismiss(toastEl), RESUME_MS);
  };
  toastEl.addEventListener('pointerenter', () => {
    hovered = true;
    update();
  });
  toastEl.addEventListener('pointerleave', () => {
    hovered = false;
    update();
  });
  toastEl.addEventListener('focusin', () => {
    focused = true;
    update();
  });
  toastEl.addEventListener('focusout', (event) => {
    if (toastEl.contains(event.relatedTarget)) return;
    focused = false;
    update();
  });

  region.append(toastEl);
  const visible = [...region.children].filter((child) => !child.classList.contains('is-leaving'));
  if (visible.length > MAX_VISIBLE) dismiss(visible[0]);
}

export function showToast(message) {
  addToast({ message, tone: 'neutral', timeout: 4000 });
}

/** Shows an ApiError with its code (R1-R7, ROOM_STATUS, UNAVAILABLE ...) when it has one. */
export function showErrorToast(error) {
  addToast({ message: error.message, code: error.code, tone: 'error', timeout: 9000 });
}
