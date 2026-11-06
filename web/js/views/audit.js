// Night audit card: the latest report from the API, or an empty state before the first audit has run.

import { byId, el, icon, setText } from '../dom.js';
import { formatLongDate, formatPercent } from '../format.js';

const body = byId('audit-body');
const dateEl = byId('audit-date');
let lastSignature;

function metric(label, value, note) {
  return el('div', { className: 'audit-metric' }, [
    el('span', { className: 'eyebrow', text: label }),
    el('span', { className: 'audit-value tabular', text: String(value) }),
    el('span', { className: 'audit-note tabular', text: note ?? '' }),
  ]);
}

function emptyState() {
  return el('div', { className: 'audit-empty' }, [
    icon('moon'),
    el('p', { className: 'audit-empty-title', text: 'No night audit has run yet' }),
    el('p', {
      className: 'audit-empty-text',
      text: 'The first report appears here after the night audit job closes a business day.',
    }),
  ]);
}

function reportView(report) {
  const noShows = report.no_shows ?? [];
  const fill = el('div', { className: 'bar-fill' });
  fill.style.setProperty('--value', String(Math.min(1, Math.max(0, report.occupancy_rate))));

  return [
    el('div', { className: 'audit-metrics' }, [
      metric('Checked in', report.checked_in),
      metric('Checked out', report.checked_out),
      metric('No-shows', noShows.length, noShows.length ? noShows.map((id) => `#${id}`).join(', ') : 'none'),
      metric('In-house', report.in_house),
    ]),
    el('div', { className: 'audit-occupancy' }, [
      el('div', { className: 'audit-occupancy-head' }, [
        el('span', { className: 'eyebrow', text: 'Occupancy' }),
        el('span', { className: 'audit-occupancy-value tabular', text: formatPercent(report.occupancy_rate) }),
      ]),
      el('div', { className: 'bar', attrs: { role: 'presentation' } }, [fill]),
    ]),
  ];
}

export function renderAudit(report) {
  const signature = JSON.stringify(report);
  if (signature === lastSignature) return;
  lastSignature = signature;

  if (!report) {
    setText(dateEl, '');
    body.replaceChildren(emptyState());
    return;
  }
  setText(dateEl, `Closed ${formatLongDate(report.business_date)}`);
  body.replaceChildren(...reportView(report));
}
