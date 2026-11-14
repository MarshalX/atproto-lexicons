import json
import typing as t
from pathlib import Path

from atproto_lexicons_tools.build import support
from atproto_lexicons_tools.build.diagnostics import parse_warnings
from atproto_lexicons_tools.core.registry import Service

_SERVICE = Service('example.com', ())
_NSIDS = {'com.example.post', 'com.example.getPosts', 'com.example.defs'}
_KINDS = {'record': 1, 'query': 1, 'procedure': 0, 'subscription': 0}


def _classify(warnings: list[str], sdk_nsids: t.AbstractSet[str] = frozenset()) -> support.ServiceSupport:
    return support.classify(_SERVICE, _NSIDS, sdk_nsids, parse_warnings(warnings), _KINDS)


def test_service_without_warnings_is_fully_supported() -> None:
    result = _classify(['Skipped org.other.thing.json: defs.main: bad'])

    assert result.status == support.Status.FULL
    assert (result.lexicons, result.generated) == (3, 3)


def test_skipped_lexicon_makes_a_service_partial() -> None:
    result = _classify(['Skipped com.example.defs.json: defs.main: bad'])

    assert result.status == support.Status.PARTIAL
    assert result.skipped_lexicons == ['com.example.defs']
    assert result.generated == 2


def test_skipped_method_and_untyped_reference_make_a_service_partial() -> None:
    result = _classify(
        [
            "Skipped method com.example.getPosts: its body 'com.missing.thing' is not available",
            "Unresolved reference '#nope' in com.example.post: '#nope' names a definition that is missing.",
        ]
    )

    assert result.status == support.Status.PARTIAL
    assert result.skipped_methods == ['com.example.getPosts']
    assert result.weakened_lexicons == ['com.example.post']
    assert result.generated == 3


def test_service_with_nothing_generated_is_not_supported() -> None:
    result = _classify([f'Skipped {nsid}.json: bad' for nsid in sorted(_NSIDS)])

    assert result.status == support.Status.UNSUPPORTED
    assert result.generated == 0


def test_lexicons_of_the_sdk_are_left_to_it() -> None:
    result = _classify([], sdk_nsids={'com.example.post'})

    assert result.status == support.Status.FULL
    assert (result.generated, result.provided_by_sdk) == (2, 1)


def test_kinds_are_counted_by_the_main_definition(tmp_path: Path) -> None:
    for name, kind in (('a', 'record'), ('b', 'query'), ('c', 'query'), ('d', 'object')):
        tmp_path.joinpath(f'{name}.json').write_text(json.dumps({'defs': {'main': {'type': kind}}}))
    tmp_path.joinpath('e.json').write_text(json.dumps({'defs': {'other': {'type': 'token'}}}))

    counts = support.count_kinds(sorted(tmp_path.glob('*.json')))

    assert counts == {'record': 1, 'query': 2, 'procedure': 0, 'subscription': 0}


def test_rendered_list_has_a_row_per_service() -> None:
    rendered = support.render([_classify([]), _classify(['Skipped com.example.defs.json: bad'])])

    assert '| Full | 1 |' in rendered
    assert '| Partial | 1 |' in rendered
    assert rendered.count('| `example.com` |') == 2
    assert '| `example.com` | Partial | 2 of 3 | 1 | 1 | 0 | 1 |  |' in rendered
