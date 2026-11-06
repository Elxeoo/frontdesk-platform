// Shared behaviour of the native <dialog> forms: close buttons, focus return, the inline error box with the rule code, and a lock that keeps a dialog open while its request is in flight.

import { ApiError } from '../api.js';
import { byId, slots } from '../dom.js';
import { RULE_TITLE } from '../domain.js';
import { showErrorToast } from '../views/toasts.js';

const busy = new WeakSet(); // dialogs with a request in flight
const sessions = new WeakMap(); // dialog -> number of times it was opened

export function setupDialog(dialog) {
  dialog.addEventListener('click', (event) => {
    if (event.target.closest('[data-close]') && !busy.has(dialog)) dialog.close();
  });
  dialog.addEventListener('cancel', (event) => {
    if (busy.has(dialog)) event.preventDefault();
  });
}

/** Opens a dialog modally and returns focus to the element that opened it (or the main region if that is gone). */
export function openDialog(dialog, focusTarget) {
  const opener = document.activeElement;
  sessions.set(dialog, (sessions.get(dialog) ?? 0) + 1);
  dialog.showModal();
  focusTarget?.focus();
  dialog.addEventListener(
    'close',
    () => {
      const target = opener instanceof HTMLElement && opener.isConnected && opener !== document.body ? opener : byId('main');
      target.focus({ preventScroll: target.id === 'main' });
    },
    { once: true },
  );
}

/**
 * Runs `task` with the dialog locked: the submit button shows progress, and Close buttons and Escape do nothing until
 * it settles. Browsers may still force a modal dialog shut (Escape pressed twice without user activation), so the
 * outcome says whether the dialog is still the one that sent the request.
 *
 * Resolves to `{ ok, value, error, current }`. An API error for a dialog that is no longer current becomes a toast.
 */
export async function runLocked(dialog, button, busyLabel, task) {
  const session = sessions.get(dialog);
  const closers = [...dialog.querySelectorAll('[data-close]')];
  const label = button.textContent;
  const focused = document.activeElement;

  busy.add(dialog);
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  button.textContent = busyLabel;
  for (const closer of closers) closer.disabled = true;

  const isCurrent = () => sessions.get(dialog) === session && dialog.open;
  try {
    const value = await task();
    return { ok: true, value, current: isCurrent() };
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    const current = isCurrent();
    if (!current) showErrorToast(error);
    return { ok: false, error, current };
  } finally {
    busy.delete(dialog);
    button.disabled = false;
    button.removeAttribute('aria-busy');
    // Keep a label that a reopened dialog has set meanwhile (the confirm dialog relabels its button).
    if (button.textContent === busyLabel) button.textContent = label;
    for (const closer of closers) closer.disabled = false;
    // Disabling the focused button dropped focus; give it back while the dialog stays open.
    if (isCurrent() && !dialog.contains(document.activeElement) && dialog.contains(focused)) focused.focus();
  }
}

/** Shows an API error inside a dialog: the code chip (R1-R6 ...), a short title and the API's message. */
export function showFormError(box, error) {
  const content = byId('tpl-form-error').content.cloneNode(true);
  const parts = slots(content);
  const hasCode = error.code && !error.code.startsWith('HTTP_') && error.code !== 'NETWORK';
  parts.code.textContent = hasCode ? error.code : '!';
  parts.title.textContent = RULE_TITLE[error.code] ?? '';
  parts.message.textContent = error.message;
  box.replaceChildren(content);
  box.hidden = false;
}

export function clearFormError(box) {
  box.hidden = true;
  box.replaceChildren();
}
