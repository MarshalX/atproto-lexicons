import { ANY_KIND, DIGIT, groupOf } from './constants.js';

const byName = (a, b) => a.service.domain.localeCompare(b.service.domain);
const SORTERS = {
  name: byName,
  size: (a, b) => b.service.lexicons.length - a.service.lexicons.length || byName(a, b),
  changed: (a, b) => b.service.updated.localeCompare(a.service.updated) || byName(a, b),
};

function countBy(items, key) {
  const counts = {};
  for (const item of items) counts[key(item)] = (counts[key(item)] || 0) + 1;

  return counts;
}

function prepareService(service) {
  const lexicons = service.lexicons.map((lexicon) => ({
    ...lexicon,
    group: groupOf(lexicon.kind),
    haystack: `${lexicon.nsid}\n${lexicon.description}`.toLowerCase(),
  }));
  const first = service.domain.charAt(0).toUpperCase();

  return {
    ...service,
    lexicons,
    groups: countBy(lexicons, (lexicon) => lexicon.group),
    letter: /\d/.test(first) ? DIGIT : first,
  };
}

export async function loadCatalog(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);

  const raw = await response.json();
  const services = raw.services.map(prepareService);
  const lexicons = services.flatMap((service) => service.lexicons);

  return {
    services,
    repository: raw.repository,
    generated: raw.generated,
    sdkStars: raw.sdk_stars,
    lexiconCount: lexicons.length,
    groups: countBy(lexicons, (lexicon) => lexicon.group),
    letters: new Set(services.map((service) => service.letter)),
  };
}

/** Services that pass the filters, each with the lexicons that made it pass. */
export function select(catalog, { query, status, kind, sort, letter }) {
  const needle = query.trim().toLowerCase();
  const matched = [];

  for (const service of catalog.services) {
    const byDomain = !needle || service.domain.toLowerCase().includes(needle);

    let lexicons = byDomain ? service.lexicons : service.lexicons.filter((lexicon) => lexicon.haystack.includes(needle));
    if (kind !== ANY_KIND) lexicons = lexicons.filter((lexicon) => lexicon.group === kind);

    if (lexicons.length || (byDomain && kind === ANY_KIND)) matched.push({ service, lexicons });
  }

  const entries = matched
    .filter(({ service }) => (status === 'all' || service.status === status) && (!letter || service.letter === letter))
    .sort(SORTERS[sort]);

  return {
    needle,
    entries,
    statuses: { all: matched.length, ...countBy(matched, ({ service }) => service.status) },
    lexiconCount: entries.reduce((total, entry) => total + entry.lexicons.length, 0),
  };
}

export function filterLexicons(lexicons, text) {
  const needle = text.trim().toLowerCase();

  return needle ? lexicons.filter((lexicon) => lexicon.haystack.includes(needle)) : lexicons;
}
