import { $, h, icon } from '../lib/dom.js';
import { formatDate, formatNumber, plural } from '../lib/format.js';
import { createDropdown } from '../ui/dropdown.js';
import { createSearch } from '../ui/search.js';
import { ANY_KIND, DIGIT, GROUPS, LETTERS, OTHER, SORTS, STATUSES } from './constants.js';
import { loadCatalog, select } from './store.js';
import { groupKey, serviceElement, serviceGroups } from './view.js';

const WIDE = matchMedia('(min-width: 720px)');
const DEFAULTS = { query: '', status: 'all', kind: ANY_KIND, letter: null };

function linkedDomain() {
  try {
    return decodeURIComponent(location.hash.slice(1));
  } catch {
    return '';
  }
}

export function initCatalog(config) {
  const root = $('#catalog');
  const els = {
    statuses: $('[data-status-filter]', root),
    letters: $('[data-letters]', root),
    count: $('[data-result-count]', root),
    built: $('[data-built]', root),
    services: $('[data-services]', root),
    status: $('[data-catalog-status]', root),
    empty: $('[data-empty]', root),
    showAll: $('[data-show-all]', root),
  };

  const state = {
    ...DEFAULTS,
    query: new URLSearchParams(location.search).get('q') || '',
    sort: SORTS[0].value,
    showAll: false,
    open: new Set(),
    filters: new Map(),
    expanded: new Set(),
  };
  let catalog = null;
  let entries = new Map();
  let needle = '';

  const search = createSearch({
    suggestions: config.search.suggestions,
    onChange: setQuery,
    onSubmit: revealResults,
    onArrowDown: () => $('.service-row', els.services)?.focus(),
  });
  search.show(state.query);

  const context = () => ({
    needle,
    open: state.open,
    filters: state.filters,
    expanded: state.expanded,
    repository: catalog.repository,
    siteUrl: config.siteUrl,
    lexiconsShownPerKind: config.catalog.lexiconsShownPerKind,
    lexiconFilterFrom: config.catalog.lexiconFilterFrom,
  });

  const isDefaultView = (filters = state) => Object.entries(DEFAULTS).every(([key, value]) => filters[key] === value);

  function renderCount(result, capped) {
    const services = plural(result.entries.length, 'service', 'services');
    let detail;

    if (result.needle) {
      const verb = result.lexiconCount === 1 ? 'lexicon matches' : 'lexicons match';
      detail = ` · ${formatNumber(result.lexiconCount)} ${verb} “${state.query.trim()}”`;
    } else if (state.letter) {
      detail = state.letter === DIGIT ? ' starting with a digit' : ` starting with ${state.letter}`;
    } else {
      detail = ` · ${plural(result.lexiconCount, 'lexicon', 'lexicons')}`;
      if (capped) detail += ` · showing the first ${config.catalog.servicesShown}`;
    }

    els.count.replaceChildren(h('strong', { text: services }), detail);
  }

  function renderEmpty() {
    const query = state.query.trim();
    const onlySearch = isDefaultView({ ...state, query: '' });

    for (const node of els.empty.querySelectorAll('[data-empty-search]')) node.hidden = !query;
    $('[data-empty-filters]', els.empty).hidden = Boolean(query);
    $('[data-empty-query]', els.empty).textContent = query;
    $('[data-reset]', els.empty).textContent = query && onlySearch ? 'Clear search' : 'Clear filters';
  }

  function render({ openMatches = false } = {}) {
    const result = select(catalog, state);
    if (openMatches && result.needle && result.entries.length <= config.catalog.searchOpensUpTo) {
      for (const { service } of result.entries) state.open.add(service.domain);
    }

    const capped = isDefaultView() && !state.showAll && result.entries.length > config.catalog.servicesShown;
    const shown = capped ? result.entries.slice(0, config.catalog.servicesShown) : result.entries;

    needle = result.needle;
    entries = new Map(shown.map((entry) => [entry.service.domain, entry]));

    const shared = context();
    els.services.replaceChildren(...shown.map((entry) => serviceElement(entry, shared)));

    els.empty.hidden = shown.length > 0;
    if (!shown.length) renderEmpty();

    els.showAll.hidden = !capped;
    renderCount(result, capped);

    for (const button of els.statuses.children) {
      button.setAttribute('aria-pressed', String(button.dataset.value === state.status));
      button.lastElementChild.textContent = formatNumber(result.statuses[button.dataset.value] || 0);
    }
    for (const button of els.letters.children) {
      button.setAttribute('aria-pressed', String((button.dataset.value || null) === state.letter));
    }
  }

  function update(changes) {
    Object.assign(state, changes);
    render();
  }

  function refreshService(domain) {
    const current = document.getElementById(domain);
    const focused = current.contains(document.activeElement) && document.activeElement.classList.contains('service-row');
    const next = serviceElement(entries.get(domain), context());

    current.replaceWith(next);
    if (focused) $('.service-row', next).focus();
  }

  function setQuery(query) {
    state.query = query;
    state.open.clear();

    const url = new URL(location.href);
    if (query.trim()) url.searchParams.set('q', query.trim());
    else url.searchParams.delete('q');
    url.hash = '';
    history.replaceState(null, '', url);

    if (catalog) render({ openMatches: true });
  }

  function toggle(domain) {
    const open = !state.open.has(domain);
    if (open) state.open.add(domain);
    else state.open.delete(domain);

    if (open) history.replaceState(null, '', `#${encodeURIComponent(domain)}`);
    else if (linkedDomain() === domain) history.replaceState(null, '', location.pathname + location.search);

    refreshService(domain);
  }

  function reset() {
    search.show('');
    Object.assign(state, DEFAULTS);
    setQuery('');
  }

  function revealResults() {
    if (root.getBoundingClientRect().top > innerHeight * 0.55) root.scrollIntoView({ block: 'start' });
    if (!WIDE.matches) document.activeElement?.blur();
  }

  function openLinked() {
    const domain = linkedDomain();
    if (!catalog.services.some((service) => service.domain === domain)) return;

    state.open.add(domain);
    state.showAll = true;
    render();

    if (!entries.has(domain)) {
      search.show('');
      Object.assign(state, DEFAULTS);
      render();
    }
    document.getElementById(domain).scrollIntoView({ block: 'start' });
  }

  function buildControls() {
    els.statuses.replaceChildren(
      ...STATUSES.map(({ value, label }) =>
        h(
          'button',
          { type: 'button', 'data-value': value, 'data-status': value, onclick: () => update({ status: value }) },
          value !== 'all' && icon(`status-${value}`, 12),
          label,
          h('span'),
        ),
      ),
    );

    const letterLabel = (letter) => (letter === DIGIT ? 'Starting with a digit' : `Starting with ${letter}`);
    els.letters.replaceChildren(
      h('button', { type: 'button', text: 'All', 'aria-label': 'All letters', onclick: () => update({ letter: null }) }),
      ...LETTERS.map((letter) =>
        h('button', {
          type: 'button',
          text: letter,
          'data-value': letter,
          'aria-label': letterLabel(letter),
          disabled: !catalog.letters.has(letter),
          onclick: () => {
            state.open.clear();
            update({ letter });
          },
        }),
      ),
    );

    createDropdown($('[data-dropdown="kind"]', root), {
      id: 'menu-kind',
      label: 'Defines',
      value: state.kind,
      onChange: (kind) => update({ kind }),
      options: [
        { value: ANY_KIND, label: 'Any kind', hint: formatNumber(catalog.lexiconCount), separated: true },
        ...GROUPS.filter((group) => group.value !== OTHER).map((group) => ({
          value: group.value,
          label: group.label,
          kind: group.value,
          hint: formatNumber(catalog.groups[group.value] || 0),
        })),
      ],
    });
    createDropdown($('[data-dropdown="sort"]', root), {
      id: 'menu-sort',
      label: 'Sort',
      value: state.sort,
      onChange: (sort) => update({ sort }),
      options: SORTS,
    });
  }

  function bindEvents() {
    els.services.addEventListener('click', (event) => {
      const service = event.target.closest('.service');
      if (!service) return;

      if (event.target.closest('.service-row')) {
        toggle(service.id);
        return;
      }

      const more = event.target.closest('.group-more');
      if (more) {
        state.expanded.add(groupKey(service.id, more.dataset.group));
        refreshGroups(service);
      }
    });

    els.services.addEventListener('input', (event) => {
      const service = event.target.closest('.service');
      if (!event.target.closest('.panel-filter')) return;

      state.filters.set(service.id, event.target.value);
      refreshGroups(service);
    });

    els.services.addEventListener('keydown', (event) => {
      const row = event.target.closest('.service-row');
      const step = { ArrowDown: 1, ArrowUp: -1 }[event.key];
      if (!row || !step) return;

      event.preventDefault();
      const rows = [...els.services.querySelectorAll('.service-row')];
      const target = rows[rows.indexOf(row) + step];

      if (target) target.focus();
      else if (step < 0) search.focus();
    });

    $('button', els.showAll).addEventListener('click', () => update({ showAll: true }));
    $('[data-reset]', els.empty).addEventListener('click', reset);

    for (const button of els.empty.querySelectorAll('[data-example]')) {
      const example = config.search.examples[button.dataset.example];
      button.textContent = example;
      button.addEventListener('click', () => {
        Object.assign(state, DEFAULTS);
        search.set(example);
      });
    }

    addEventListener('hashchange', openLinked);
  }

  function refreshGroups(service) {
    $('.groups', service).replaceWith(serviceGroups(entries.get(service.id), context()));
  }

  function renderFacts() {
    const total = catalog.services.length;
    const date = formatDate(catalog.generated);
    const setPlaceholder = () =>
      search.setPlaceholder(
        WIDE.matches
          ? `Search ${formatNumber(total)} services and ${formatNumber(catalog.lexiconCount)} lexicons`
          : 'Search services and NSIDs',
      );

    els.built.textContent = `Built ${date.day} ${date.year}, rebuilt daily`;
    $('[data-show-all-label]', els.showAll).textContent = `Show all ${formatNumber(total)} services`;

    setPlaceholder();
    WIDE.addEventListener('change', setPlaceholder);
  }

  const loaded = loadCatalog(config.catalogUrl).then(
    (data) => {
      catalog = data;
      els.status.hidden = true;

      buildControls();
      bindEvents();
      renderFacts();
      render({ openMatches: true });
      openLinked();

      return catalog;
    },
    (error) => {
      console.error(error);
      els.status.textContent = 'The catalog could not be loaded. Reload the page to try again.';

      return null;
    },
  );

  return { loaded, focusSearch: search.focus };
}
