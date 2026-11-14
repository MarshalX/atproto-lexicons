import json
from pathlib import Path

import pytest

from atproto_lexicons_tools.core.lock import Changes, Lock, LockEntry, date_changes, diff_locks
from atproto_lexicons_tools.paths import LOCK_PATH

_DID = 'did:plc:aaaaaaaaaaaaaaaaaaaaaaaa'


def _entries(**cids: str) -> dict[str, LockEntry]:
    return {nsid: LockEntry(_DID, cid) for nsid, cid in cids.items()}


def test_locks_are_compared_by_content_hash() -> None:
    old = Lock(services={'example.com': _entries(a='1', b='1')}, external=_entries(x='1'))
    new = Lock(services={'example.com': _entries(a='1', b='2', c='1')})

    assert diff_locks(old, new) == Changes(added=['c'], changed=['b'], removed=['x'])
    assert not diff_locks(old, Lock.from_dict(old.to_dict()))


def test_service_keeps_its_date_until_its_lexicons_change() -> None:
    old = Lock(
        services={'same.dev': _entries(a='1'), 'changed.dev': _entries(a='1'), 'gone.dev': {}},
        updated={'same.dev': '2026-01-01', 'changed.dev': '2026-01-01', 'gone.dev': '2026-01-01'},
    )
    new = {'same.dev': _entries(a='1'), 'changed.dev': _entries(a='2'), 'new.dev': _entries(a='1')}

    assert date_changes(old, new, '2026-11-13') == {
        'same.dev': '2026-01-01',
        'changed.dev': '2026-11-13',
        'new.dev': '2026-11-13',
    }


def test_lock_is_empty_until_the_first_fetch(tmp_path: Path) -> None:
    assert Lock.load(tmp_path / 'lock.json') == Lock()


def test_committed_lock_is_written_back_unchanged(tmp_path: Path) -> None:
    path = tmp_path / 'lock.json'

    Lock.load(LOCK_PATH).save(path)

    assert path.read_text(encoding='utf-8') == LOCK_PATH.read_text(encoding='utf-8')


@pytest.mark.parametrize(
    'data',
    [
        [],
        {'services': []},
        {'services': {'example.com': {'com.example.post': {'cid': 'c'}}}},
        {'external': {'com.example.post': 'cid'}},
    ],
)
def test_malformed_lock_is_rejected(tmp_path: Path, data: object) -> None:
    path = tmp_path / 'lock.json'
    path.write_text(json.dumps(data), encoding='utf-8')

    with pytest.raises(ValueError, match='not a lock of lexicons'):
        Lock.load(path)
