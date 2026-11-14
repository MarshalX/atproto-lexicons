import json
import typing as t
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from atproto_lexicons_tools import cli
from atproto_lexicons_tools.build import support
from atproto_lexicons_tools.build.diagnostics import parse_warnings
from atproto_lexicons_tools.core.registry import Service
from atproto_lexicons_tools.site import builder, catalog, github

_KINDS = {'record': 0, 'query': 0, 'procedure': 0, 'subscription': 0}
_SDK_NSIDS = frozenset({'com.example.shipped'})


def _lexicon(nsid: str, main: dict[str, t.Any] | None = None, **extra: t.Any) -> dict[str, t.Any]:
    defs = {'main': main} if main else {'view': {'type': 'object', 'properties': {}}}
    return {'lexicon': 1, 'id': nsid, 'defs': defs, **extra}


_LEXICONS = [
    _lexicon('com.example.post', {'type': 'record', 'description': 'A   post.\nWith a second line.'}),
    _lexicon('com.example.getPosts', {'type': 'query'}, description='Lists posts.'),
    _lexicon('com.example.4000.createThing', {'type': 'procedure'}),
    _lexicon('com.example.defs'),
    _lexicon('com.example.authFull', {'type': 'permission-set'}),
    _lexicon('com.example.broken', {'type': 'space'}),
    _lexicon('com.example.getUnion', {'type': 'query'}),
    _lexicon('com.example.weak', {'type': 'record'}),
    _lexicon('com.example.shipped', {'type': 'record'}),
    _lexicon('com.example.audioSettings', {'type': 'record'}),
    _lexicon('com.example.audio.settings', {'type': 'record'}),
]
_WARNINGS = [
    'Skipped com.example.broken.json: defs.main: Input tag does not match',
    'Skipped method com.example.getUnion: its body is a union, which is not supported yet',
    "Unresolved reference '#nope' in com.example.weak: '#nope' names a definition that is missing.",
]


def _service(tmp_path: Path) -> dict[str, t.Any]:
    directory = tmp_path / 'example.com'
    directory.mkdir()
    for lexicon in _LEXICONS:
        directory.joinpath(f'{lexicon["id"]}.json').write_text(json.dumps(lexicon), encoding='utf-8')

    nsids = {lexicon['id'] for lexicon in _LEXICONS}
    warnings = parse_warnings(_WARNINGS)
    summary = support.classify(Service('example.com', ()), nsids, _SDK_NSIDS, warnings, _KINDS)
    (service,) = catalog.build_services([summary], warnings, {'example.com': '2026-11-13'}, tmp_path, _SDK_NSIDS)

    return service.to_dict()


def _entries(tmp_path: Path) -> dict[str, dict[str, t.Any]]:
    return {lexicon['nsid']: lexicon for lexicon in _service(tmp_path)['lexicons']}


def test_service_carries_its_status_and_the_day_it_changed(tmp_path: Path) -> None:
    service = _service(tmp_path)

    assert (service['domain'], service['status'], service['updated']) == ('example.com', 'partial', '2026-11-13')
    assert len(service['lexicons']) == len(_LEXICONS)


def test_record_is_reached_through_the_client_and_its_model(tmp_path: Path) -> None:
    post = _entries(tmp_path)['com.example.post']

    assert post == {
        'nsid': 'com.example.post',
        'kind': 'record',
        'description': 'A post. With a second line.',
        'state': 'generated',
        'model': 'atproto_lexicons.models.ComExamplePost',
        'client': 'client.com.example.post',
    }


def test_methods_are_snake_cased_and_unsafe_segments_renamed(tmp_path: Path) -> None:
    entries = _entries(tmp_path)

    assert entries['com.example.getPosts']['client'] == 'client.com.example.get_posts()'
    assert entries['com.example.getPosts']['description'] == 'Lists posts.'
    assert entries['com.example.4000.createThing']['client'] == 'client.com.example._4000.create_thing()'


def test_definitions_have_a_model_but_no_client_path(tmp_path: Path) -> None:
    defs = _entries(tmp_path)['com.example.defs']

    assert (defs['kind'], defs['state']) == ('defs', 'generated')
    assert 'client' not in defs


def test_what_was_left_out_is_explained(tmp_path: Path) -> None:
    entries = _entries(tmp_path)

    assert entries['com.example.broken']['state'] == 'skipped'
    assert entries['com.example.broken']['reason'] == 'defs.main: Input tag does not match'
    assert 'model' not in entries['com.example.broken']

    assert entries['com.example.getUnion']['state'] == 'method-skipped'
    assert 'union' in entries['com.example.getUnion']['reason']
    assert 'client' not in entries['com.example.getUnion']
    assert entries['com.example.getUnion']['model'] == 'atproto_lexicons.models.ComExampleGetUnion'

    assert entries['com.example.weak']['state'] == 'untyped'
    assert entries['com.example.weak']['client'] == 'client.com.example.weak'


def test_permission_set_has_an_id_and_no_model(tmp_path: Path) -> None:
    auth = _entries(tmp_path)['com.example.authFull']

    assert auth == {
        'nsid': 'com.example.authFull',
        'kind': 'permission-set',
        'description': '',
        'state': 'generated',
        'id': 'atproto_lexicons.models.ids.ComExampleAuthFull',
    }


def test_lexicon_of_the_sdk_points_at_the_sdk(tmp_path: Path) -> None:
    shipped = _entries(tmp_path)['com.example.shipped']

    assert shipped['state'] == 'sdk'
    assert shipped['model'] == 'atproto.models.ComExampleShipped'


def test_colliding_aliases_match_the_generated_package(tmp_path: Path) -> None:
    entries = _entries(tmp_path)

    assert entries['com.example.audioSettings']['model'] == 'atproto_lexicons.models.ComExampleAudioSettings'
    assert entries['com.example.audio.settings']['model'] == 'atproto_lexicons.models.Com_Example_Audio_Settings'


def test_long_descriptions_are_cut() -> None:
    lexicon = _lexicon('com.example.long', {'type': 'record', 'description': 'word ' * 200})

    description = catalog.get_description(lexicon)

    assert len(description) <= 220
    assert description.endswith('…')


def test_website_is_written_with_its_domain(tmp_path: Path) -> None:
    result = builder.run(tmp_path / 'site')

    assert result.directory.joinpath('index.html').is_file()
    assert result.directory.joinpath('CNAME').read_text(encoding='utf-8') == 'lex.atproto.blue\n'
    assert result.directory.joinpath('.nojekyll').is_file()

    catalog = json.loads(result.directory.joinpath('catalog.json').read_text(encoding='utf-8'))
    assert len(catalog['services']) == result.services
    assert catalog['generated'].endswith('+00:00')
    assert 'sdk_stars' not in catalog


def test_page_states_how_much_the_catalog_holds(tmp_path: Path) -> None:
    result = builder.run(tmp_path / 'site')

    page = result.directory.joinpath('index.html').read_text(encoding='utf-8')

    assert f'{result.lexicons:,} lexicons from {result.services:,} services' in page
    assert '{{' not in page


def test_website_carries_the_stars_of_the_sdk(tmp_path: Path) -> None:
    result = builder.run(tmp_path / 'site', sdk_stars=1234)

    assert json.loads(result.directory.joinpath('catalog.json').read_text(encoding='utf-8'))['sdk_stars'] == 1234


def _github(response: httpx.Response, seen: list[httpx.Request]) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_stars_are_read_from_github_with_the_token() -> None:
    seen: list[httpx.Request] = []
    client = _github(httpx.Response(200, json={'stargazers_count': 1234}), seen)

    assert github.fetch_stars('MarshalX/atproto', 'secret', client) == 1234
    assert str(seen[0].url) == 'https://api.github.com/repos/MarshalX/atproto'
    assert seen[0].headers['Authorization'] == 'Bearer secret'


def test_stars_are_asked_for_anonymously_without_a_token() -> None:
    seen: list[httpx.Request] = []

    github.fetch_stars('MarshalX/atproto', client=_github(httpx.Response(200, json={'stargazers_count': 1}), seen))

    assert 'Authorization' not in seen[0].headers


def test_refusal_of_github_is_an_error() -> None:
    with pytest.raises(httpx.HTTPStatusError):
        github.fetch_stars('MarshalX/atproto', client=_github(httpx.Response(403), []))


def test_site_command_builds_without_the_stars_when_github_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fetch(_repository: str, _token: str) -> int:
        message = 'no route'
        raise httpx.ConnectError(message)

    built: list[int | None] = []

    def run(sdk_stars: int | None = None) -> builder.SiteResult:
        built.append(sdk_stars)
        return builder.SiteResult(Path('site'), 0, 0)

    monkeypatch.setattr(github, 'fetch_stars', fetch)
    monkeypatch.setattr(builder, 'run', run)

    result = CliRunner().invoke(cli.app, ['site'])

    assert result.exit_code == 0
    assert built == [None]
    assert 'could not ask GitHub' in result.output
