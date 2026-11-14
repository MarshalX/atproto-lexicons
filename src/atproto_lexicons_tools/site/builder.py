import json
import shutil
import typing as t
from datetime import datetime, timezone
from pathlib import Path

from atproto_lexicons_tools.build.diagnostics import parse_warnings
from atproto_lexicons_tools.build.support import SupportList
from atproto_lexicons_tools.core.lock import Lock
from atproto_lexicons_tools.core.sdk import get_sdk_nsids
from atproto_lexicons_tools.paths import (
    LEXICONS_DIR,
    LOCK_PATH,
    SITE_DOMAIN,
    SITE_OUTPUT_DIR,
    SITE_SOURCE_DIR,
    SUPPORT_JSON_PATH,
)
from atproto_lexicons_tools.site.catalog import Catalog, build_services

_CATALOG_FILENAME = 'catalog.json'
_PAGE_FILENAME = 'index.html'
_DOMAIN_FILENAME = 'CNAME'
_NO_JEKYLL_FILENAME = '.nojekyll'


class SiteResult(t.NamedTuple):
    directory: Path
    services: int
    lexicons: int


def _stamp_page(page: Path, catalog: Catalog) -> None:
    # the counts are in the markup, so that previews and crawlers that run no scripts see them too
    numbers = {'{{services}}': f'{len(catalog.services):,}', '{{lexicons}}': f'{catalog.lexicon_count:,}'}

    content = page.read_text(encoding='utf-8')
    for placeholder, number in numbers.items():
        content = content.replace(placeholder, number)

    page.write_text(content, encoding='utf-8')


def run(output_dir: Path = SITE_OUTPUT_DIR, sdk_stars: int | None = None) -> SiteResult:
    """Build the website from the last build and the lock.

    The star count of the SDK is shown only when it is given: the page does without it.

    Raises:
        FileNotFoundError: The support list does not exist yet.
    """
    support_list = SupportList.load(SUPPORT_JSON_PATH)
    services = build_services(
        support_list.services,
        parse_warnings(support_list.warnings),
        Lock.load(LOCK_PATH).updated,
        LEXICONS_DIR,
        get_sdk_nsids(),
    )
    catalog = Catalog(services, generated=datetime.now(timezone.utc), sdk_stars=sdk_stars)

    shutil.rmtree(output_dir, ignore_errors=True)
    shutil.copytree(SITE_SOURCE_DIR, output_dir)

    content = json.dumps(catalog.to_dict(), separators=(',', ':'))
    output_dir.joinpath(_CATALOG_FILENAME).write_text(content, encoding='utf-8')
    _stamp_page(output_dir.joinpath(_PAGE_FILENAME), catalog)
    output_dir.joinpath(_DOMAIN_FILENAME).write_text(f'{SITE_DOMAIN}\n', encoding='utf-8')
    output_dir.joinpath(_NO_JEKYLL_FILENAME).touch()

    return SiteResult(output_dir, len(catalog.services), catalog.lexicon_count)
