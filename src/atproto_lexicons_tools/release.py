import typing as t
from datetime import date

import httpx

_PYPI_URL = 'https://pypi.org/pypi/{package}/json'
_TIMEOUT_SECONDS = 30


def get_next_version(today: date, published: t.Iterable[str]) -> str:
    base = f'{today.year}.{today.month}.{today.day}'
    taken = set(published)
    if base not in taken:
        return base

    counter = 1
    while f'{base}.{counter}' in taken:
        counter += 1

    return f'{base}.{counter}'


def fetch_published_versions(package: str, client: httpx.Client | None = None) -> list[str]:
    url = _PYPI_URL.format(package=package)
    response = (client or httpx).get(url, timeout=_TIMEOUT_SECONDS, follow_redirects=True)
    if response.status_code == httpx.codes.NOT_FOUND:
        return []

    response.raise_for_status()
    return list(response.json()['releases'])
