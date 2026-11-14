import json
import re
import typing as t
from pathlib import Path

from atproto_lexicons_tools.core.lock import Entries, Lock
from atproto_lexicons_tools.core.registry import (
    DID_RE,
    DIDS_KEY,
    DOMAIN_KEY,
    SERVICES_KEY,
    Service,
    dump_services,
    parse_services,
)
from atproto_lexicons_tools.paths import EXTERNAL_DIR_NAME

_DOMAIN_RE = re.compile(r'^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]([a-z0-9-]{0,61}[a-z0-9])?$')
_SDK_DOMAINS = frozenset({'atproto.com', 'bsky.app', 'bsky.chat', 'bsky.internal', 'bsky.network', 'ozone.tools'})
_ENTRY_KEYS = frozenset({DOMAIN_KEY, DIDS_KEY})


class Problem(t.NamedTuple):
    message: str
    fixable: bool = False


def _is_string_list(value: t.Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in t.cast('list[t.Any]', value))


def is_domain(value: str) -> bool:
    return bool(_DOMAIN_RE.match(value)) and value not in _SDK_DOMAINS


def _check_dids(where: str, dids: t.Any) -> list[Problem]:
    if not _is_string_list(dids):
        return [Problem(f'{where}: "{DIDS_KEY}" must be a list of strings')]

    problems = [Problem(f'{where}: "{did}" is not a did:plc or did:web') for did in dids if not DID_RE.match(did)]
    if len(set(dids)) != len(dids):
        problems.append(Problem(f'{where}: "{DIDS_KEY}" has duplicates', fixable=True))
    elif dids != sorted(dids):
        problems.append(Problem(f'{where}: "{DIDS_KEY}" must be sorted', fixable=True))

    return problems


def _check_entry(index: int, entry: t.Any) -> list[Problem]:
    where = f'{SERVICES_KEY}[{index}]'
    if not isinstance(entry, dict):
        return [Problem(f'{where}: must be an object')]

    fields = t.cast('dict[str, t.Any]', entry)
    domain = fields.get(DOMAIN_KEY)
    if not isinstance(domain, str):
        return [Problem(f'{where}: "{DOMAIN_KEY}" is required and must be a string')]

    where = f'{where} ({domain})'
    problems = [Problem(f'{where}: unknown key "{key}"') for key in sorted(set(fields) - _ENTRY_KEYS)]

    if not _DOMAIN_RE.match(domain):
        problems.append(Problem(f'{where}: not a lowercase domain name'))
    if domain in _SDK_DOMAINS:
        problems.append(Problem(f'{where}: the SDK ships the lexicons of this domain'))

    return [*problems, *_check_dids(where, fields.get(DIDS_KEY, []))]


def _check_domains(domains: list[str]) -> list[Problem]:
    unique = sorted(set(domains))
    problems = [Problem(f'{domain}: listed more than once') for domain in unique if domains.count(domain) > 1]

    if domains != sorted(domains):
        problems.append(Problem(f'{SERVICES_KEY} must be sorted by domain', fixable=True))

    # one service would claim the lexicons of the other
    problems.extend(
        Problem(f'{inner}: is inside {outer}, list only one of them')
        for outer in unique
        for inner in unique
        if inner.endswith(f'.{outer}')
    )

    return problems


def _get_domain(entry: t.Any) -> str | None:
    domain = t.cast('dict[str, t.Any]', entry).get(DOMAIN_KEY) if isinstance(entry, dict) else None

    return domain if isinstance(domain, str) else None


def check_registry(data: t.Any) -> list[Problem]:
    if not isinstance(data, dict) or set(t.cast('dict[str, t.Any]', data)) != {SERVICES_KEY}:
        return [Problem(f'the file must be an object with the single key "{SERVICES_KEY}"')]

    entries = t.cast('dict[str, t.Any]', data)[SERVICES_KEY]
    if not isinstance(entries, list):
        return [Problem(f'"{SERVICES_KEY}" must be a list')]

    problems: list[Problem] = []
    for index, entry in enumerate(t.cast('list[t.Any]', entries)):
        problems.extend(_check_entry(index, entry))

    domains = [domain for domain in map(_get_domain, t.cast('list[t.Any]', entries)) if domain is not None]

    return [*problems, *_check_domains(domains)]


def format_registry(data: t.Any) -> str:
    """Write a registry the way it is committed. It must have nothing but fixable problems."""
    return dump_services(parse_services(data))


def _check_lexicon_file(path: Path, service: Service | None) -> list[str]:
    where = f'{path.parent.name}/{path.name}'
    try:
        lexicon = json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return [f'{where}: not valid JSON']

    if not isinstance(lexicon, dict) or t.cast('dict[str, t.Any]', lexicon).get('id') != path.stem:
        return [f'{where}: the "id" of the lexicon must match the file name']
    if service is not None and not service.owns(path.stem):
        return [f'{where}: does not belong to {service.domain}']

    return []


def _find_directories(lexicons_dir: Path) -> dict[str, Path]:
    if not lexicons_dir.is_dir():
        return {}

    return {path.name: path for path in lexicons_dir.iterdir() if path.is_dir()}


def check_lexicons(services: list[Service], lock: Lock, lexicons_dir: Path) -> list[str]:
    by_domain = {service.domain: service for service in services}
    locked: dict[str, Entries] = dict(lock.services)

    problems = [f'{domain}: not fetched yet, run `lex fetch`' for domain in sorted(set(by_domain) - set(locked))]
    problems.extend(f'{domain}: in the lock but not in the registry' for domain in sorted(set(locked) - set(by_domain)))

    locked[EXTERNAL_DIR_NAME] = lock.external
    directories = _find_directories(lexicons_dir)
    problems.extend(
        f'lexicons/{name}: no such service in the registry' for name in sorted(set(directories) - set(locked))
    )

    for name, entries in sorted(locked.items()):
        paths = sorted(directories[name].glob('*.json')) if name in directories else []
        on_disk = {path.stem for path in paths}

        problems.extend(f'{name}/{nsid}.json: in the lock but missing' for nsid in sorted(set(entries) - on_disk))
        problems.extend(f'{name}/{nsid}.json: not in the lock' for nsid in sorted(on_disk - set(entries)))

        for path in paths:
            problems.extend(_check_lexicon_file(path, by_domain.get(name)))

    return problems


def lint(services_path: Path, lock_path: Path, lexicons_dir: Path, *, fix: bool) -> list[str]:
    try:
        text = services_path.read_text(encoding='utf-8')
        data = json.loads(text)
    except ValueError as e:
        return [f'{services_path.name}: not valid JSON: {e}']

    problems = check_registry(data)
    if fix and all(problem.fixable for problem in problems):
        text = format_registry(data)
        services_path.write_text(text, encoding='utf-8')
        data = json.loads(text)
        problems = check_registry(data)

    if problems:
        return [problem.message for problem in problems]
    if text != format_registry(data):
        return [f'{services_path.name}: not formatted, run `lex lint --fix`']

    try:
        lock = Lock.load(lock_path)
    except ValueError as e:
        return [f'{lock_path.name}: {e}']

    return check_lexicons(parse_services(data), lock, lexicons_dir)
