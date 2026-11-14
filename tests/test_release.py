from datetime import date

import httpx
import pytest
from typer.testing import CliRunner

from atproto_lexicons_tools import cli, release

_TODAY = date(2026, 11, 4)


@pytest.mark.parametrize(
    ('published', 'expected'),
    [
        ([], '2026.11.4'),
        (['2026.11.3', '2026.11.3.1'], '2026.11.4'),
        (['2026.11.4'], '2026.11.4.1'),
        (['2026.11.4', '2026.11.4.1', '2026.11.4.2'], '2026.11.4.3'),
        (['2026.11.4.1'], '2026.11.4'),
    ],
)
def test_next_version_is_the_date_with_a_counter_if_taken(published: list[str], expected: str) -> None:
    assert release.get_next_version(_TODAY, published) == expected


def _client(response: httpx.Response) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda _request: response))


def test_published_versions_are_read_from_pypi() -> None:
    response = httpx.Response(200, json={'releases': {'2026.11.3': [], '2026.11.4': []}})

    assert release.fetch_published_versions('atproto-lexicons', _client(response)) == ['2026.11.3', '2026.11.4']


def test_package_that_was_never_published_has_no_versions() -> None:
    assert release.fetch_published_versions('atproto-lexicons', _client(httpx.Response(404))) == []


def test_pypi_error_is_not_mistaken_for_no_versions() -> None:
    with pytest.raises(httpx.HTTPStatusError):
        release.fetch_published_versions('atproto-lexicons', _client(httpx.Response(503)))


def test_version_command_prints_only_the_version(monkeypatch: pytest.MonkeyPatch) -> None:
    def fetch(_package: str) -> list[str]:
        return []

    monkeypatch.setattr(release, 'fetch_published_versions', fetch)

    result = CliRunner().invoke(cli.app, ['version'])

    assert result.exit_code == 0
    today = cli.datetime.now(cli.timezone.utc).date()
    assert result.output.strip() == f'{today.year}.{today.month}.{today.day}'


def test_version_command_fails_when_pypi_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fetch(_package: str) -> list[str]:
        message = 'no route'
        raise httpx.ConnectError(message)

    monkeypatch.setattr(release, 'fetch_published_versions', fetch)

    result = CliRunner().invoke(cli.app, ['version'])

    assert result.exit_code == 1
    assert 'Could not ask PyPI' in result.output
