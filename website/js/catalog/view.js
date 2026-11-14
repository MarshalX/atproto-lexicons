import { h, icon } from '../lib/dom.js';
import { formatDate, highlight, plural } from '../lib/format.js';
import { GROUPS, KIND_LABELS, NOTES, OTHER, STATUS_LABELS, USAGE } from './constants.js';
import { filterLexicons } from './store.js';

export const panelId = (domain) => `panel-${domain}`;
export const groupKey = (domain, group) => `${domain}|${group}`;

function kindSummary(service, withOther) {
  return GROUPS.filter((group) => service.groups[group.value] && (withOther || group.value !== OTHER)).map((group) =>
    plural(service.groups[group.value], group.one, group.many),
  );
}

function statusLabel(status) {
  return h('span', { class: 'status', 'data-status': status }, icon(`status-${status}`, 12), STATUS_LABELS[status]);
}

function kindBar(service) {
  const total = service.lexicons.length;
  const segments = GROUPS.filter((group) => service.groups[group.value]).map((group) =>
    h('i', { 'data-kind': group.value, style: `width: ${((service.groups[group.value] / total) * 100).toFixed(1)}%` }),
  );

  return h('span', { class: 'kind-bar', 'aria-hidden': 'true' }, segments);
}

function serviceRow(service, { needle, open }) {
  const date = formatDate(service.updated);
  const kinds = kindSummary(service, false);

  return h(
    'button',
    { class: 'service-row', type: 'button', 'aria-expanded': String(open), 'aria-controls': panelId(service.domain) },
    h('span', { class: 'service-domain' }, highlight(service.domain, needle)),
    statusLabel(service.status),
    h(
      'span',
      { class: 'service-summary' },
      kindBar(service),
      h(
        'span',
        {},
        plural(service.lexicons.length, 'lexicon', 'lexicons'),
        kinds.length > 0 && h('span', { class: 'service-kinds', text: ` · ${kinds.join(' · ')}` }),
      ),
    ),
    h('span', { class: 'service-date' }, date && [date.day, h('span', { class: 'service-year', text: ` ${date.year}` })]),
    icon('chevron', 18, 'service-chevron'),
  );
}

function chip(label, value) {
  return h(
    'button',
    { class: 'chip copy', type: 'button', 'data-copy': value, 'aria-label': `Copy ${value}` },
    h('span', { class: 'chip-label', text: label }),
    h('span', { class: 'chip-value', text: value }),
    h('span', { class: 'chip-state copy-idle' }, icon('copy', 14)),
    h('span', { class: 'chip-state copy-done' }, icon('check', 14), 'Copied'),
  );
}

function note(lexicon) {
  const { icon: name, text } = NOTES[lexicon.state];

  return h(
    'p',
    { class: 'note', 'data-state': lexicon.state },
    icon(name, 16),
    h('span', {}, text, lexicon.reason && [' ', h('span', { class: 'note-reason', text: lexicon.reason })]),
  );
}

function lexiconCard(lexicon, service, { needle, repository }) {
  const chips = USAGE.filter((name) => lexicon[name]).map((name) => chip(name, lexicon[name]));

  return h(
    'article',
    { class: 'lexicon', 'data-kind': lexicon.group, 'data-state': lexicon.state },
    h(
      'div',
      { class: 'lexicon-head' },
      h('h5', { class: 'lexicon-nsid' }, highlight(lexicon.nsid, needle)),
      h('span', { class: 'kind-badge', text: KIND_LABELS[lexicon.kind] || lexicon.kind }),
      h(
        'a',
        { class: 'lexicon-schema', href: `${repository}/blob/main/lexicons/${service.domain}/${lexicon.nsid}.json` },
        'schema.json',
        icon('arrow-up-right', 12),
      ),
    ),
    lexicon.description && h('p', { class: 'lexicon-description' }, highlight(lexicon.description, needle)),
    NOTES[lexicon.state] && note(lexicon),
    chips.length > 0 && h('div', { class: 'lexicon-chips' }, chips),
  );
}

export function serviceGroups({ service, lexicons }, context) {
  const visible = filterLexicons(lexicons, context.filters.get(service.domain) || '');

  const groups = GROUPS.map((group) => {
    const all = visible.filter((lexicon) => lexicon.group === group.value);
    if (!all.length) return null;

    const expanded = context.expanded.has(groupKey(service.domain, group.value));
    const shown = expanded ? all : all.slice(0, context.lexiconsShownPerKind);
    const hidden = all.length - shown.length;

    return h(
      'section',
      { class: 'group', 'data-kind': group.value },
      h('h4', { class: 'group-head' }, h('i', { 'aria-hidden': 'true' }), h('strong', { text: group.label }), String(all.length)),
      h(
        'div',
        { class: 'group-items' },
        shown.map((lexicon) => lexiconCard(lexicon, service, context)),
      ),
      hidden > 0 &&
        h(
          'button',
          { class: 'group-more', type: 'button', 'data-group': group.value },
          group.value === OTHER ? `Show ${hidden} more` : `Show ${plural(hidden, `more ${group.one}`, `more ${group.many}`)}`,
          icon('chevron', 14),
        ),
    );
  }).filter(Boolean);

  if (!groups.length) groups.push(h('p', { class: 'panel-empty', text: 'No lexicon of this service matches.' }));

  return h('div', { class: 'groups' }, groups);
}

function servicePanel(entry, context) {
  const { service, lexicons } = entry;
  const total = service.lexicons.length;
  const count =
    lexicons.length < total ? `${lexicons.length} of ${plural(total, 'lexicon', 'lexicons')}` : plural(total, 'lexicon', 'lexicons');

  const filter =
    lexicons.length >= context.lexiconFilterFrom &&
    h(
      'label',
      { class: 'panel-filter' },
      h('span', { class: 'visually-hidden', text: `Filter lexicons of ${service.domain}` }),
      icon('search', 14),
      h('input', {
        type: 'search',
        placeholder: `Filter ${plural(lexicons.length, 'lexicon', 'lexicons')}`,
        value: context.filters.get(service.domain),
        autocomplete: 'off',
        autocapitalize: 'none',
        spellcheck: 'false',
      }),
    );

  return h(
    'div',
    { class: 'service-panel', id: panelId(service.domain) },
    h(
      'div',
      { class: 'panel-head' },
      h('p', { class: 'panel-summary' }, h('strong', { text: count }), ` · ${kindSummary(service, true).join(' · ')}`),
      filter,
      h(
        'button',
        { class: 'panel-link copy', type: 'button', 'data-copy': `${context.siteUrl}#${service.domain}` },
        icon('link', 14),
        h('span', { class: 'copy-idle', text: 'Copy link' }),
        h('span', { class: 'copy-done', text: 'Copied' }),
      ),
    ),
    serviceGroups(entry, context),
  );
}

export function serviceElement(entry, context) {
  const { service } = entry;
  const open = context.open.has(service.domain);

  return h(
    'div',
    { class: open ? 'service is-open' : 'service', id: service.domain, 'data-status': service.status },
    h('h3', { class: 'service-heading' }, serviceRow(service, { needle: context.needle, open })),
    open && servicePanel(entry, context),
  );
}
