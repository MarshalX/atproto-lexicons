import typing as t

import dns.exception
import httpx
import pytest

from atproto_lexicons_tools.core.registry import Service
from atproto_lexicons_tools.fetch.resolver import ResolvedSchema, Resolver, UnreachableError, resolve_external
from tests.helpers import DID, OTHER_DID, PDS, make_lexicon, make_record, make_reference, make_resolver, make_transport

_SERVICE = Service('example.com', (DID,))
_POST = 'com.example.post'


async def _fail_lookup(_name: str) -> list[str]:
    raise dns.exception.Timeout


async def test_service_gets_the_lexicons_its_authority_points_at() -> None:
    repos: dict[str, list[t.Any]] = {
        DID: [
            make_record(DID, _POST, make_lexicon(_POST)),
            # another namespace published in the same repository
            make_record(DID, 'org.other.thing', make_lexicon('org.other.thing')),
            # the authority of this one points elsewhere
            make_record(DID, 'com.example.feed.like', make_lexicon('com.example.feed.like')),
            # stored under a key that is not its id
            make_record(DID, 'com.example.wrong', make_lexicon('com.example.right')),
            # not records at all
            'garbage',
            {'uri': f'at://{DID}/com.atproto.lexicon.schema/com.example.nocid', 'value': make_lexicon(_POST)},
        ]
    }
    client, resolver = make_resolver(repos, {'example.com': DID, 'feed.example.com': OTHER_DID})

    async with client:
        schemas = await resolver.resolve_service(_SERVICE)

    assert schemas == {_POST: ResolvedSchema(make_lexicon(_POST), f'cid-{_POST}', DID)}


async def test_unreachable_repository_is_not_an_empty_one() -> None:
    client, resolver = make_resolver({}, {'example.com': DID})

    async with client:
        with pytest.raises(UnreachableError, match=DID):
            await resolver.resolve_service(_SERVICE)

    assert resolver.errors == [f'{DID}: HTTP 400']


async def test_dns_outage_is_not_a_missing_record() -> None:
    client = httpx.AsyncClient(transport=make_transport({DID: [make_record(DID, _POST, make_lexicon(_POST))]}))
    resolver = Resolver(client, _fail_lookup, retry_delay=0)

    async with client:
        with pytest.raises(UnreachableError, match=r'DNS _lexicon\.example\.com: Timeout'):
            await resolver.resolve_service(_SERVICE)

    assert resolver.errors == ['DNS _lexicon.example.com: Timeout']


async def test_dns_lookup_is_retried() -> None:
    calls: list[str] = []

    async def lookup(name: str) -> list[str]:
        calls.append(name)
        if len(calls) == 1:
            raise dns.exception.Timeout

        return [f'did={DID}']

    async with httpx.AsyncClient(transport=make_transport({})) as client:
        resolver = Resolver(client, lookup, retry_delay=0)

        assert await resolver.get_authority_did(_POST) == DID

    assert calls == ['_lexicon.example.com', '_lexicon.example.com']
    assert resolver.errors == []


def _make_flaky_transport(failures: int, requests: list[httpx.Request]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) <= failures:
            return httpx.Response(503)
        if request.url.host == 'plc.directory':
            return httpx.Response(200, json={'service': [{'id': '#atproto_pds', 'serviceEndpoint': PDS}]})

        return httpx.Response(200, json={'records': []})

    return httpx.MockTransport(handle)


async def test_request_is_retried() -> None:
    requests: list[httpx.Request] = []

    async with httpx.AsyncClient(transport=_make_flaky_transport(3, requests)) as client:
        resolver = Resolver(client, _fail_lookup, retry_delay=0)

        assert await resolver.get_repo_schemas(DID) == {}

    # three failures, then the DID document and the records
    assert len(requests) == 5


async def test_request_is_given_up_after_the_last_attempt() -> None:
    requests: list[httpx.Request] = []

    async with httpx.AsyncClient(transport=_make_flaky_transport(4, requests)) as client:
        resolver = Resolver(client, _fail_lookup, retry_delay=0)

        with pytest.raises(UnreachableError, match='HTTP 503'):
            await resolver.get_repo_schemas(DID)

    assert len(requests) == 4


@pytest.mark.parametrize(
    'response',
    [
        httpx.Response(200, text='<html>'),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={'service': 'none'}),
        httpx.Response(200, json={'service': [{'id': '#atproto_pds', 'serviceEndpoint': 'http://insecure.example'}]}),
    ],
)
async def test_did_document_without_a_pds_is_unreachable(response: httpx.Response) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: response)) as client:
        resolver = Resolver(client, _fail_lookup, retry_delay=0)

        with pytest.raises(UnreachableError):
            await resolver.get_repo_schemas(DID)


async def test_did_web_document_is_read_from_its_host() -> None:
    urls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        resolver = Resolver(client, _fail_lookup, retry_delay=0)

        with pytest.raises(UnreachableError):
            await resolver.get_repo_schemas('did:web:example.com%3A8443')

    assert urls == ['https://example.com:8443/.well-known/did.json']


async def test_external_references_are_resolved_transitively() -> None:
    repos = {
        OTHER_DID: [
            make_record(
                OTHER_DID, 'org.other.thing', make_lexicon('org.other.thing', make_reference('org.other.deep'))
            ),
            make_record(OTHER_DID, 'org.other.deep', make_lexicon('org.other.deep')),
        ]
    }
    client, resolver = make_resolver(repos, {'other.org': OTHER_DID})
    refs = ['org.other.thing', 'org.missing.thing', 'app.bsky.feed.post']
    own = {_POST: ResolvedSchema(make_lexicon(_POST, {'main': {'type': 'union', 'refs': refs}}), 'cid', DID)}

    async with client:
        external, unresolved = await resolve_external(resolver, own, {_POST, 'app.bsky.feed.post'})

    assert sorted(external) == ['org.other.deep', 'org.other.thing']
    assert unresolved == ['org.missing.thing']


async def test_external_lexicon_survives_an_outage_of_its_authority() -> None:
    client, resolver = make_resolver({}, {'other.org': OTHER_DID})
    own = {_POST: ResolvedSchema(make_lexicon(_POST, make_reference('org.other.thing')), 'cid', DID)}
    kept = ResolvedSchema(make_lexicon('org.other.thing', make_reference('org.other.new')), 'old-cid', OTHER_DID)

    async with client:
        external, unresolved = await resolve_external(resolver, own, {_POST}, {'org.other.thing': kept})

    assert external == {'org.other.thing': kept}
    assert unresolved == ['org.other.new']
