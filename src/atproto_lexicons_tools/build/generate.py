import shutil
import typing as t
from pathlib import Path

from atproto_codegen.config import CodegenConfig
from atproto_codegen.diagnostics import clear_warnings, get_warnings
from atproto_codegen.models import builder
from atproto_codegen.models.generator import generate_models
from atproto_codegen.namespaces.generator import generate_namespaces
from atproto_codegen.subscriptions.generator import generate_subscriptions

from atproto_lexicons_tools.paths import LEXICONS_DIR, PACKAGE, PACKAGE_DIR

_PY_TYPED = 'py.typed'


def stage_lexicons(staging_dir: Path, sdk_nsids: t.AbstractSet[str]) -> int:
    count = 0
    for path in sorted(LEXICONS_DIR.glob('*/*.json')):
        if path.stem not in sdk_nsids:
            shutil.copy(path, staging_dir.joinpath(path.name))
            count += 1

    return count


def generate(lexicon_dir: Path) -> list[str]:
    config = CodegenConfig(emit_lexicon_dirs=(lexicon_dir,), output_dir=PACKAGE_DIR, package=PACKAGE, skip_invalid=True)

    shutil.rmtree(PACKAGE_DIR, ignore_errors=True)
    builder.clear_caches()
    clear_warnings()

    generate_models(config)
    generate_namespaces(config)
    generate_subscriptions(config)
    PACKAGE_DIR.joinpath(_PY_TYPED).touch()

    return get_warnings()
