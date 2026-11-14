import typing as t

import httpx

from atproto_lexicons_tools.fetch.resolver import Resolver, TxtLookup

DID = 'did:plc:aaaaaaaaaaaaaaaaaaaaaaaa'
OTHER_DID = 'did:plc:bbbbbbbbbbbbbbbbbbbbbbbb'
PDS = 'https://pds.example.com'

Records = list[dict[str, t.Any]]


def make_lexicon(nsid: str, defs: dict[str, t.Any] | None = None) -> dict[str, t.Any]:
    return {'lexicon': 1, 'id': nsid, 'defs': defs or {'main': {'type': 'token'}}}


def make_reference(nsid: str) -> dict[str, t.Any]:
    return {'main': {'type': 'object', 'properties': {'x': {'type': 'ref', 'ref': nsid}}}}


def make_record(did: str, nsid: str, value: dict[str, t.Any]) -> dict[str, t.Any]:
    return {'uri': f'at://{did}/com.atproto.lexicon.schema/{nsid}', 'cid': f'cid-{nsid}', 'value': value}


def make_transport(repos: dict[str, Records]) -> httpx.MockTransport:
    """Serve the repositories from one PDS; a repository that is not listed cannot be reached."""

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == 'plc.directory':
            service = {'id': '#atproto_pds', 'serviceEndpoint': PDS}
            return httpx.Response(200, json={'service': [service]})

        did = request.url.params['repo']
        if did not in repos:
            return httpx.Response(400, json={'error': 'RepoNotFound'})

        return httpx.Response(200, json={'records': repos[did]})

    return httpx.MockTransport(handle)


def make_txt_lookup(authorities: dict[str, str]) -> TxtLookup:
    async def lookup_txt(name: str) -> list[str]:
        did = authorities.get(name.removeprefix('_lexicon.'))
        return [f'did={did}'] if did else []

    return lookup_txt


def make_resolver(repos: dict[str, Records], authorities: dict[str, str]) -> tuple[httpx.AsyncClient, Resolver]:
    client = httpx.AsyncClient(transport=make_transport(repos))

    return client, Resolver(client, make_txt_lookup(authorities), retry_delay=0)
