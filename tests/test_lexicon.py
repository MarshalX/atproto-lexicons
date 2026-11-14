import typing as t

from atproto_lexicons_tools.core import lexicon


def test_authority_is_the_reversed_namespace() -> None:
    assert lexicon.get_authority('fm.teal.feed.play') == 'feed.teal.fm'


def test_referenced_nsids_skip_local_and_own_references() -> None:
    schema = {
        'defs': {
            'main': {
                'type': 'object',
                'properties': {
                    'a': {'type': 'ref', 'ref': 'com.other.defs#view'},
                    'b': {'type': 'ref', 'ref': '#local'},
                    'c': {'type': 'array', 'items': {'type': 'union', 'refs': ['com.third.thing', 'com.example.post']}},
                    'd': {'type': 'ref', 'ref': 'not a reference'},
                },
            }
        }
    }

    assert lexicon.find_referenced_nsids(schema, 'com.example.post') == {'com.other.defs', 'com.third.thing'}


def test_references_are_found_at_any_depth() -> None:
    nodes: list[t.Any] = [{'type': 'ref', 'ref': 'com.other.deep'}]
    for _ in range(5000):
        nodes.append({'items': [nodes[-1]]})

    assert lexicon.find_referenced_nsids(nodes[-1], 'com.example.post') == {'com.other.deep'}


def test_kind_is_the_type_of_the_main_definition() -> None:
    assert lexicon.get_kind({'defs': {'main': {'type': 'record'}}}) == lexicon.RECORD
    assert lexicon.get_kind({'defs': {'main': {'type': 'permission-set'}}}) == lexicon.PERMISSION_SET


def test_lexicon_without_a_usable_main_definition_holds_definitions() -> None:
    documents: list[dict[str, t.Any]] = [
        {'defs': {'main': {'type': 'object'}}},
        {'defs': {'view': {'type': 'object'}}},
        {'defs': {'main': 'record'}},
        {'defs': {'main': {'type': ['record']}}},
        {'defs': []},
        {},
    ]

    for document in documents:
        assert lexicon.get_kind(document) == lexicon.DEFINITIONS
