import shutil
import tempfile
import typing as t
from pathlib import Path

from atproto_lexicons_tools.build.diagnostics import CodegenWarning, parse_warnings
from atproto_lexicons_tools.build.generate import generate, stage_lexicons
from atproto_lexicons_tools.build.support import ServiceSupport, SupportList, classify, count_kinds, render
from atproto_lexicons_tools.core.registry import Service, load_services
from atproto_lexicons_tools.core.sdk import get_sdk_nsids
from atproto_lexicons_tools.paths import (
    LEXICONS_DIR,
    PACKAGE_PROJECT_DIR,
    README_PATH,
    SUPPORT_JSON_PATH,
    SUPPORT_MD_PATH,
)


def summarize(
    services: list[Service], sdk_nsids: t.AbstractSet[str], warnings: t.Sequence[CodegenWarning]
) -> list[ServiceSupport]:
    summary: list[ServiceSupport] = []
    for service in services:
        paths = sorted(LEXICONS_DIR.joinpath(service.domain).glob('*.json'))
        nsids = {path.stem for path in paths}
        summary.append(classify(service, nsids, sdk_nsids, warnings, count_kinds(paths)))

    return summary


def write_support_list(summary: list[ServiceSupport], warnings: list[str]) -> None:
    SupportList(summary, warnings).save(SUPPORT_JSON_PATH)
    SUPPORT_MD_PATH.write_text(render(summary), encoding='utf-8')


class BuildResult(t.NamedTuple):
    lexicon_count: int
    summary: list[ServiceSupport]
    warnings: list[str]


def run() -> BuildResult:
    services = load_services()
    sdk_nsids = get_sdk_nsids()

    with tempfile.TemporaryDirectory(prefix='atproto_lexicons_') as staging:
        count = stage_lexicons(Path(staging), sdk_nsids)
        warnings = generate(Path(staging))

    shutil.copy(README_PATH, PACKAGE_PROJECT_DIR.joinpath(README_PATH.name))

    summary = summarize(services, sdk_nsids, parse_warnings(warnings))
    write_support_list(summary, warnings)

    return BuildResult(count, summary, warnings)
