import { h, icon } from '../lib/dom.js';

const OPEN_KEYS = new Set(['ArrowDown', 'ArrowUp', 'Enter', ' ']);

/**
 * A listbox behind a button, in place of a native <select>.
 * Options are { value, label, hint?, kind?, separated? }.
 */
export function createDropdown(host, { id, label, options, value, onChange }) {
  const dot = h('span', { class: 'dropdown-dot', 'aria-hidden': 'true' });
  const current = h('span', { class: 'dropdown-value' });
  const trigger = h(
    'button',
    { class: 'dropdown-trigger', type: 'button', 'aria-haspopup': 'listbox', 'aria-expanded': 'false', 'aria-controls': id },
    h('span', { class: 'dropdown-label', text: label }),
    dot,
    current,
    icon('chevron', 14),
  );

  const hasDots = options.some((option) => option.kind);
  const items = options.map((option) =>
    h(
      'button',
      { class: 'dropdown-option', type: 'button', role: 'option', tabindex: '-1', 'data-value': option.value },
      h('span', { class: 'dropdown-check' }, icon('check', 16)),
      hasDots && h('span', { class: 'dropdown-dot', 'data-kind': option.kind, 'aria-hidden': 'true' }),
      h('span', { class: 'dropdown-option-label', text: option.label }),
      option.hint && h('span', { class: 'dropdown-hint', text: option.hint }),
    ),
  );
  const menu = h(
    'div',
    { class: 'dropdown-menu', id, role: 'listbox', 'aria-label': label, hidden: true },
    items.flatMap((item, index) => [item, options[index].separated && h('div', { class: 'dropdown-separator' })]),
  );

  const isOpen = () => !menu.hidden;
  const selectedItem = () => items.find((item) => item.dataset.value === value);

  function select(next, notify = true) {
    value = next;
    const option = options.find((entry) => entry.value === value);

    current.textContent = option.label;
    dot.hidden = !option.kind;
    if (option.kind) dot.dataset.kind = option.kind;
    for (const item of items) item.setAttribute('aria-selected', String(item.dataset.value === value));

    if (notify) onChange(value);
  }

  function open() {
    menu.hidden = false;
    host.classList.add('is-open');
    trigger.setAttribute('aria-expanded', 'true');
    selectedItem().focus();
  }

  function close(refocus = false) {
    if (!isOpen()) return;

    menu.hidden = true;
    host.classList.remove('is-open');
    trigger.setAttribute('aria-expanded', 'false');
    if (refocus) trigger.focus();
  }

  function move(step) {
    const index = items.indexOf(document.activeElement);
    items[(index + step + items.length) % items.length].focus();
  }

  trigger.addEventListener('click', () => (isOpen() ? close() : open()));
  trigger.addEventListener('keydown', (event) => {
    if (isOpen() || !OPEN_KEYS.has(event.key)) return;

    event.preventDefault();
    open();
  });

  menu.addEventListener('click', (event) => {
    const item = event.target.closest('.dropdown-option');
    if (!item) return;

    select(item.dataset.value);
    close(true);
  });
  menu.addEventListener('keydown', (event) => {
    const actions = {
      ArrowDown: () => move(1),
      ArrowUp: () => move(-1),
      Home: () => items[0].focus(),
      End: () => items.at(-1).focus(),
      Escape: () => close(true),
    };

    if (actions[event.key]) {
      event.preventDefault();
      event.stopPropagation();
      actions[event.key]();
      return;
    }

    if (event.key.length !== 1 || event.metaKey || event.ctrlKey) return;

    const typed = event.key.toLowerCase();
    items[options.findIndex((option) => option.label.toLowerCase().startsWith(typed))]?.focus();
  });

  host.addEventListener('focusout', (event) => {
    if (!host.contains(event.relatedTarget)) close();
  });
  document.addEventListener('pointerdown', (event) => {
    if (!host.contains(event.target)) close();
  });

  host.append(trigger, menu);
  select(value, false);

  return { set: (next) => select(next, false) };
}
