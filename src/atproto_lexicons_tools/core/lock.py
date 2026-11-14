import dataclasses
import json
import typing as t
from pathlib import Path

import typing_extensions as te


class LockEntry(t.NamedTuple):
    did: str
    cid: str


Entries = dict[str, LockEntry]


def _parse_entries(data: dict[str, t.Any]) -> Entries:
    return {nsid: LockEntry(did=str(entry['did']), cid=str(entry['cid'])) for nsid, entry in data.items()}


def _dump_entries(entries: Entries) -> dict[str, dict[str, str]]:
    return {nsid: entry._asdict() for nsid, entry in entries.items()}


@dataclasses.dataclass(frozen=True)
class Lock:
    services: dict[str, Entries] = dataclasses.field(default_factory=dict[str, Entries])
    external: Entries = dataclasses.field(default_factory=dict[str, LockEntry])
    unresolved: list[str] = dataclasses.field(default_factory=list[str])
    unreachable: list[str] = dataclasses.field(default_factory=list[str])
    # the day the lexicons of each service last changed
    updated: dict[str, str] = dataclasses.field(default_factory=dict[str, str])

    @classmethod
    def from_dict(cls, data: t.Any) -> te.Self:
        try:
            return cls(
                services={domain: _parse_entries(entries) for domain, entries in data.get('services', {}).items()},
                external=_parse_entries(data.get('external', {})),
                unresolved=[str(nsid) for nsid in data.get('unresolved', [])],
                unreachable=[str(domain) for domain in data.get('unreachable', [])],
                updated={str(domain): str(day) for domain, day in data.get('updated', {}).items()},
            )
        except (AttributeError, KeyError, TypeError) as e:
            message = f'not a lock of lexicons: {type(e).__name__} {e}'
            raise ValueError(message) from e

    @classmethod
    def load(cls, path: Path) -> te.Self:
        """Read the lock, which is empty until the first fetch.

        Raises:
            ValueError: The file is not JSON or does not have the shape of a lock.
        """
        if not path.exists():
            return cls()

        return cls.from_dict(json.loads(path.read_text(encoding='utf-8')))

    def to_dict(self) -> dict[str, t.Any]:
        return {
            'services': {domain: _dump_entries(entries) for domain, entries in self.services.items()},
            'external': _dump_entries(self.external),
            'unresolved': self.unresolved,
            'unreachable': self.unreachable,
            'updated': self.updated,
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + '\n', encoding='utf-8')

    @property
    def lexicon_count(self) -> int:
        return sum(len(entries) for entries in self.services.values())

    def get_cids(self) -> dict[str, str]:
        cids = {nsid: entry.cid for entries in self.services.values() for nsid, entry in entries.items()}
        cids.update({nsid: entry.cid for nsid, entry in self.external.items()})

        return cids


class Changes(t.NamedTuple):
    added: list[str]
    changed: list[str]
    removed: list[str]

    def __bool__(self) -> bool:
        return bool(self.added or self.changed or self.removed)


def diff_locks(old: Lock, new: Lock) -> Changes:
    before, after = old.get_cids(), new.get_cids()

    return Changes(
        added=sorted(set(after) - set(before)),
        changed=sorted(nsid for nsid in set(after) & set(before) if after[nsid] != before[nsid]),
        removed=sorted(set(before) - set(after)),
    )


def date_changes(old: Lock, services: dict[str, Entries], today: str) -> dict[str, str]:
    return {
        domain: today if entries != old.services.get(domain) else old.updated.get(domain, today)
        for domain, entries in services.items()
    }
