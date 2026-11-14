import config from '../config.js';
import { initCatalog } from './catalog/index.js';
import { bindCopyButtons } from './lib/clipboard.js';
import { $ } from './lib/dom.js';
import { formatNumber } from './lib/format.js';
import { bindHotkeys } from './lib/hotkeys.js';
import { renderBackdrop } from './ui/backdrop.js';
import { highlightCode } from './ui/code.js';
import { initNav } from './ui/nav.js';
import { initTheme } from './ui/theme.js';

function showStars(stars) {
  if (!Number.isInteger(stars)) return;

  const count = formatNumber(stars);
  $('[data-stars-count]').textContent = count;
  $('[data-stars]').hidden = false;
  $('[data-stars-link]').setAttribute('aria-label', `Star the atproto SDK on GitHub, ${count} stars`);
}

const theme = initTheme();
initNav();
renderBackdrop(config.backdrop);
highlightCode();
bindCopyButtons(config);

const catalog = initCatalog(config);
catalog.loaded.then((data) => data && showStars(data.sdkStars));

bindHotkeys([
  [config.hotkeys.focusSearch, catalog.focusSearch],
  [config.hotkeys.toggleTheme, theme.toggle],
]);
