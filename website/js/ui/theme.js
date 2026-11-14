import { $ } from '../lib/dom.js';

// the inline script in index.html reads the same key before the first paint
const STORAGE_KEY = 'theme';
const LABELS = { light: 'Switch to dark theme', dark: 'Switch to light theme' };

function stored() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function initTheme() {
  const root = document.documentElement;
  const button = $('[data-theme-toggle]');
  const meta = $('meta[name="theme-color"]');
  const system = matchMedia('(prefers-color-scheme: dark)');

  function apply(theme) {
    root.dataset.theme = theme;
    button.setAttribute('aria-label', LABELS[theme]);
    meta.content = getComputedStyle(root).getPropertyValue('--theme-color').trim();
  }

  function toggle() {
    const theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {}

    if (document.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      document.startViewTransition(() => apply(theme));
    } else {
      apply(theme);
    }
  }

  button.addEventListener('click', toggle);
  system.addEventListener('change', (event) => {
    if (!stored()) apply(event.matches ? 'dark' : 'light');
  });
  apply(root.dataset.theme);

  return { toggle };
}
