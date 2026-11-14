import enum
import re
import typing as t


class WarningKind(enum.Enum):
    SKIPPED_LEXICON = enum.auto()
    SKIPPED_METHOD = enum.auto()
    UNRESOLVED_REFERENCE = enum.auto()


class CodegenWarning(t.NamedTuple):
    kind: WarningKind
    nsid: str
    reason: str


_PATTERNS = (
    (WarningKind.SKIPPED_METHOD, re.compile(r'^Skipped method (?P<nsid>\S+): (?P<reason>.*)$', re.DOTALL)),
    (WarningKind.SKIPPED_LEXICON, re.compile(r'^Skipped (?P<nsid>\S+)\.json: (?P<reason>.*)$', re.DOTALL)),
    (
        WarningKind.UNRESOLVED_REFERENCE,
        re.compile(r"^Unresolved reference '.+' in (?P<nsid>\S+): (?P<reason>.*)$", re.DOTALL),
    ),
)


def parse_warning(text: str) -> CodegenWarning | None:
    for kind, pattern in _PATTERNS:
        match = pattern.match(text)
        if match:
            return CodegenWarning(kind, match['nsid'], match['reason'])

    return None


def parse_warnings(texts: t.Iterable[str]) -> list[CodegenWarning]:
    """Read the warnings that name a lexicon; the others say nothing about the support of a service."""
    return [warning for warning in map(parse_warning, texts) if warning]
