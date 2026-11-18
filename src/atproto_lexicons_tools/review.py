"""Decide whether an update of the lexicons can be merged without a person looking at it.

An update that only adds or changes lexicons ships what the services publish. One that takes something away
from the users of the package is held: removed lexicons break the code that imports them.
"""

import json
import subprocess
import typing as t

from atproto_lexicons_tools.build.support import ServiceSupport, Status, SupportList
from atproto_lexicons_tools.core.lock import Lock, diff_locks
from atproto_lexicons_tools.paths import LOCK_PATH, ROOT, SUPPORT_JSON_PATH

_LIST_LIMIT = 20
_RANKS = {Status.FULL: 0, Status.PARTIAL: 1, Status.UNSUPPORTED: 2}


def _describe_removed(nsids: list[str]) -> str:
    listed = ', '.join(f'`{nsid}`' for nsid in nsids[:_LIST_LIMIT])
    more = f' and {len(nsids) - _LIST_LIMIT} more' if len(nsids) > _LIST_LIMIT else ''

    count = '1 lexicon is' if len(nsids) == 1 else f'{len(nsids)} lexicons are'

    return f'{count} removed: {listed}{more}.'


def _describe_regression(old: ServiceSupport, new: ServiceSupport) -> str | None:
    if _RANKS[new.status] > _RANKS[old.status]:
        return f'`{new.domain}` is supported worse: {old.status.label.lower()} before, {new.status.label.lower()} now.'
    if new.available < old.available:
        return f'`{new.domain}` has fewer lexicons in the package: {old.available} before, {new.available} now.'

    return None


def find_hold_reasons(old_lock: Lock, new_lock: Lock, old_support: SupportList, new_support: SupportList) -> list[str]:
    reasons: list[str] = []

    removed = diff_locks(old_lock, new_lock).removed
    if removed:
        reasons.append(_describe_removed(removed))

    before = {service.domain: service for service in old_support.services}
    for service in new_support.services:
        old = before.get(service.domain)
        reason = _describe_regression(old, service) if old else None
        if reason:
            reasons.append(reason)

    return reasons


def _read_at(revision: str, path: str) -> t.Any:
    """Read a JSON file as it is in a revision; :obj:`None` if it does not exist there."""
    completed = subprocess.run(  # noqa: S603 the arguments are not run by a shell
        ['git', 'show', f'{revision}:{path}'],  # noqa: S607 git is wherever the repository is checked out
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        check=False,
    )
    if completed.returncode:
        return None

    return json.loads(completed.stdout)


def run(base: str) -> list[str]:
    """Compare the working tree with a revision.

    Raises:
        ValueError: A lock cannot be read.
    """
    old_lock_data = _read_at(base, LOCK_PATH.name)
    old_support_data = _read_at(base, SUPPORT_JSON_PATH.name)

    return find_hold_reasons(
        Lock.from_dict(old_lock_data) if old_lock_data else Lock(),
        Lock.load(LOCK_PATH),
        SupportList.from_dict(old_support_data) if old_support_data else SupportList([], []),
        SupportList.load(SUPPORT_JSON_PATH),
    )


def build_section(reasons: list[str]) -> str:
    """Tell in the pull request why it waits for a person."""
    if not reasons:
        return ''

    return '\n'.join(['**Held for review, not merged automatically**', *(f'- {reason}' for reason in reasons)])
