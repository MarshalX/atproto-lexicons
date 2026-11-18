import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from atproto_lexicons_tools import cli, review
from atproto_lexicons_tools.build.support import ServiceSupport, Status, SupportList
from atproto_lexicons_tools.core.lock import Lock, LockEntry

_DID = 'did:plc:aaaaaaaaaaaaaaaaaaaaaaaa'
_KINDS = {'record': 0, 'query': 0, 'procedure': 0, 'subscription': 0}


def _lock(**cids: str) -> Lock:
    entries = {nsid.replace('_', '.'): LockEntry(_DID, cid) for nsid, cid in cids.items()}
    return Lock(services={'example.com': entries})


def _support(status: Status = Status.FULL, generated: int = 2) -> SupportList:
    service = ServiceSupport('example.com', status, 2, generated, 0, _KINDS, [], [], [])
    return SupportList([service], [])


def test_update_that_adds_and_changes_is_merged() -> None:
    reasons = review.find_hold_reasons(
        _lock(com_example_a='1'), _lock(com_example_a='2', com_example_b='1'), _support(), _support()
    )

    assert reasons == []


def test_removed_lexicons_hold_the_update() -> None:
    reasons = review.find_hold_reasons(_lock(com_example_a='1', com_example_b='1'), _lock(), _support(), _support())

    assert reasons == ['2 lexicons are removed: `com.example.a`, `com.example.b`.']


def test_worse_support_holds_the_update() -> None:
    reasons = review.find_hold_reasons(_lock(), _lock(), _support(), _support(Status.PARTIAL, generated=1))

    assert reasons == ['`example.com` is supported worse: full before, partial now.']


def test_fewer_generated_lexicons_hold_the_update() -> None:
    reasons = review.find_hold_reasons(
        _lock(), _lock(), _support(Status.PARTIAL), _support(Status.PARTIAL, generated=1)
    )

    assert reasons == ['`example.com` has fewer lexicons in the package: 2 before, 1 now.']


def test_better_support_and_new_services_are_merged() -> None:
    new = SupportList(
        [*_support().services, ServiceSupport('new.example', Status.PARTIAL, 1, 0, 0, _KINDS, [], [], [])], []
    )

    assert review.find_hold_reasons(_lock(), _lock(), _support(Status.PARTIAL, generated=1), new) == []


def test_section_explains_the_hold() -> None:
    assert review.build_section([]) == ''
    assert review.build_section(['a', 'b']) == '**Held for review, not merged automatically**\n- a\n- b'


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lock_path, support_path = tmp_path / 'lexicons.lock.json', tmp_path / 'supported.json'
    _lock(com_example_a='1').save(lock_path)
    _support().save(support_path)

    def git(*args: str) -> None:
        subprocess.run(['git', *args], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603, S607

    git('init', '--initial-branch=main')
    git('add', '.')
    git('-c', 'user.name=test', '-c', 'user.email=test@example.com', 'commit', '-m', 'base')

    monkeypatch.setattr(review, 'ROOT', tmp_path)
    monkeypatch.setattr(review, 'LOCK_PATH', lock_path)
    monkeypatch.setattr(review, 'SUPPORT_JSON_PATH', support_path)
    monkeypatch.setenv('GITHUB_OUTPUT', str(tmp_path / 'output'))

    return tmp_path


def test_command_compares_the_working_tree_with_the_last_commit(repository: Path) -> None:
    _lock().save(repository / 'lexicons.lock.json')

    result = CliRunner().invoke(cli.app, ['review'])

    assert result.exit_code == 0
    assert 'Held for review' in result.output
    output = (repository / 'output').read_text(encoding='utf-8')
    assert '- 1 lexicon is removed: `com.example.a`.' in output


def test_command_lets_an_unchanged_tree_through(repository: Path) -> None:
    result = CliRunner().invoke(cli.app, ['review'])

    assert result.exit_code == 0
    assert 'Can be merged automatically' in result.output
    name, value, _ = (repository / 'output').read_text(encoding='utf-8').splitlines()
    assert name.startswith('hold<<')
    assert not value
