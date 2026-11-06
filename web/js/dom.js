// Small DOM helpers: element creation, template cloning, icons and change-aware updates. API data only ever goes in via textContent.

const SVG_NS = 'http://www.w3.org/2000/svg';

export function byId(id) {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing element #${id}`);
  return node;
}

/** Creates an element; `props` may hold className, text, attrs, dataset and hidden. */
export function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  if (props.className) node.className = props.className;
  if (props.text !== undefined) node.textContent = props.text;
  if (props.hidden) node.hidden = true;
  for (const [name, value] of Object.entries(props.attrs ?? {})) node.setAttribute(name, value);
  Object.assign(node.dataset, props.dataset ?? {});
  node.append(...children);
  return node;
}

/** An inline icon that references a symbol of the sprite in index.html. */
export function icon(name, className = 'icon') {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', className);
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS(SVG_NS, 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);
  return svg;
}

/** A small tinted square with the status glyph, used in the legend and menus. */
export function statusSwatch(status) {
  return el('span', { className: 'swatch', dataset: { status } }, [icon(status)]);
}

/** Room number in a status-tinted chip; the status is also spelled out for screen readers. */
export function roomChip(number, status, statusLabel) {
  const chip = el('span', { className: 'room-chip tabular' }, [el('span', { text: number })]);
  if (status) {
    chip.dataset.status = status;
    chip.prepend(icon(status));
    chip.append(el('span', { className: 'visually-hidden', text: `, ${statusLabel}` }));
  }
  return chip;
}

/** Clones the first element of a <template>. */
export function fromTemplate(id) {
  return byId(id).content.firstElementChild.cloneNode(true);
}

/** Collects every [data-slot] descendant into an object keyed by slot name. */
export function slots(root) {
  const found = {};
  for (const node of root.querySelectorAll('[data-slot]')) found[node.dataset.slot] = node;
  return found;
}

/** Writes text only when it changed, so refreshes do not disturb selection or screen readers. */
export function setText(node, text) {
  const value = String(text ?? '');
  if (node.textContent !== value) node.textContent = value;
}

export function setAttr(node, name, value) {
  if (value === null || value === undefined || value === false) {
    node.removeAttribute(name);
  } else if (node.getAttribute(name) !== String(value)) {
    node.setAttribute(name, value);
  }
}

/** Restarts a one-shot CSS animation class. */
export function replayClass(node, className) {
  node.classList.remove(className);
  void node.offsetWidth;
  node.classList.add(className);
  node.addEventListener('animationend', () => node.classList.remove(className), { once: true });
}

/** Puts `children` into `parent` in the given order, moving only the nodes that are out of place. */
export function placeInOrder(parent, children) {
  const wanted = new Set(children);
  for (const child of [...parent.children]) {
    if (!wanted.has(child)) child.remove();
  }
  children.forEach((child, index) => {
    const current = parent.children[index];
    if (current !== child) parent.insertBefore(child, current ?? null);
  });
}
