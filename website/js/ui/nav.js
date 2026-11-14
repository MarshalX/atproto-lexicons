import { $ } from '../lib/dom.js';

const LABELS = { true: 'Close menu', false: 'Open menu' };

export function initNav() {
  const toggle = $('[data-nav-toggle]');
  const nav = $('#site-nav');

  function set(open) {
    nav.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', LABELS[open]);
  }

  const isOpen = () => nav.classList.contains('is-open');

  toggle.addEventListener('click', () => set(!isOpen()));
  nav.addEventListener('click', (event) => {
    if (event.target.closest('a')) set(false);
  });
  document.addEventListener('pointerdown', (event) => {
    if (isOpen() && !nav.contains(event.target) && !toggle.contains(event.target)) set(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !isOpen()) return;

    set(false);
    toggle.focus();
  });
}
