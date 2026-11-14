import { $, h } from '../lib/dom.js';

const KBD_IDLE = '/';
const KBD_FOCUSED = 'esc';

export function createSearch({ suggestions, onChange, onSubmit, onArrowDown }) {
  const root = $('.search');
  const field = $('.search-field', root);
  const input = $('#catalog-search');
  const clear = $('[data-search-clear]', root);
  const kbd = $('[data-search-kbd]', root);

  function sync() {
    const filled = input.value.length > 0;

    root.classList.toggle('has-query', filled);
    clear.hidden = !filled;
    kbd.hidden = filled;
  }

  function set(value) {
    input.value = value;
    sync();
    onChange(value);
  }

  input.addEventListener('input', () => {
    sync();
    onChange(input.value);
  });
  input.addEventListener('focus', () => (kbd.textContent = KBD_FOCUSED));
  input.addEventListener('blur', () => (kbd.textContent = KBD_IDLE));
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      if (input.value) set('');
      else input.blur();
    } else if (event.key === 'Enter') {
      onSubmit();
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      onArrowDown();
    }
  });

  clear.addEventListener('click', () => {
    set('');
    input.focus();
  });
  field.addEventListener('pointerdown', (event) => {
    if (event.target === input || event.target.closest('button')) return;

    event.preventDefault();
    input.focus();
  });

  const chips = suggestions.map((text) =>
    h('button', {
      type: 'button',
      text,
      onclick: () => {
        set(text);
        onSubmit();
      },
    }),
  );
  $('[data-suggestions]', root).append(...chips);

  return {
    set,
    get value() {
      return input.value;
    },
    show(value) {
      input.value = value;
      sync();
    },
    focus() {
      const { top, bottom } = field.getBoundingClientRect();

      input.focus({ preventScroll: true });
      input.select();
      if (top < 0 || bottom > innerHeight) field.scrollIntoView({ block: 'center' });
    },
    setPlaceholder(text) {
      input.placeholder = text;
    },
  };
}
