import asyncio
import typing as t
from urllib.parse import unquote

import dns.asyncresolver
import dns.exception
import dns.resolver
import httpx
from dns.rdtypes.txtbase import TXTBase

from atproto_lexicons_tools.core.lexicon import Document, find_referenced_nsids, get_authority, is_lexicon
from atproto_lexicons_tools.core.registry import DID_RE, Service

_PLC_URL = 'https://plc.directory'
_DID_WEB_PREFIX = 'did:web:'
_DID_WEB_DOCUMENT_PATH = '/.well-known/did.json'
_PDS_SERVICE_ID = '#atproto_pds'
_PDS_SCHEME = 'https://'

_AUTHORITY_RECORD_PREFIX = '_lexicon.'
_DID_TXT_PREFIX = 'did='
_NAMESERVERS = ('1.1.1.1', '8.8.8.8')
_DNS_LIFETIME_SECONDS = 8

_SCHEMA_COLLECTION = 'com.atproto.lexicon.schema'
_LIST_RECORDS_METHOD = 'com.atproto.repo.listRecords'
_PAGE_SIZE = 100
_MAX_RECORDS_PER_REPO = 3000
_MAX_DEPENDENCY_DEPTH = 6

_CONCURRENCY = 12
_ATTEMPTS = 4
_RETRY_DELAY_SECONDS = 1.5
# asking again does not change these answers
_FINAL_STATUSES = frozenset({httpx.codes.BAD_REQUEST, httpx.codes.NOT_FOUND})

TxtLookup = t.Callable[[str], t.Awaitable[list[str]]]


class ResolvedSchema(t.NamedTuple):
    value: Document
    cid: str
    did: str


Schemas = dict[str, ResolvedSchema]


class UnreachableError(Exception):
    """An answer could not be obtained, which is not the same as the answer being "nothing"."""


def _make_txt_lookup() -> TxtLookup:
    resolver = dns.asyncresolver.Resolver()
    resolver.nameservers = list(_NAMESERVERS)
    resolver.lifetime = _DNS_LIFETIME_SECONDS

    async def lookup(name: str) -> list[str]:
        try:
            answer = await resolver.resolve(name, 'TXT')
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return []

        records = (rdata for rdata in answer if isinstance(rdata, TXTBase))
        return [b''.join(rdata.strings).decode('utf-8', 'replace').strip() for rdata in records]

    return lookup


def _parse_record(record: t.Any, did: str) -> tuple[str, ResolvedSchema] | None:
    if not isinstance(record, dict):
        return None

    fields = t.cast('dict[str, t.Any]', record)
    nsid = str(fields.get('uri', '')).rsplit('/', 1)[-1]
    value, cid = fields.get('value'), fields.get('cid')
    if not is_lexicon(nsid, value) or not isinstance(cid, str):
        return None

    return nsid, ResolvedSchema(value=t.cast('Document', value), cid=cid, did=did)


def _find_pds(did_doc: t.Any) -> str | None:
    services = t.cast('dict[str, t.Any]', did_doc).get('service') if isinstance(did_doc, dict) else None
    if not isinstance(services, list):
        return None

    for service in t.cast('list[t.Any]', services):
        if not isinstance(service, dict):
            continue

        fields = t.cast('dict[str, t.Any]', service)
        endpoint = str(fields.get('serviceEndpoint', ''))
        if str(fields.get('id', '')).endswith(_PDS_SERVICE_ID) and endpoint.startswith(_PDS_SCHEME):
            return endpoint.rstrip('/')

    return None


class Resolver:
    def __init__(
        self,
        client: httpx.AsyncClient,
        lookup_txt: TxtLookup | None = None,
        retry_delay: float = _RETRY_DELAY_SECONDS,
    ) -> None:
        self._client = client
        self._lookup_txt = lookup_txt or _make_txt_lookup()
        self._retry_delay = retry_delay

        self._limit = asyncio.Semaphore(_CONCURRENCY)
        self._authorities: dict[str, asyncio.Future[str | None]] = {}
        self._repos: dict[str, asyncio.Future[Schemas]] = {}

        self.errors: list[str] = []

    async def _back_off(self, attempt: int) -> None:
        await asyncio.sleep(self._retry_delay * attempt)

    async def _get_json(self, url: str, **kwargs: t.Any) -> t.Any:
        reason = 'no attempts'
        for attempt in range(_ATTEMPTS):
            if attempt:
                await self._back_off(attempt)

            try:
                response = await self._client.get(url, **kwargs)
            except httpx.HTTPError as e:
                reason = f'{type(e).__name__} {e}'.strip()
                continue

            if response.status_code == httpx.codes.OK:
                try:
                    return response.json()
                except (ValueError, RecursionError):
                    reason = 'the response is not JSON'
                    continue

            reason = f'HTTP {response.status_code}'
            if response.status_code in _FINAL_STATUSES:
                break

        raise UnreachableError(reason)

    async def _lookup_txt_with_retries(self, name: str) -> list[str]:
        reason = 'no attempts'
        for attempt in range(_ATTEMPTS):
            if attempt:
                await self._back_off(attempt)

            try:
                return await self._lookup_txt(name)
            except (dns.exception.DNSException, OSError) as e:
                reason = type(e).__name__

        message = f'DNS {name}: {reason}'
        self.errors.append(message)
        raise UnreachableError(message)

    def get_authority_did(self, nsid: str) -> asyncio.Future[str | None]:
        """Find the repository the authority of the NSID publishes in, if it names one.

        Raises:
            UnreachableError: When awaited, if DNS did not answer.
        """
        domain = get_authority(nsid)
        if domain not in self._authorities:
            self._authorities[domain] = asyncio.ensure_future(self._resolve_authority(domain))

        return self._authorities[domain]

    async def _resolve_authority(self, domain: str) -> str | None:
        async with self._limit:
            values = await self._lookup_txt_with_retries(f'{_AUTHORITY_RECORD_PREFIX}{domain}')

        dids = [value[len(_DID_TXT_PREFIX) :] for value in values if value.startswith(_DID_TXT_PREFIX)]
        return next((did for did in dids if DID_RE.match(did)), None)

    def get_repo_schemas(self, did: str) -> asyncio.Future[Schemas]:
        """List the lexicons a repository publishes.

        Raises:
            UnreachableError: When awaited, if the repository could not be listed.
        """
        if did not in self._repos:
            self._repos[did] = asyncio.ensure_future(self._list_schemas(did))

        return self._repos[did]

    async def _resolve_pds(self, did: str) -> str:
        if did.startswith(_DID_WEB_PREFIX):
            # a port is percent-encoded in the identifier
            url = f'https://{unquote(did[len(_DID_WEB_PREFIX) :])}{_DID_WEB_DOCUMENT_PATH}'
        else:
            url = f'{_PLC_URL}/{did}'

        pds = _find_pds(await self._get_json(url))
        if pds is None:
            message = 'no PDS in the DID document'
            raise UnreachableError(message)

        return pds

    async def _read_schema_records(self, pds: str, did: str) -> Schemas:
        schemas: Schemas = {}
        cursor = None

        while len(schemas) < _MAX_RECORDS_PER_REPO:
            params: dict[str, str | int] = {'repo': did, 'collection': _SCHEMA_COLLECTION, 'limit': _PAGE_SIZE}
            if cursor:
                params['cursor'] = cursor

            page = await self._get_json(f'{pds}/xrpc/{_LIST_RECORDS_METHOD}', params=params)
            records = t.cast('dict[str, t.Any]', page).get('records') if isinstance(page, dict) else None
            if not isinstance(records, list):
                message = 'the PDS did not return a list of records'
                raise UnreachableError(message)

            schemas.update(filter(None, (_parse_record(record, did) for record in t.cast('list[t.Any]', records))))

            cursor = t.cast('dict[str, t.Any]', page).get('cursor')
            if not isinstance(cursor, str) or not cursor or not records:
                break

        return schemas

    async def _list_schemas(self, did: str) -> Schemas:
        async with self._limit:
            try:
                pds = await self._resolve_pds(did)
                return await self._read_schema_records(pds, did)
            except UnreachableError as e:
                message = f'{did}: {e}'
                self.errors.append(message)
                raise UnreachableError(message) from e

    async def _is_authority(self, did: str, nsid: str) -> bool:
        return await self.get_authority_did(nsid) == did

    async def resolve(self, nsid: str) -> ResolvedSchema | None:
        """Find one lexicon by its NSID.

        Raises:
            UnreachableError: DNS or the repository of the authority did not answer.
        """
        did = await self.get_authority_did(nsid)
        if not did:
            return None

        return (await self.get_repo_schemas(did)).get(nsid)

    async def resolve_service(self, service: Service) -> Schemas:
        """Collect the lexicons of a service from every repository it publishes in.

        Raises:
            UnreachableError: DNS or one of the repositories did not answer, so the result would be incomplete.
        """
        dids = set(service.dids)
        own_did = await self.get_authority_did(service.probe_nsid)
        if own_did:
            dids.add(own_did)

        schemas: Schemas = {}
        for did in sorted(dids):
            repo = await self.get_repo_schemas(did)

            for nsid, schema in repo.items():
                if service.owns(nsid) and await self._is_authority(did, nsid):
                    schemas[nsid] = schema

        return schemas


async def _resolve_dependency(resolver: Resolver, nsid: str, previous: Schemas) -> ResolvedSchema | None:
    try:
        return await resolver.resolve(nsid)
    except UnreachableError:
        # an outage must not drop a lexicon that was fetched before
        return previous.get(nsid)


async def resolve_external(
    resolver: Resolver, schemas: Schemas, known: t.AbstractSet[str], previous: Schemas | None = None
) -> tuple[Schemas, list[str]]:
    """Follow the references of the schemas to the lexicons of other authorities, and theirs in turn.

    Args:
        resolver: Where to look the lexicons up.
        schemas: The lexicons whose references are followed.
        known: The NSIDs that need no lookup.
        previous: The external lexicons of the last fetch, to fall back on while their authority is down.

    Returns:
        The external lexicons that were found, and the NSIDs that were not.
    """
    external: Schemas = {}
    unresolved: set[str] = set()
    frontier = schemas

    for _ in range(_MAX_DEPENDENCY_DEPTH):
        wanted: set[str] = set()
        for nsid, schema in frontier.items():
            wanted |= find_referenced_nsids(schema.value, nsid)

        wanted -= known | set(external) | unresolved
        if not wanted:
            break

        ordered = sorted(wanted)
        found = await asyncio.gather(*(_resolve_dependency(resolver, nsid, previous or {}) for nsid in ordered))

        frontier = {}
        for nsid, schema in zip(ordered, found, strict=True):
            if schema:
                external[nsid] = frontier[nsid] = schema
            else:
                unresolved.add(nsid)

    return external, sorted(unresolved)
