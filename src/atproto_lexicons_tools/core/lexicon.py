import json
import re
import typing as t
from pathlib import Path

Document = dict[str, t.Any]

RECORD = 'record'
QUERY = 'query'
PROCEDURE = 'procedure'
SUBSCRIPTION = 'subscription'
PERMISSION_SET = 'permission-set'
DEFINITIONS = 'defs'

COUNTED_KINDS = (RECORD, QUERY, PROCEDURE, SUBSCRIPTION)
METHOD_KINDS = frozenset({QUERY, PROCEDURE})
_MAIN_KINDS = frozenset({*COUNTED_KINDS, PERMISSION_SET})

NSID_RE = re.compile(
    r'^[a-zA-Z]([a-zA-Z0-9-]{0,62})?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,62})?)+(\.[a-zA-Z]([a-zA-Z0-9]{0,62})?)$'
)

_LEXICON_VERSION = 1
_DEFINITION_SEPARATOR = '#'


def get_authority(nsid: str) -> str:
    return '.'.join(reversed(nsid.split('.')[:-1]))


def is_lexicon(nsid: str, value: t.Any) -> bool:
    return (
        bool(NSID_RE.match(nsid))
        and isinstance(value, dict)
        and value.get('id') == nsid
        and value.get('lexicon') == _LEXICON_VERSION
        and isinstance(value.get('defs'), dict)
    )


def read(path: Path) -> Document:
    """Read a lexicon file.

    Raises:
        OSError: The file cannot be read.
        ValueError: It is not a JSON object.
    """
    document = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(document, dict):
        message = f'{path.name} is not a JSON object'
        raise ValueError(message)  # noqa: TRY004

    return t.cast('Document', document)


def get_main(lexicon: Document) -> Document:
    defs = lexicon.get('defs')
    main = t.cast('dict[str, t.Any]', defs).get('main') if isinstance(defs, dict) else None

    return t.cast('Document', main) if isinstance(main, dict) else {}


def get_kind(lexicon: Document) -> str:
    kind = get_main(lexicon).get('type')

    return kind if isinstance(kind, str) and kind in _MAIN_KINDS else DEFINITIONS


def _find_targets(node: Document, own_nsid: str) -> set[str]:
    refs: list[t.Any] = []
    if node.get('type') == 'ref':
        refs.append(node.get('ref'))
    if node.get('type') == 'union' and isinstance(node.get('refs'), list):
        refs.extend(node['refs'])

    targets = {ref.split(_DEFINITION_SEPARATOR, 1)[0] for ref in refs if isinstance(ref, str)}

    return {target for target in targets if target != own_nsid and NSID_RE.match(target)}


def find_referenced_nsids(root: t.Any, own_nsid: str) -> set[str]:
    found: set[str] = set()
    pending: list[t.Any] = [root]

    while pending:
        node = pending.pop()

        if isinstance(node, dict):
            mapping = t.cast('Document', node)
            found |= _find_targets(mapping, own_nsid)
            pending.extend(mapping.values())
        elif isinstance(node, list):
            pending.extend(t.cast('list[t.Any]', node))

    return found
