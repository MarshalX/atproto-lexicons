import enum
import json
import typing as t
from pathlib import Path

import typing_extensions as te

from atproto_lexicons_tools.build.diagnostics import CodegenWarning, WarningKind
from atproto_lexicons_tools.core import lexicon
from atproto_lexicons_tools.core.registry import Service


class Status(str, enum.Enum):
    FULL = 'full'
    PARTIAL = 'partial'
    UNSUPPORTED = 'unsupported'

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {Status.FULL: 'Full', Status.PARTIAL: 'Partial', Status.UNSUPPORTED: 'Not supported'}

COLUMNS = ('Service', 'Status', 'Lexicons', 'Records', 'Queries', 'Procedures', 'Skipped', 'Untyped refs in')


class ServiceSupport(t.NamedTuple):
    domain: str
    status: Status
    lexicons: int
    generated: int
    provided_by_sdk: int
    kinds: dict[str, int]
    skipped_lexicons: list[str]
    skipped_methods: list[str]
    weakened_lexicons: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> te.Self:
        fields: dict[str, t.Any] = {**data, 'status': Status(data['status'])}

        return cls(**fields)

    def to_dict(self) -> dict[str, t.Any]:
        return {**self._asdict(), 'status': self.status.value}

    @property
    def available(self) -> int:
        return self.generated + self.provided_by_sdk

    def get_counts(self) -> tuple[str, ...]:
        """Fill the columns after the status; a zero of what went wrong is left blank."""
        skipped = len(self.skipped_lexicons) + len(self.skipped_methods)

        return (
            f'{self.available} of {self.lexicons}',
            str(self.kinds[lexicon.RECORD]),
            str(self.kinds[lexicon.QUERY]),
            str(self.kinds[lexicon.PROCEDURE]),
            str(skipped or ''),
            str(len(self.weakened_lexicons) or ''),
        )


class SupportList(t.NamedTuple):
    services: list[ServiceSupport]
    # as the code generator worded them
    warnings: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> te.Self:
        return cls([ServiceSupport.from_dict(service) for service in data['services']], data['warnings'])

    @classmethod
    def load(cls, path: Path) -> te.Self:
        return cls.from_dict(json.loads(path.read_text(encoding='utf-8')))

    def save(self, path: Path) -> None:
        data = {'services': [service.to_dict() for service in self.services], 'warnings': self.warnings}
        path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def count_kinds(lexicon_paths: t.Iterable[Path]) -> dict[str, int]:
    counts = dict.fromkeys(lexicon.COUNTED_KINDS, 0)
    for path in lexicon_paths:
        kind = lexicon.get_kind(lexicon.read(path))
        if kind in counts:
            counts[kind] += 1

    return counts


def _find_nsids(kind: WarningKind, warnings: t.Iterable[CodegenWarning], own: t.AbstractSet[str]) -> list[str]:
    return sorted({warning.nsid for warning in warnings if warning.kind is kind and warning.nsid in own})


def classify(
    service: Service,
    nsids: set[str],
    sdk_nsids: t.AbstractSet[str],
    warnings: t.Sequence[CodegenWarning],
    kinds: dict[str, int],
) -> ServiceSupport:
    emitted = nsids - sdk_nsids
    skipped_lexicons = _find_nsids(WarningKind.SKIPPED_LEXICON, warnings, emitted)
    skipped_methods = _find_nsids(WarningKind.SKIPPED_METHOD, warnings, emitted)
    weakened_lexicons = _find_nsids(WarningKind.UNRESOLVED_REFERENCE, warnings, emitted)

    generated = len(emitted) - len(skipped_lexicons)
    if emitted and not generated:
        status = Status.UNSUPPORTED
    elif skipped_lexicons or skipped_methods or weakened_lexicons:
        status = Status.PARTIAL
    else:
        status = Status.FULL

    return ServiceSupport(
        domain=service.domain,
        status=status,
        lexicons=len(nsids),
        generated=generated,
        provided_by_sdk=len(nsids & sdk_nsids),
        kinds=kinds,
        skipped_lexicons=skipped_lexicons,
        skipped_methods=skipped_methods,
        weakened_lexicons=weakened_lexicons,
    )


def count_by_status(services: t.Iterable[ServiceSupport]) -> dict[Status, int]:
    counts = dict.fromkeys(Status, 0)
    for service in services:
        counts[service.status] += 1

    return counts


def _to_row(cells: t.Iterable[str]) -> str:
    return f'| {" | ".join(cells)} |'


def render(services: list[ServiceSupport]) -> str:
    counts = count_by_status(services)
    generated = sum(service.generated for service in services)
    total = sum(service.lexicons for service in services)
    by_sdk = sum(service.provided_by_sdk for service in services)

    lines = [
        '# Supported services',
        '',
        f'{generated} of {total} lexicons are packaged. Another {by_sdk} ship with the SDK itself.',
        '',
        '| Status | Services | Meaning |',
        '|---|---|---|',
        f'| Full | {counts[Status.FULL]} | Every lexicon is generated as published. |',
        (
            f'| Partial | {counts[Status.PARTIAL]} '
            '| Some lexicons are invalid and skipped, or have references that are typed as unknown. |'
        ),
        f'| Not supported | {counts[Status.UNSUPPORTED]} | Nothing could be generated. |',
        '',
        _to_row(COLUMNS),
        '|---' * len(COLUMNS) + '|',
    ]
    lines.extend(_to_row((f'`{service.domain}`', service.status.label, *service.get_counts())) for service in services)
    lines += [
        '',
        '"Skipped" counts lexicons that could not be parsed plus methods without a usable body.',
        '"Untyped refs in" counts lexicons where at least one reference could not be resolved.',
        '',
    ]

    return '\n'.join(lines)
