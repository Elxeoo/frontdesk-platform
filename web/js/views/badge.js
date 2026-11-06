// Version and pod badge: who served the latest API response, and how the last 20 responses split across versions, so a canary is visible on screen.

import { byId, el, placeInOrder, replayClass, setAttr, setText } from '../dom.js';

const WINDOW = 20;
const NO_VERSION = 'no version';

const summary = byId('vbadge').querySelector('summary');
const dot = byId('vb-dot');
const versionEl = byId('vb-version');
const podEl = byId('vb-pod');
const bar = byId('vb-bar');
const labels = byId('vb-labels');
const ticks = byId('vb-ticks');
const pods = byId('vb-pods');

const samples = []; // oldest first: { version, pod, failed }
const segments = new Map(); // version -> bar segment
const shareLabels = new Map(); // version -> { node, share }
let shownVersion = null;
let frame = 0;

/**
 * Stable hue for a version string: FNV-1a hash, spread with the golden ratio so that
 * neighbouring versions such as 1.4.0 and 1.5.0 land far apart on the colour wheel.
 */
function versionHue(version) {
  let hash = 0x811c9dc5;
  for (const char of version) {
    hash ^= char.codePointAt(0);
    hash = Math.imul(hash, 0x01000193);
  }
  return Math.round((((hash >>> 0) * 0.6180339887) % 1) * 360);
}

function paint(node, version) {
  const known = version !== NO_VERSION;
  node.classList.toggle('is-unknown', !known);
  if (known) node.style.setProperty('--hue', String(versionHue(version)));
}

function versionDot(version) {
  const node = el('span', { className: 'ver-dot', attrs: { 'aria-hidden': 'true' } });
  paint(node, version);
  return node;
}

function compareVersions(a, b) {
  return a.localeCompare(b, 'en', { numeric: true });
}

function renderSplit(counts) {
  const versions = [...counts.keys()].sort(compareVersions);
  const total = samples.length;

  const segmentNodes = versions.map((version) => {
    let segment = segments.get(version);
    if (!segment) {
      segment = el('span', { className: 'split-seg' });
      paint(segment, version);
      segments.set(version, segment);
    }
    segment.style.setProperty('--share', String(counts.get(version)));
    return segment;
  });
  placeInOrder(bar, segmentNodes);

  const labelNodes = versions.map((version) => {
    let label = shareLabels.get(version);
    if (!label) {
      const share = el('span', { className: 'split-share' });
      label = { node: el('span', { className: 'split-label' }, [versionDot(version), el('span', { text: version }), share]), share };
      shareLabels.set(version, label);
    }
    setText(label.share, `${Math.round((counts.get(version) / total) * 100)}%`);
    return label.node;
  });
  placeInOrder(labels, labelNodes);

  for (const version of [...segments.keys()]) {
    if (!counts.has(version)) {
      segments.delete(version);
      shareLabels.delete(version);
    }
  }
}

function renderTicks() {
  while (ticks.children.length < WINDOW) ticks.append(el('li', { className: 'tick' }));
  [...ticks.children].forEach((tick, index) => {
    const sample = samples[index];
    tick.classList.toggle('is-empty', !sample);
    tick.classList.toggle('is-error', Boolean(sample?.failed));
    if (sample) paint(tick, sample.version);
    setAttr(tick, 'title', sample ? `${sample.version} · ${sample.pod}${sample.failed ? ' · server error' : ''}` : null);
  });
}

function renderPods() {
  const byPod = new Map();
  for (const sample of samples) {
    const entry = byPod.get(sample.pod) ?? { version: sample.version, count: 0 };
    entry.count += 1;
    byPod.set(sample.pod, entry);
  }
  const rows = [...byPod]
    .sort((a, b) => compareVersions(a[1].version, b[1].version) || a[0].localeCompare(b[0]))
    .map(([pod, { version, count }]) =>
      el('tr', {}, [
        el('td', { text: pod, attrs: { title: pod } }),
        el('td', {}, [el('span', { className: 'pod-version' }, [versionDot(version), el('span', { text: version })])]),
        el('td', { className: 'num tabular', text: String(count) }),
      ]),
    );
  pods.replaceChildren(...rows);
}

function render() {
  frame = 0;
  const latest = samples.at(-1);
  setText(versionEl, latest.version);
  setText(podEl, latest.pod);
  paint(dot, latest.version);
  if (shownVersion !== null && latest.version !== shownVersion) replayClass(dot, 'is-new');
  shownVersion = latest.version;

  const counts = new Map();
  for (const sample of samples) counts.set(sample.version, (counts.get(sample.version) ?? 0) + 1);
  renderSplit(counts);
  renderTicks();
  renderPods();

  const split = [...counts.keys()]
    .sort(compareVersions)
    .map((version) => `${version} ${Math.round((counts.get(version) / samples.length) * 100)}%`)
    .join(', ');
  setAttr(
    summary,
    'aria-label',
    `Latest API response from version ${latest.version}, pod ${latest.pod}. Last ${samples.length} responses: ${split}. Show details.`,
  );
}

/** Records one API response; rendering is batched to one update per animation frame. */
export function recordResponse({ version, pod, status }) {
  samples.push({ version: version || NO_VERSION, pod: pod || 'unknown pod', failed: status >= 500 });
  if (samples.length > WINDOW) samples.shift();
  if (!frame) frame = requestAnimationFrame(render);
}
