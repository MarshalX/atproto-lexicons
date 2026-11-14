import json
import re
import typing as t
from pathlib import Path

from atproto_lexicons_tools.paths import SERVICES_PATH

DID_RE = re.compile(r'^did:(plc:[a-z2-7]{24}|web:[a-zA-Z0-9.%-]+)$')


SERVICES_KEY = 'services'
DOMAIN_KEY = 'domain'
DIDS_KEY = 'dids'


class Service(t.NamedTuple):
    domain: str
    dids: tuple[str, ...]

    @property
    def nsid_prefix(self) -> str:
        return '.'.join(reversed(self.domain.split('.'))) + '.'

    @property
    def probe_nsid(self) -> str:
        """An NSID right under the prefix: its authority is the domain of the service itself."""
        return f'{self.nsid_prefix}x'

    def owns(self, nsid: str) -> bool:
        return nsid.startswith(self.nsid_prefix)


def parse_services(data: t.Any) -> list[Service]:
    services = [Service(entry[DOMAIN_KEY], tuple(entry.get(DIDS_KEY, ()))) for entry in data[SERVICES_KEY]]

    domains = [service.domain for service in services]
    duplicates = sorted({domain for domain in domains if domains.count(domain) > 1})
    if duplicates:
        message = f'Services listed more than once: {", ".join(duplicates)}'
        raise ValueError(message)

    return services


def load_services(path: Path = SERVICES_PATH) -> list[Service]:
    return parse_services(json.loads(path.read_text(encoding='utf-8')))


def dump_services(services: t.Iterable[Service]) -> str:
    """Write the registry the one way it is committed: services by domain, their repositories sorted."""
    entries = [
        {DOMAIN_KEY: service.domain, DIDS_KEY: sorted(set(service.dids))}
        for service in sorted(services, key=lambda service: service.domain)
    ]

    return json.dumps({SERVICES_KEY: entries}, indent=2) + '\n'


def find_owner(nsid: str, services: t.Iterable[Service]) -> Service | None:
    owners = [service for service in services if service.owns(nsid)]
    return max(owners, key=lambda service: len(service.nsid_prefix), default=None)
