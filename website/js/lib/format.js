import { h } from './dom.js';

const numberFormat = new Intl.NumberFormat('en');
const dateFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });

export const formatNumber = (value) => numberFormat.format(value);

export function plural(count, one, many) {
  return `${formatNumber(count)} ${count === 1 ? one : many}`;
}

export function formatDate(value) {
  if (!value) return null;

  const parts = dateFormat.formatToParts(new Date(value));
  const part = (type) => parts.find((entry) => entry.type === type).value;

  return { day: `${part('day')} ${part('month')}`, year: part('year') };
}

export function highlight(text, query) {
  if (!query) return [text];

  const lower = text.toLowerCase();
  const nodes = [];
  let from = 0;

  for (let at = lower.indexOf(query); at >= 0; at = lower.indexOf(query, from)) {
    if (at > from) nodes.push(text.slice(from, at));
    nodes.push(h('mark', { text: text.slice(at, at + query.length) }));
    from = at + query.length;
  }
  if (from < text.length) nodes.push(text.slice(from));

  return nodes;
}
