import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from atproto_lexicons_tools import cli
from atproto_lexicons_tools.build import support, verify
from atproto_lexicons_tools.core.lock import Changes, Lock, LockEntry
from atproto_lexicons_tools.core.registry import Service
from atproto_lexicons_tools.fetch import fetcher
from atproto_lexicons_tools.fetch.resolver import UnreachableError

runner = CliRunner()

_DID = 'did:plc:aaaaaaaaaaaaaaaaaaaaaaaa'
_KINDS = {'record': 1, 'query': 0, 'procedure': 0, 'subscription': 0}


def _support(domain: str, status: str, **overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        'domain': domain,
        'status': status,
        'lexicons': 3,
        'generated': 3,
        'provided_by_sdk': 0,
        'kinds': _KINDS,
        'skipped_lexicons': [],
        'skipped_methods': [],
        'weakened_lexicons': [],
    }
    return {**fields, **overrides}


@pytest.fixture
def support_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / 'supported.json'
    services = [
        _support('example.com', support.Status.FULL.value),
        _support('teal.fm', support.Status.PARTIAL.value, generated=2, skipped_lexicons=['fm.teal.broken']),
    ]
    path.write_text(json.dumps({'services': services, 'warnings': []}), encoding='utf-8')
    monkeypatch.setattr(cli, 'SUPPORT_JSON_PATH', path)
    return path


@pytest.fixture
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / 'services.json'
    path.write_text(json.dumps({'services': [{'domain': 'teal.fm', 'dids': [_DID]}]}), encoding='utf-8')
    monkeypatch.setattr(cli, 'SERVICES_PATH', path)
    monkeypatch.setattr(cli, 'load_services', lambda: [Service('teal.fm', (_DID,))])
    return path


def test_no_arguments_shows_the_commands() -> None:
    result = runner.invoke(cli.app, [])

    for command in ('fetch', 'build', 'verify', 'lint', 'add', 'status'):
        assert command in result.output


def test_lint_passes_on_a_clean_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_lint(*_args: object, **_kwargs: object) -> list[str]:
        return []

    monkeypatch.setattr(cli.lint_tool, 'lint', fake_lint)

    result = runner.invoke(cli.app, ['lint'])

    assert result.exit_code == 0
    assert 'All good.' in result.output


def test_lint_lists_the_problems_and_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_lint(*_args: object, fix: bool) -> list[str]:
        calls.append(fix)
        return ['services must be sorted by domain', 'teal.fm: listed more than once']

    monkeypatch.setattr(cli.lint_tool, 'lint', fake_lint)

    result = runner.invoke(cli.app, ['lint', '--fix'])

    assert result.exit_code == 1
    assert calls == [True]
    assert 'services must be sorted by domain' in result.output
    assert '2 problems found.' in result.output


@pytest.mark.usefixtures('support_list')
def test_status_lists_the_services() -> None:
    result = runner.invoke(cli.app, ['status'])

    assert result.exit_code == 0
    assert 'example.com' in result.output
    assert 'teal.fm' in result.output
    assert '2 of 3' in result.output
    assert '2 services: 1 full, 1 partial, 0 not supported.' in result.output


@pytest.mark.usefixtures('support_list')
def test_status_filters_by_status() -> None:
    result = runner.invoke(cli.app, ['status', '--only', 'partial'])

    assert 'teal.fm' in result.output
    assert 'example.com' not in result.output


@pytest.mark.usefixtures('support_list')
def test_status_shows_what_a_service_is_missing() -> None:
    result = runner.invoke(cli.app, ['status', 'teal.fm'])

    assert result.exit_code == 0
    assert 'Partial' in result.output
    assert 'fm.teal.broken' in result.output


@pytest.mark.usefixtures('support_list')
@pytest.mark.parametrize(
    ('args', 'expected'),
    [
        (['status', 'missing.dev'], 'is not in the support list'),
        (['status', '--only', 'broken'], 'Unknown status'),
    ],
)
def test_status_rejects_unknown_input(args: list[str], expected: str) -> None:
    result = runner.invoke(cli.app, args)

    assert result.exit_code == 1
    assert expected in result.output


def test_status_needs_a_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, 'SUPPORT_JSON_PATH', tmp_path / 'supported.json')

    result = runner.invoke(cli.app, ['status'])

    assert result.exit_code == 1
    assert 'lex build' in result.output


@pytest.mark.parametrize(
    ('args', 'expected'),
    [
        (['add', 'Teal.FM'], 'is not a lowercase domain name'),
        (['add', 'bsky.app'], 'is not a lowercase domain name'),
        (['add', 'teal.fm'], 'is in the registry already'),
        (['add', 'example.com', '--nsid', 'org.other.thing'], 'is not under com.example.*'),
    ],
)
def test_add_rejects_bad_input(registry: Path, args: list[str], expected: str) -> None:
    before = registry.read_text(encoding='utf-8')

    result = runner.invoke(cli.app, args)

    assert result.exit_code == 1
    assert expected in ' '.join(result.output.split())
    assert registry.read_text(encoding='utf-8') == before


@pytest.mark.usefixtures('registry')
def test_add_explains_a_missing_dns_record(monkeypatch: pytest.MonkeyPatch) -> None:
    async def find_no_dids(_nsids: object) -> list[str]:
        return []

    monkeypatch.setattr(cli.fetch_tool, 'find_dids', find_no_dids)

    result = runner.invoke(cli.app, ['add', 'example.com'])

    assert result.exit_code == 1
    assert '--nsid com.example.' in ' '.join(result.output.split())


@pytest.mark.usefixtures('registry')
def test_add_does_not_take_a_dns_outage_for_a_missing_record(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(_nsids: object) -> list[str]:
        message = 'DNS _lexicon.example.com: Timeout'
        raise UnreachableError(message)

    monkeypatch.setattr(cli.fetch_tool, 'find_dids', fail)

    result = runner.invoke(cli.app, ['add', 'example.com'])

    assert result.exit_code == 1
    assert 'try again' in result.output
    assert '--nsid' not in result.output


def test_add_registers_the_service_and_fetches(registry: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[list[str]] = []

    async def find_dids(nsids: list[str]) -> list[str]:
        asked.append(list(nsids))
        return [_DID]

    lock = Lock(services={'example.com': {'com.example.post': LockEntry(_DID, 'c')}})
    changes = Changes(added=['com.example.post'], changed=[], removed=[])
    monkeypatch.setattr(cli.fetch_tool, 'find_dids', find_dids)

    def run(_services: list[Service]) -> fetcher.FetchResult:
        return fetcher.FetchResult(lock, changes, [])

    monkeypatch.setattr(cli.fetch_tool, 'run', run)

    result = runner.invoke(cli.app, ['add', 'example.com', '--nsid', 'com.example.feed.post'])

    assert result.exit_code == 0, result.output
    assert asked == [['com.example.x', 'com.example.feed.post']]
    assert json.loads(registry.read_text(encoding='utf-8')) == {
        'services': [{'domain': 'example.com', 'dids': [_DID]}, {'domain': 'teal.fm', 'dids': [_DID]}]
    }
    assert '+ com.example.post' in result.output
    assert 'lex build' in result.output


def test_verify_reports_the_size_of_the_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verify, 'run_isolated', lambda: verify.VerifyResult(files=10, models=20))

    result = runner.invoke(cli.app, ['verify'])

    assert result.exit_code == 0
    assert 'Verified 10 files, 20 models.' in result.output


def test_verify_shows_why_the_package_does_not_load(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> verify.VerifyResult:
        raise subprocess.CalledProcessError(1, ['python'], stderr='RuntimeError: Model X is not fully defined\n')

    monkeypatch.setattr(verify, 'run_isolated', fail)

    result = runner.invoke(cli.app, ['verify'])

    assert result.exit_code == 1
    assert 'Model X is not fully defined' in result.output
    assert 'does not load' in result.output
