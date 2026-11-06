// Refresh loop: runs a task every few seconds while the tab is visible, pauses when hidden, never runs two at once, and lets the task ask for a longer wait.

/**
 * @param {() => Promise<number|void>} task  Resolves to the delay in ms it wants before the next run (e.g. Retry-After).
 * @param {number} intervalMs                 Normal delay, and the minimum.
 */
export function createPoller(task, intervalMs) {
  let timer = 0;
  let running = null;
  let rerun = false;
  let nextDelay = intervalMs;

  function schedule() {
    clearTimeout(timer);
    if (document.visibilityState === 'visible') timer = setTimeout(run, nextDelay);
  }

  /** Runs the task now. A call during a run queues exactly one more run; the returned promise settles after it. */
  async function run() {
    clearTimeout(timer);
    if (running) {
      rerun = true;
      return running;
    }
    running = (async () => {
      do {
        rerun = false;
        nextDelay = Math.max(intervalMs, (await task()) ?? 0);
      } while (rerun);
    })();
    try {
      await running;
    } finally {
      running = null;
      schedule();
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') run();
    else clearTimeout(timer);
  });

  return { run };
}
