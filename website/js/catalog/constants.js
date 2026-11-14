export const STATUSES = [
  { value: 'all', label: 'All' },
  { value: 'full', label: 'Full' },
  { value: 'partial', label: 'Partial' },
  { value: 'unsupported', label: 'Not supported' },
];
export const STATUS_LABELS = Object.fromEntries(STATUSES.map(({ value, label }) => [value, label]));

export const OTHER = 'other';
export const GROUPS = [
  { value: 'record', label: 'Records', one: 'record', many: 'records' },
  { value: 'query', label: 'Queries', one: 'query', many: 'queries' },
  { value: 'procedure', label: 'Procedures', one: 'procedure', many: 'procedures' },
  { value: 'subscription', label: 'Subscriptions', one: 'subscription', many: 'subscriptions' },
  { value: OTHER, label: 'Other', one: 'other', many: 'other' },
];
const GROUP_VALUES = new Set(GROUPS.map((group) => group.value));

export const groupOf = (kind) => (GROUP_VALUES.has(kind) ? kind : OTHER);

export const KIND_LABELS = { 'permission-set': 'permission set', defs: 'definitions' };

export const ANY_KIND = 'any';

export const SORTS = [
  { value: 'name', label: 'Name', hint: 'A to Z' },
  { value: 'size', label: 'Size', hint: 'most lexicons' },
  { value: 'changed', label: 'Last changed', hint: 'newest first' },
];

export const DIGIT = '#';
export const LETTERS = [DIGIT, ...'ABCDEFGHIJKLMNOPQRSTUVWXYZ'];

export const NOTES = {
  skipped: { icon: 'ban', text: 'Skipped: invalid schema.' },
  'method-skipped': { icon: 'info', text: 'Models only: no client method for this one.' },
  untyped: { icon: 'warning', text: 'Has untyped references.' },
  sdk: { icon: 'check', text: 'Ships with the atproto SDK: import it from atproto.' },
};

export const USAGE = ['client', 'model', 'id'];
