import asyncio
import dataclasses
import typing as t
from datetime import datetime, timezone

import httpx

from atproto_lexicons_tools.core.lock import Changes, Entries, Lock, date_changes, diff_locks
from atproto_lexicons_tools.core.registry import Service, find_owner, load_services
from atproto_lexicons_tools.core.sdk import get_sdk_nsids
from atproto_lexicons_tools.fetch.report import write_github_outputs
from atproto_lexicons_tools.fetch.resolver import Resolver, Schemas, UnreachableError, resolve_external
from atproto_lexicons_tools.fetch.storage import (
    describe_oversized,
    read_schemas,
    remove_stale_directories,
    write_schemas,
)
from atproto_lexicons_tools.paths import EXTERNAL_DIR_NAME, LEXICONS_DIR, LOCK_PATH

_USER_AGENT = 'atproto-lexicons'
_TIMEOUT_SECONDS = 30


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, headers={'User-Agent': _USER_AGENT}, follow_redirects=True)


async def fetch(services: list[Service], old_lock: Lock) -> tuple[Lock, list[str]]:
    """Download the lexicons of the services and everything they refer to.

    Returns:
        The new lock, without the dates, and what went wrong on the way.
    """
    external_dir = LEXICONS_DIR.joinpath(EXTERNAL_DIR_NAME)

    async with _make_client() as client:
        resolver = Resolver(client)
        results = await asyncio.gather(
            *(resolver.resolve_service(service) for service in services), return_exceptions=True
        )

        locked: dict[str, Entries] = {}
        unreachable: list[str] = []
        oversized: list[str] = []
        current: Schemas = {}

        for service, result in zip(services, results, strict=True):
            directory = LEXICONS_DIR.joinpath(service.domain)

            if isinstance(result, UnreachableError):
                # an outage must not drop the service from the package, nor what its lexicons refer to
                locked[service.domain] = old_lock.services.get(service.domain, {})
                unreachable.append(service.domain)
                current.update(read_schemas(directory, locked[service.domain]))
            elif isinstance(result, BaseException):
                raise result
            else:
                locked[service.domain], too_large = write_schemas(directory, result)
                oversized.extend(too_large)
                current.update(result)

        known = set(current) | get_sdk_nsids()
        known.update(nsid for entries in locked.values() for nsid in entries)

        previous = read_schemas(external_dir, old_lock.external)
        external, unresolved = await resolve_external(resolver, current, known, previous)

    # an external lexicon may belong to a service that joined the registry since
    external = {nsid: schema for nsid, schema in external.items() if find_owner(nsid, services) is None}
    external_entries, too_large = write_schemas(external_dir, external)
    oversized.extend(too_large)

    remove_stale_directories(LEXICONS_DIR, services)

    lock = Lock(services=locked, external=external_entries, unresolved=unresolved, unreachable=unreachable)
    return lock, sorted({*resolver.errors, *describe_oversized(oversized)})


class FetchResult(t.NamedTuple):
    lock: Lock
    changes: Changes
    errors: list[str]


def run(services: list[Service] | None = None) -> FetchResult:
    services = load_services() if services is None else services
    old_lock = Lock.load(LOCK_PATH)
    LEXICONS_DIR.mkdir(exist_ok=True)

    lock, errors = asyncio.run(fetch(services, old_lock))

    today = datetime.now(timezone.utc).date().isoformat()
    lock = dataclasses.replace(lock, updated=date_changes(old_lock, lock.services, today))
    lock.save(LOCK_PATH)

    changes = diff_locks(old_lock, lock)
    write_github_outputs(changes, lock.unreachable, errors)

    return FetchResult(lock, changes, errors)


async def find_dids(nsids: t.Iterable[str]) -> list[str]:
    """Find the repositories the authorities of the NSIDs publish in.

    Raises:
        UnreachableError: DNS did not answer for one of them.
    """
    async with _make_client() as client:
        resolver = Resolver(client)
        results = await asyncio.gather(*(resolver.get_authority_did(nsid) for nsid in nsids), return_exceptions=True)

    for result in results:
        if isinstance(result, BaseException):
            raise result

    return sorted({did for did in results if isinstance(did, str)})
