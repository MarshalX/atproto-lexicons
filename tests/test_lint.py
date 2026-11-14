import json
import typing as t
from pathlib import Path

import pytest

from atproto_lexicons_tools import lint
from atproto_lexicons_tools.core.lock import Lock
from atproto_lexicons_tools.core.registry import Service
from atproto_lexicons_tools.paths import LEXICONS_DIR, LOCK_PATH, SERVICES_PATH

_DID = 'did:plc:aaaaaaaaaaaaaaaaaaaaaaaa'
_OTHER_DID = 'did:plc:bbbbbbbbbbbbbbbbbbbbbbbb'


def _registry(*entries: t.Any) -> dict[str, t.Any]:
    return {'services': list(entries)}


def _service(domain: str, *dids: str) -> dict[str, t.Any]:
    return {'domain': domain, 'dids': list(dids)}


def test_valid_registry_has_no_problems() -> None:
    data = _registry(_service('example.com', _DID, _OTHER_DID), _service('teal.fm'), {'domain': 'web.site'})

    assert lint.check_registry(data) == []


@pytest.mark.parametrize(
    ('data', 'expected'),
    [
        ([], 'single key "services"'),
        ({'services': [], 'extra': 1}, 'single key "services"'),
        ({'services': {}}, 'must be a list'),
        (_registry('teal.fm'), 'must be an object'),
        (_registry({'dids': []}), '"domain" is required'),
        (_registry({'domain': 'teal.fm', 'name': 'Teal'}), 'unknown key "name"'),
        (_registry(_service('Teal.fm')), 'not a lowercase domain name'),
        (_registry(_service('https://teal.fm')), 'not a lowercase domain name'),
        (_registry(_service('localhost')), 'not a lowercase domain name'),
        (_registry(_service('fm.teal.feed.play.')), 'not a lowercase domain name'),
        (_registry(_service('bsky.app')), 'the SDK ships the lexicons'),
        (_registry({'domain': 'teal.fm', 'dids': _DID}), 'must be a list of strings'),
        (_registry(_service('teal.fm', 'did:key:z6Mk')), 'is not a did:plc or did:web'),
        (_registry(_service('teal.fm', _DID, _DID)), 'has duplicates'),
        (_registry(_service('teal.fm', _OTHER_DID, _DID)), '"dids" must be sorted'),
        (_registry(_service('teal.fm'), _service('teal.fm')), 'listed more than once'),
        (_registry(_service('teal.fm'), _service('example.com')), 'services must be sorted by domain'),
        (_registry(_service('example.com'), _service('labs.example.com')), 'is inside example.com'),
    ],
)
def test_invalid_registry_is_reported(data: t.Any, expected: str) -> None:
    assert any(expected in problem.message for problem in lint.check_registry(data))


def test_formatting_sorts_services_and_dids() -> None:
    data = _registry(_service('teal.fm', _OTHER_DID, _DID, _DID), {'domain': 'example.com'})

    formatted = json.loads(lint.format_registry(data))

    assert formatted == _registry(_service('example.com'), _service('teal.fm', _DID, _OTHER_DID))
    assert lint.check_registry(formatted) == []


def _write(path: Path, data: t.Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf-8')


def _entries(*nsids: str) -> dict[str, dict[str, str]]:
    return {nsid: {'did': _DID, 'cid': 'c'} for nsid in nsids}


def _lock(external: tuple[str, ...] = (), **services: list[str]) -> dict[str, t.Any]:
    return {
        'services': {domain: _entries(*nsids) for domain, nsids in services.items()},
        'external': _entries(*external),
    }


def test_lexicons_matching_the_lock_have_no_problems(tmp_path: Path) -> None:
    _write(tmp_path / 'teal.fm' / 'fm.teal.feed.play.json', {'id': 'fm.teal.feed.play'})
    lock = Lock.from_dict(_lock(('org.other.thing',), **{'teal.fm': ['fm.teal.feed.play'], 'example.com': []}))
    _write(tmp_path / '_external' / 'org.other.thing.json', {'id': 'org.other.thing'})

    assert lint.check_lexicons([Service('example.com', ()), Service('teal.fm', ())], lock, tmp_path) == []


def test_lexicons_out_of_step_are_reported(tmp_path: Path) -> None:
    _write(tmp_path / 'teal.fm' / 'fm.teal.feed.play.json', {'id': 'fm.teal.feed.other'})
    _write(tmp_path / 'teal.fm' / 'fm.teal.extra.json', {'id': 'fm.teal.extra'})
    _write(tmp_path / 'teal.fm' / 'com.example.post.json', {'id': 'com.example.post'})
    _write(tmp_path / 'stray.dev' / 'dev.stray.thing.json', {'id': 'dev.stray.thing'})
    tmp_path.joinpath('teal.fm', 'fm.teal.broken.json').write_text('{', encoding='utf-8')
    lock = Lock.from_dict(
        _lock(
            **{
                'teal.fm': ['fm.teal.feed.play', 'fm.teal.gone', 'com.example.post', 'fm.teal.broken'],
                'removed.org': [],
            }
        )
    )

    problems = lint.check_lexicons([Service('teal.fm', ()), Service('new.app', ())], lock, tmp_path)

    assert problems == [
        'new.app: not fetched yet, run `lex fetch`',
        'removed.org: in the lock but not in the registry',
        'lexicons/stray.dev: no such service in the registry',
        'teal.fm/fm.teal.gone.json: in the lock but missing',
        'teal.fm/fm.teal.extra.json: not in the lock',
        'teal.fm/com.example.post.json: does not belong to teal.fm',
        'teal.fm/fm.teal.broken.json: not valid JSON',
        'teal.fm/fm.teal.feed.play.json: the "id" of the lexicon must match the file name',
    ]


def test_fix_rewrites_an_unsorted_registry(tmp_path: Path) -> None:
    services_path = tmp_path / 'services.json'
    _write(services_path, _registry(_service('teal.fm', _OTHER_DID, _DID), _service('example.com')))
    _write(tmp_path / 'lock.json', _lock(**{'teal.fm': [], 'example.com': []}))

    assert lint.lint(services_path, tmp_path / 'lock.json', tmp_path / 'lexicons', fix=False)
    assert lint.lint(services_path, tmp_path / 'lock.json', tmp_path / 'lexicons', fix=True) == []
    assert lint.lint(services_path, tmp_path / 'lock.json', tmp_path / 'lexicons', fix=False) == []


def test_fix_does_not_touch_an_invalid_registry(tmp_path: Path) -> None:
    services_path = tmp_path / 'services.json'
    _write(services_path, _registry(_service('teal.fm'), _service('Example.com')))
    before = services_path.read_text(encoding='utf-8')

    problems = lint.lint(services_path, tmp_path / 'lock.json', tmp_path / 'lexicons', fix=True)

    assert any('not a lowercase domain name' in problem for problem in problems)
    assert services_path.read_text(encoding='utf-8') == before


def test_unformatted_registry_is_reported(tmp_path: Path) -> None:
    services_path = tmp_path / 'services.json'
    services_path.write_text(json.dumps(_registry(_service('teal.fm'))), encoding='utf-8')

    problems = lint.lint(services_path, tmp_path / 'lock.json', tmp_path / 'lexicons', fix=False)

    assert problems == ['services.json: not formatted, run `lex lint --fix`']


def test_repository_passes_its_own_lint() -> None:
    assert lint.lint(SERVICES_PATH, LOCK_PATH, LEXICONS_DIR, fix=False) == []


def test_fix_leaves_a_duplicated_service_alone(tmp_path: Path) -> None:
    services_path = tmp_path / 'services.json'
    _write(services_path, _registry(_service('teal.fm', _OTHER_DID, _DID), _service('teal.fm')))
    before = services_path.read_text(encoding='utf-8')

    problems = lint.lint(services_path, tmp_path / 'lock.json', tmp_path / 'lexicons', fix=True)

    assert any('listed more than once' in problem for problem in problems)
    assert services_path.read_text(encoding='utf-8') == before


def test_malformed_lock_is_reported(tmp_path: Path) -> None:
    services_path = tmp_path / 'services.json'
    services_path.write_text(lint.format_registry(_registry(_service('teal.fm'))), encoding='utf-8')
    _write(tmp_path / 'lock.json', {'services': {'teal.fm': {'fm.teal.feed.play': {'cid': 'c'}}}})

    problems = lint.lint(services_path, tmp_path / 'lock.json', tmp_path / 'lexicons', fix=False)

    assert len(problems) == 1
    assert problems[0].startswith('lock.json: not a lock of lexicons')
