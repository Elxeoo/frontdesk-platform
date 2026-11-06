// Confirmation dialog for check-out and cancel: runs the action on confirm and keeps API errors (R6 ...) inside the dialog.

import { byId, setText, slots } from '../dom.js';
import { clearFormError, openDialog, runLocked, setupDialog, showFormError } from './dialog.js';

const dialog = byId('confirm-dialog');
const form = byId('confirm-form');
const parts = slots(dialog);
const keepButton = dialog.querySelector('[data-close]');

let pending = null; // { run, busyLabel, resolve, inFlight }

/** Resolves one request's promise; it never touches a newer request. */
function settle(request, result) {
  if (pending === request) pending = null;
  request.resolve(result);
}

async function submit(event) {
  event.preventDefault();
  const request = pending;
  if (!request || request.inFlight) return;

  request.inFlight = true;
  const outcome = await runLocked(dialog, parts.submit, request.busyLabel, request.run);
  request.inFlight = false;

  if (outcome.ok) {
    settle(request, outcome.value);
    if (outcome.current) dialog.close();
  } else if (outcome.current) {
    showFormError(parts.error, outcome.error);
  } else {
    settle(request, undefined);
  }
}

export function initConfirm() {
  setupDialog(dialog);
  form.addEventListener('submit', submit);
  // Backing out settles with undefined; a request still in flight settles itself when it finishes.
  dialog.addEventListener('close', () => {
    if (pending && !pending.inFlight) settle(pending, undefined);
  });
}

/**
 * Asks for confirmation, then runs `run` while the dialog shows progress.
 * Resolves with run's result, or undefined when the operator backs out.
 */
export function confirmAndRun({ title, body, confirmLabel, busyLabel, danger = false, run }) {
  if (pending && !pending.inFlight) settle(pending, undefined);
  return new Promise((resolve) => {
    pending = { run, busyLabel, resolve, inFlight: false };
    setText(byId('confirm-title'), title);
    setText(byId('confirm-body'), body);
    setText(parts.submit, confirmLabel);
    parts.submit.classList.toggle('btn-danger', danger);
    parts.submit.classList.toggle('btn-primary', !danger);
    clearFormError(parts.error);
    // Destructive actions start on the safe choice.
    openDialog(dialog, danger ? keepButton : parts.submit);
  });
}
