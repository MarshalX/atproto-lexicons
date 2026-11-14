import enum
import typing as t
from datetime import datetime
from pathlib import Path

from atproto_codegen.utils import build_aliases, convert_camel_case_to_snake_case, to_identifier
from atproto_core.nsid import NSID

from atproto_lexicons_tools.build import support
from atproto_lexicons_tools.build.diagnostics import CodegenWarning, WarningKind
from atproto_lexicons_tools.core import lexicon
from atproto_lexicons_tools.paths import PACKAGE, REPOSITORY_URL

_SDK_PACKAGE = 'atproto'
_DESCRIPTION_LIMIT = 220
_ELLIPSIS = '…'


class State(str, enum.Enum):
    GENERATED = 'generated'
    PROVIDED_BY_SDK = 'sdk'
    SKIPPED = 'skipped'
    METHOD_SKIPPED = 'method-skipped'
    UNTYPED_REFERENCES = 'untyped'


_STATES_WITH_CLIENT = frozenset({State.GENERATED, State.UNTYPED_REFERENCES, State.PROVIDED_BY_SDK})
_STATES_WITH_MODEL = _STATES_WITH_CLIENT | {State.METHOD_SKIPPED}
_STATES_WITH_REASON = frozenset({State.SKIPPED, State.METHOD_SKIPPED})
_REASONED_WARNINGS = frozenset({WarningKind.SKIPPED_LEXICON, WarningKind.SKIPPED_METHOD})


class CatalogLexicon(t.NamedTuple):
    nsid: str
    kind: str
    description: str
    state: State
    reason: str = ''
    id: str = ''
    model: str = ''
    client: str = ''

    def to_dict(self) -> dict[str, str]:
        required = {'nsid': self.nsid, 'kind': self.kind, 'description': self.description, 'state': self.state.value}
        optional = {'reason': self.reason, 'id': self.id, 'model': self.model, 'client': self.client}

        return {**required, **{name: value for name, value in optional.items() if value}}


class CatalogService(t.NamedTuple):
    domain: str
    status: support.Status
    updated: str
    lexicons: list[CatalogLexicon]

    def to_dict(self) -> dict[str, t.Any]:
        return {
            'domain': self.domain,
            'status': self.status.value,
            'updated': self.updated,
            'lexicons': [entry.to_dict() for entry in self.lexicons],
        }


class Catalog(t.NamedTuple):
    services: list[CatalogService]
    generated: datetime
    sdk_stars: int | None = None
    package: str = PACKAGE
    repository: str = REPOSITORY_URL

    @property
    def lexicon_count(self) -> int:
        return sum(len(service.lexicons) for service in self.services)

    def to_dict(self) -> dict[str, t.Any]:
        content: dict[str, t.Any] = {
            'package': self.package,
            'repository': self.repository,
            'generated': self.generated.replace(microsecond=0).isoformat(),
            'services': [service.to_dict() for service in self.services],
        }
        if self.sdk_stars is not None:
            content['sdk_stars'] = self.sdk_stars

        return content


def _shorten(text: str) -> str:
    text = ' '.join(text.split())
    if len(text) <= _DESCRIPTION_LIMIT:
        return text

    return text[: _DESCRIPTION_LIMIT - len(_ELLIPSIS)].rstrip() + _ELLIPSIS


def get_description(document: lexicon.Document) -> str:
    description = document.get('description') or lexicon.get_main(document).get('description') or ''

    return _shorten(description) if isinstance(description, str) else ''


def get_client_path(nsid: str, kind: str) -> str:
    *namespace, name = nsid.split('.')
    path = ['client', *(to_identifier(segment) for segment in namespace)]

    if kind == lexicon.RECORD:
        return '.'.join([*path, to_identifier(name)])
    if kind in lexicon.METHOD_KINDS:
        return '.'.join([*path, to_identifier(convert_camel_case_to_snake_case(name))]) + '()'

    return ''


def _get_state(nsid: str, service: support.ServiceSupport, sdk_nsids: t.AbstractSet[str]) -> State:
    if nsid in sdk_nsids:
        return State.PROVIDED_BY_SDK
    if nsid in service.skipped_lexicons:
        return State.SKIPPED
    if nsid in service.skipped_methods:
        return State.METHOD_SKIPPED
    if nsid in service.weakened_lexicons:
        return State.UNTYPED_REFERENCES

    return State.GENERATED


def _describe_lexicon(
    path: Path,
    service: support.ServiceSupport,
    aliases: dict[str, str],
    sdk_nsids: t.AbstractSet[str],
    reasons: dict[str, str],
) -> CatalogLexicon:
    nsid = path.stem
    document = lexicon.read(path)
    kind = lexicon.get_kind(document)

    state = _get_state(nsid, service, sdk_nsids)
    package = _SDK_PACKAGE if state is State.PROVIDED_BY_SDK else PACKAGE
    reason = reasons.get(nsid, '') if state in _STATES_WITH_REASON else ''
    entry = CatalogLexicon(nsid, kind, get_description(document), state, reason)

    if kind == lexicon.PERMISSION_SET:
        # requested by its NSID in an OAuth scope, so it has an id and no model
        has_id = state is not State.SKIPPED
        return entry._replace(id=f'{package}.models.ids.{aliases[nsid]}' if has_id else '')

    return entry._replace(
        model=f'{package}.models.{aliases[nsid]}' if state in _STATES_WITH_MODEL else '',
        client=get_client_path(nsid, kind) if state in _STATES_WITH_CLIENT else '',
    )


def _build_aliases(nsids: t.Iterable[str], sdk_nsids: t.AbstractSet[str]) -> dict[str, str]:
    # the package names its models among themselves, the SDK named each of its own on its own
    own = [NSID.from_str(nsid) for nsid in nsids if nsid not in sdk_nsids]
    aliases = {str(nsid): alias for nsid, alias in build_aliases(own).items()}

    for nsid in sdk_nsids:
        aliases.update({str(key): alias for key, alias in build_aliases([NSID.from_str(nsid)]).items()})

    return aliases


def build_services(
    summary: list[support.ServiceSupport],
    warnings: t.Iterable[CodegenWarning],
    updated: dict[str, str],
    lexicons_dir: Path,
    sdk_nsids: t.AbstractSet[str],
) -> list[CatalogService]:
    reasons = {warning.nsid: _shorten(warning.reason) for warning in warnings if warning.kind in _REASONED_WARNINGS}
    paths = {service.domain: sorted(lexicons_dir.joinpath(service.domain).glob('*.json')) for service in summary}
    aliases = _build_aliases((path.stem for group in paths.values() for path in group), sdk_nsids)

    return [
        CatalogService(
            domain=service.domain,
            status=service.status,
            updated=updated.get(service.domain, ''),
            lexicons=[_describe_lexicon(path, service, aliases, sdk_nsids, reasons) for path in paths[service.domain]],
        )
        for service in summary
    ]
