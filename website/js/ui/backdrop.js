import { $, h } from '../lib/dom.js';

// spreads the items out deterministically, so the page looks the same on every load
const spread = (index, step, range) => ((index * step) % range) / range;

export function renderBackdrop({ items, drift }) {
  const nodes = items.map(({ text, x, y, small }, index) => {
    const dx = (spread(index, 37, 29) * 2 - 1) * drift;
    const dy = (spread(index, 53, 23) * 2 - 1) * drift;
    const style = [
      `--x: ${x}%`,
      `--y: ${y}px`,
      `--dx: ${dx.toFixed(1)}px`,
      `--dy: ${dy.toFixed(1)}px`,
      `--duration: ${(9 + spread(index, 7, 8) * 8).toFixed(1)}s`,
      `--delay: ${(-index * 1.3).toFixed(1)}s`,
      `--enter: ${(index * 0.08).toFixed(2)}s`,
    ].join('; ');

    return h('span', { class: small && 'is-small', style, text });
  });

  $('[data-backdrop]').replaceChildren(...nodes);
}
