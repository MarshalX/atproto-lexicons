import json
from pathlib import Path

import httpx
import pytest

from atproto_lexicons_tools.core.lock import Lock, LockEntry
from atproto_lexicons_tools.core.registry import Service
from atproto_lexicons_tools.fetch import fetcher, storage
from atproto_lexicons_tools.fetch.resolver import Resolver
from tests.helpers import (
    DID,
    OTHER_DID,
    Records,
    make_lexicon,
    make_record,
    make_reference,
    make_transport,
    make_txt_lookup,
)

_SERVICE = Service('example.com', (DID,))
_POST = 'com.example.post'
_THING = 'org.other.thing'
_AUTHORITIES = {'example.com': DID, 'other.org': OTHER_DID}
_REPOS: dict[str, Records] = {
    DID: [make_record(DID, _POST, make_lexicon(_POST, make_reference(_THING)))],
    OTHER_DID: [make_record(OTHER_DID, _THING, make_lexicon(_THING))],
}
_LOCK = Lock(
    services={'example.com': {_POST: LockEntry(DID, f'cid-{_POST}')}},
    external={_THING: LockEntry(OTHER_DID, f'cid-{_THING}')},
)


@pytest.fixture
def lexicons_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(fetcher, 'LEXICONS_DIR', tmp_path)
    monkeypatch.setattr(fetcher, 'get_sdk_nsids', frozenset[str])

    return tmp_path


def _serve(monkeypatch: pytest.MonkeyPatch, repos: dict[str, Records]) -> None:
    def make_resolver(client: httpx.AsyncClient) -> Resolver:
        return Resolver(client, make_txt_lookup(_AUTHORITIES), retry_delay=0)

    monkeypatch.setattr(fetcher, '_make_client', lambda: httpx.AsyncClient(transport=make_transport(repos)))
    monkeypatch.setattr(fetcher, 'Resolver', make_resolver)


def _read(path: Path) -> object:
    return json.loads(path.read_text(encoding='utf-8'))


def _read_all(directory: Path) -> dict[Path, str]:
    return {path: path.read_text(encoding='utf-8') for path in directory.rglob('*.json')}


async def test_lexicons_and_what_they_refer_to_are_written(lexicons_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _REPOS)
    lexicons_dir.joinpath('gone.dev').mkdir()

    lock, errors = await fetcher.fetch([_SERVICE], Lock())

    assert (lock, errors) == (_LOCK, [])
    assert _read(lexicons_dir / 'example.com' / f'{_POST}.json') == make_lexicon(_POST, make_reference(_THING))
    assert _read(lexicons_dir / '_external' / f'{_THING}.json') == make_lexicon(_THING)
    assert not lexicons_dir.joinpath('gone.dev').exists()


async def test_outage_keeps_what_was_fetched_before(lexicons_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _REPOS)
    await fetcher.fetch([_SERVICE], Lock())
    before = _read_all(lexicons_dir)

    _serve(monkeypatch, {})
    lock, errors = await fetcher.fetch([_SERVICE], _LOCK)

    assert lock.services == _LOCK.services
    assert lock.external == _LOCK.external
    assert lock.unreachable == ['example.com']
    assert errors == [f'{DID}: HTTP 400', f'{OTHER_DID}: HTTP 400']
    assert _read_all(lexicons_dir) == before


async def test_lexicon_that_is_gone_is_removed(lexicons_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _REPOS)
    await fetcher.fetch([_SERVICE], Lock())

    _serve(monkeypatch, {DID: [], OTHER_DID: []})
    lock, errors = await fetcher.fetch([_SERVICE], _LOCK)

    assert (lock, errors) == (Lock(services={'example.com': {}}), [])
    assert _read_all(lexicons_dir) == {}


async def test_oversized_lexicon_is_left_out_and_reported(lexicons_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    large = make_lexicon('com.example.large', {'main': {'type': 'token', 'description': 'x' * 2048}})
    _serve(
        monkeypatch, {DID: [make_record(DID, 'com.example.large', large), make_record(DID, _POST, make_lexicon(_POST))]}
    )
    monkeypatch.setattr(storage, '_MAX_LEXICON_BYTES', 1024)

    lock, errors = await fetcher.fetch([_SERVICE], Lock())

    assert list(lock.services['example.com']) == [_POST]
    assert errors == ['com.example.large: left out, larger than 1 KiB']
    assert not lexicons_dir.joinpath('example.com', 'com.example.large.json').exists()


async def test_external_lexicon_of_a_registered_service_is_left_to_it(
    lexicons_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _serve(monkeypatch, _REPOS)

    lock, _ = await fetcher.fetch([_SERVICE, Service('other.org', ())], Lock())

    assert lock.external == {}
    assert list(lock.services['other.org']) == [_THING]
    assert not lexicons_dir.joinpath('_external').exists()
