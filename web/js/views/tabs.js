// Accessible tabs (WAI-ARIA tabs pattern) with arrow-key navigation; the chosen tab is remembered in this browser.

const STORAGE_KEY = 'frontdesk.desk-tab';

export function initTabs(tablist) {
  const tabs = [...tablist.querySelectorAll('[role="tab"]')];

  function select(tab, { focus = false } = {}) {
    for (const candidate of tabs) {
      const selected = candidate === tab;
      candidate.setAttribute('aria-selected', String(selected));
      candidate.tabIndex = selected ? 0 : -1;
      document.getElementById(candidate.getAttribute('aria-controls')).hidden = !selected;
    }
    if (focus) tab.focus();
    try {
      localStorage.setItem(STORAGE_KEY, tab.id);
    } catch {
      // Storage can be unavailable (private mode, blocked site data); the tab simply is not remembered.
    }
  }

  tablist.addEventListener('click', (event) => {
    const tab = event.target.closest('[role="tab"]');
    if (tab) select(tab);
  });

  tablist.addEventListener('keydown', (event) => {
    const index = tabs.indexOf(document.activeElement);
    const moves = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: tabs.length - 1 };
    if (index < 0 || !(event.key in moves)) return;
    event.preventDefault();
    select(tabs[(moves[event.key] + tabs.length) % tabs.length], { focus: true });
  });

  let saved = null;
  try {
    saved = localStorage.getItem(STORAGE_KEY);
  } catch {
    saved = null;
  }
  const restored = tabs.find((tab) => tab.id === saved);
  if (restored) select(restored);
}
