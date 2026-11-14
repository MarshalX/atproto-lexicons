import { h } from '../lib/dom.js';

const TOKENS = [
  ['comment', /#.*/],
  ['string', /'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"/],
  ['keyword', /\b(?:from|import|as|def|class|return|async|await|with|for|in|if|else|None|True|False)\b/],
  ['class', /\b[A-Z][A-Za-z0-9]*\b/],
  ['function', /\b[a-z_][a-z0-9_]*(?=\()/],
];
const PATTERN = new RegExp(TOKENS.map(([, pattern]) => `(${pattern.source})`).join('|'), 'g');

function tokenize(line) {
  const nodes = [];
  let from = 0;

  for (const match of line.matchAll(PATTERN)) {
    if (match.index > from) nodes.push(line.slice(from, match.index));

    const [name] = TOKENS[match.slice(1).findIndex((group) => group !== undefined)];
    nodes.push(h('span', { class: `tok-${name}`, text: match[0] }));
    from = match.index + match[0].length;
  }
  if (from < line.length) nodes.push(line.slice(from));

  return nodes;
}

function parseRange(value) {
  if (!value) return () => false;

  const [first, last = first] = value.split('-').map(Number);
  return (line) => line >= first && line <= last;
}

export function highlightCode() {
  for (const block of document.querySelectorAll('[data-code]')) {
    const source = block.textContent;
    const isHot = parseRange(block.dataset.highlight);

    const lines = source.split('\n').map((line, index) => {
      return h('span', { class: isHot(index + 1) ? 'code-line is-hot' : 'code-line' }, h('span', {}, tokenize(line)));
    });

    block.dataset.source = source;
    block.firstElementChild.replaceChildren(...lines);
    block.classList.add('is-ready');
  }
}
