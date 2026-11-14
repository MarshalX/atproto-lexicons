import { $ } from './dom.js';

const timers = new WeakMap();

function textOf(button) {
  if (button.dataset.copy) return button.dataset.copy;

  const source = document.getElementById(button.dataset.copyFrom);
  return source.dataset.source ?? source.textContent;
}

export function bindCopyButtons({ copiedMs }) {
  const announcer = $('[data-announcer]');

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-copy], [data-copy-from]');
    if (!button) return;

    try {
      await navigator.clipboard.writeText(textOf(button));
    } catch {
      return;
    }

    button.classList.add('is-copied');
    announcer.textContent = 'Copied to the clipboard';

    clearTimeout(timers.get(button));
    timers.set(
      button,
      setTimeout(() => {
        button.classList.remove('is-copied');
        announcer.textContent = '';
      }, copiedMs),
    );
  });
}
