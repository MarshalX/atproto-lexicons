export default {
  catalogUrl: 'catalog.json',
  siteUrl: 'https://lex.atproto.blue/',

  search: {
    suggestions: ['teal.fm', 'dev.sensorthings.observation', 'org.tangled', 'podping'],
    examples: { domain: 'teal.fm', nsid: 'dev.sensorthings.observation' },
  },

  // x is a percentage of the hero width, y is pixels from its top
  backdrop: {
    drift: 16,
    items: [
      { text: 'fm.teal.feed.play', x: 4, y: 170 },
      { text: 'org.tangled.git.refs', x: 77, y: 150 },
      { text: 'dev.sensorthings.observation', x: 3, y: 340 },
      { text: 'at.podping.records.podping', x: 80, y: 320 },
      { text: 'net.atmowx.observation', x: 3, y: 520 },
      { text: 'pub.leaflet.document', x: 82, y: 490 },
      { text: 'adsb.at', x: 87, y: 236, small: true },
      { text: 'bookhive.buzz', x: 11, y: 262, small: true },
      { text: 'astro-colibri.science', x: 78, y: 410, small: true },
      { text: 'lexicon.community', x: 8, y: 440, small: true },
    ],
  },

  catalog: {
    servicesShown: 20,
    searchOpensUpTo: 3,
    lexiconsShownPerKind: 8,
    lexiconFilterFrom: 13,
  },

  hotkeys: {
    focusSearch: ['/', 'mod+k'],
    toggleTheme: ['mod+shift+l'],
  },

  copiedMs: 1600,
};
