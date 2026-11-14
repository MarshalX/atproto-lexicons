import json
import shutil
from pathlib import Path

from atproto_lexicons_tools.core import lexicon
from atproto_lexicons_tools.core.lock import Entries, LockEntry
from atproto_lexicons_tools.core.registry import Service
from atproto_lexicons_tools.fetch.resolver import ResolvedSchema, Schemas
from atproto_lexicons_tools.paths import EXTERNAL_DIR_NAME

_BYTES_IN_KIB = 1024
_MAX_LEXICON_BYTES = 512 * _BYTES_IN_KIB


def _get_path(directory: Path, nsid: str) -> Path:
    return directory.joinpath(f'{nsid}.json')


def write_schemas(directory: Path, schemas: Schemas) -> tuple[Entries, list[str]]:
    """Replace the content of the directory with the schemas.

    Returns:
        The lock entries of what was written, and the NSIDs that are too large to keep.
    """
    shutil.rmtree(directory, ignore_errors=True)

    entries: Entries = {}
    oversized: list[str] = []
    for nsid, schema in sorted(schemas.items()):
        content = json.dumps(schema.value, indent=2, ensure_ascii=False) + '\n'
        if len(content.encode('utf-8')) > _MAX_LEXICON_BYTES:
            oversized.append(nsid)
            continue

        directory.mkdir(parents=True, exist_ok=True)
        _get_path(directory, nsid).write_text(content, encoding='utf-8')
        entries[nsid] = LockEntry(did=schema.did, cid=schema.cid)

    return entries, oversized


def read_schemas(directory: Path, entries: Entries) -> Schemas:
    schemas: Schemas = {}
    for nsid, entry in entries.items():
        try:
            value = lexicon.read(_get_path(directory, nsid))
        except (OSError, ValueError):
            continue

        schemas[nsid] = ResolvedSchema(value=value, cid=entry.cid, did=entry.did)

    return schemas


def describe_oversized(nsids: list[str]) -> list[str]:
    limit = _MAX_LEXICON_BYTES // _BYTES_IN_KIB
    return [f'{nsid}: left out, larger than {limit} KiB' for nsid in nsids]


def remove_stale_directories(lexicons_dir: Path, services: list[Service]) -> None:
    known = {service.domain for service in services} | {EXTERNAL_DIR_NAME}
    for directory in lexicons_dir.iterdir():
        if directory.is_dir() and directory.name not in known:
            shutil.rmtree(directory)
