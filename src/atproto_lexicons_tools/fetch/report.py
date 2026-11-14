import os
import uuid
from pathlib import Path

from atproto_lexicons_tools.core.lock import Changes

_BODY_LIST_LIMIT = 40
_GITHUB_OUTPUT_ENV = 'GITHUB_OUTPUT'


def build_title(changes: Changes) -> str:
    parts = [f'{len(nsids)} {name}' for name, nsids in changes._asdict().items() if nsids]

    return f'Update lexicons: {", ".join(parts)}'


def build_body(changes: Changes, unreachable: list[str], errors: list[str]) -> str:
    lines: list[str] = []
    for name, nsids in changes._asdict().items():
        if not nsids:
            continue

        lines.append(f'**{name.capitalize()} ({len(nsids)})**')
        lines.extend(f'- `{nsid}`' for nsid in nsids[:_BODY_LIST_LIMIT])
        if len(nsids) > _BODY_LIST_LIMIT:
            lines.append(f'- and {len(nsids) - _BODY_LIST_LIMIT} more')
        lines.append('')

    if unreachable:
        lines.append('**Left untouched, could not be reached**')
        lines.extend(f'- `{domain}`' for domain in unreachable)
        lines.append('')

    if errors:
        lines.append('**Errors**')
        lines.extend(f'- {error}' for error in errors)
        lines.append('')

    return '\n'.join(lines).strip()


def _set_github_output(name: str, value: str) -> None:
    output_path = os.environ.get(_GITHUB_OUTPUT_ENV)
    if not output_path:
        return

    # a random delimiter: the value is text from other services and must not be able to end itself
    delimiter = f'EOF-{uuid.uuid4()}'
    with Path(output_path).open('a', encoding='utf-8') as f:
        f.write(f'{name}<<{delimiter}\n{value}\n{delimiter}\n')


def write_github_outputs(changes: Changes, unreachable: list[str], errors: list[str]) -> None:
    _set_github_output('changed', 'true' if changes else 'false')
    _set_github_output('title', build_title(changes) if changes else '')
    _set_github_output('body', build_body(changes, unreachable, errors))
