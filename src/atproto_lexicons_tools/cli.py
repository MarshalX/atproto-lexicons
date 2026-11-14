import asyncio
import functools
import http.server
import os
import subprocess
import sys
import typing as t
from datetime import datetime, timezone

import httpx
import typer
import typing_extensions as te
from rich.console import Console
from rich.table import Table

from atproto_lexicons_tools import lint as lint_tool
from atproto_lexicons_tools import release as release_tool
from atproto_lexicons_tools.build import builder as build_tool
from atproto_lexicons_tools.build import support
from atproto_lexicons_tools.build import verify as verify_tool
from atproto_lexicons_tools.build.support import ServiceSupport, Status
from atproto_lexicons_tools.core.registry import Service, dump_services, load_services
from atproto_lexicons_tools.fetch import fetcher as fetch_tool
from atproto_lexicons_tools.fetch.resolver import UnreachableError
from atproto_lexicons_tools.paths import (
    LEXICONS_DIR,
    LOCK_PATH,
    PACKAGE,
    PYPI_NAME,
    SDK_REPOSITORY,
    SERVICES_PATH,
    SUPPORT_JSON_PATH,
    SUPPORT_MD_PATH,
)
from atproto_lexicons_tools.site import builder as site_tool
from atproto_lexicons_tools.site import github as github_tool

app = typer.Typer(
    help='Fetch third-party AT Protocol lexicons and build the atproto-lexicons package from them.',
    no_args_is_help=True,
    rich_markup_mode='rich',
    add_completion=False,
)

_PIPED_WIDTH = 160

out = Console(width=None if sys.stdout.isatty() else _PIPED_WIDTH)
err = Console(stderr=True)

_STATUS_STYLES = {Status.FULL: 'green', Status.PARTIAL: 'yellow', Status.UNSUPPORTED: 'red'}
_STATUS_NAMES = ', '.join(status.value for status in Status)
_NUMERIC_COLUMNS_FROM = 2


class _ChangeStyle(t.NamedTuple):
    marker: str
    style: str


_CHANGE_STYLES = {
    'added': _ChangeStyle('+', 'green'),
    'changed': _ChangeStyle('~', 'yellow'),
    'removed': _ChangeStyle('-', 'red'),
}
_LIST_LIMIT = 15

_SERVE_HOST = '127.0.0.1'
_DEFAULT_SERVE_PORT = 8000
_GITHUB_TOKEN_ENV = 'GITHUB_TOKEN'  # noqa: S105 the name of the variable, not a token


def _fail(message: str) -> te.NoReturn:
    err.print(f'[bold red]error:[/] {message}')
    raise typer.Exit(code=1)


def _print_list(title: str, items: t.Sequence[str], style: str, marker: str = '-') -> None:
    if not items:
        return

    err.print(f'[bold]{title}[/] ({len(items)})')
    for item in items[:_LIST_LIMIT]:
        err.print(f'  [{style}]{marker}[/] {item}', highlight=False)

    if len(items) > _LIST_LIMIT:
        err.print(f'  [dim]and {len(items) - _LIST_LIMIT} more[/]')


def _print_fetch_result(result: fetch_tool.FetchResult, service_count: int) -> None:
    err.print(
        f'[bold green]Fetched[/] {result.lock.lexicon_count} lexicons of {service_count} services, '
        f'{len(result.lock.external)} external.'
    )

    if not result.changes:
        err.print('[dim]No changes.[/]')
    for name, nsids in result.changes._asdict().items():
        _print_list(name.capitalize(), nsids, _CHANGE_STYLES[name].style, _CHANGE_STYLES[name].marker)

    _print_list('Left untouched, could not be reached', result.lock.unreachable, 'yellow')
    _print_list('Warnings', result.errors, 'yellow')


def _fetch_and_report(services: list[Service]) -> fetch_tool.FetchResult:
    with err.status(f'Resolving {len(services)} services...'):
        try:
            result = fetch_tool.run(services)
        except ValueError as e:
            _fail(f'{LOCK_PATH.name} cannot be read: {e}')

    _print_fetch_result(result, len(services))
    return result


def _styled(status: Status, text: str) -> str:
    return f'[{_STATUS_STYLES[status]}]{text}[/]'


def _status_counts(summary: t.Iterable[ServiceSupport]) -> str:
    counts = support.count_by_status(summary)

    return ', '.join(_styled(status, f'{count} {status.label.lower()}') for status, count in counts.items())


def _run_verify() -> None:
    with err.status(f'Loading every model of [bold]{PACKAGE}[/]...'):
        try:
            result = verify_tool.run_isolated()
        except subprocess.CalledProcessError as e:
            err.print(e.stderr.strip(), markup=False, highlight=False)
            _fail(f'{PACKAGE} does not load.')

    err.print(f'[bold green]Verified[/] {result.files} files, {result.models} models.')


@app.command()
def fetch() -> None:
    """Download the lexicons every service in the registry publishes."""
    _fetch_and_report(load_services())


@app.command()
def build(
    skip_verify: te.Annotated[bool, typer.Option('--skip-verify', help='Do not load the generated package.')] = False,
) -> None:
    """Generate the package from the committed lexicons and write the support list."""
    with err.status(f'Generating [bold]{PACKAGE}[/]...'):
        result = build_tool.run()

    err.print(f'[bold green]Generated[/] {PACKAGE} from {result.lexicon_count} lexicons.')
    err.print(f'Services: {_status_counts(result.summary)}. Left out or weakened: {len(result.warnings)}.')
    err.print(f'[dim]Support list written to {SUPPORT_MD_PATH.name} and {SUPPORT_JSON_PATH.name}.[/]')

    if not skip_verify:
        _run_verify()


@app.command()
def verify() -> None:
    """Check that the generated package loads and keeps the namespaces of the SDK."""
    _run_verify()


@app.command()
def lint(
    fix: te.Annotated[bool, typer.Option('--fix', help='Sort and reformat the registry first.')] = False,
) -> None:
    """Check the registry and that the committed lexicons match it. Needs no network."""
    problems = lint_tool.lint(SERVICES_PATH, LOCK_PATH, LEXICONS_DIR, fix=fix)
    if not problems:
        err.print('[bold green]All good.[/]')
        return

    for problem in problems:
        err.print(f'[red]✗[/] {problem}', highlight=False)
    _fail(f'{len(problems)} problem{"s" if len(problems) > 1 else ""} found.')


@app.command()
def add(
    domain: te.Annotated[str, typer.Argument(help='Domain the NSIDs are under. `fm.teal.*` is `teal.fm`.')],
    nsid: te.Annotated[
        list[str] | None,
        typer.Option(help='NSID of the service, to find the repository it publishes in. Repeatable.'),
    ] = None,
) -> None:
    """Add a service to the registry and download its lexicons."""
    if not lint_tool.is_domain(domain):
        _fail(f'{domain!r} is not a lowercase domain name a service can be listed under.')

    services = load_services()
    if any(service.domain == domain for service in services):
        _fail(f'{domain} is in the registry already.')

    service = Service(domain, ())
    foreign = [value for value in nsid or [] if not service.owns(value)]
    if foreign:
        _fail(f'{", ".join(foreign)} is not under {service.nsid_prefix}*')

    with err.status(f'Looking for the lexicons of {domain}...'):
        try:
            dids = asyncio.run(fetch_tool.find_dids([service.probe_nsid, *(nsid or [])]))
        except UnreachableError as e:
            _fail(f'Could not look {domain} up, try again: {e}')

    if not dids:
        _fail(
            f'No `_lexicon` DNS record found for {domain}. If its lexicons are published under a subdomain, '
            f'pass one of them: [bold]lex add {domain} --nsid {service.nsid_prefix}feed.post[/]'
        )

    SERVICES_PATH.write_text(dump_services([*services, Service(domain, tuple(dids))]), encoding='utf-8')
    err.print(f'[bold green]Added[/] {domain} to {SERVICES_PATH.name}.')

    result = _fetch_and_report(load_services())

    if not result.lock.services.get(domain):
        err.print(f'[yellow]{domain} publishes no lexicons under {service.nsid_prefix}*[/]')

    err.print('Next: [bold]lex build[/], then commit the changes.')


def _fetch_sdk_stars() -> int | None:
    try:
        return github_tool.fetch_stars(SDK_REPOSITORY, os.environ.get(_GITHUB_TOKEN_ENV, ''))
    except (httpx.HTTPError, KeyError, ValueError) as e:
        err.print(f'[yellow]Warning:[/] could not ask GitHub for the stars of {SDK_REPOSITORY}, left out: {e}')
        return None


@app.command()
def site(
    serve: te.Annotated[bool, typer.Option('--serve', help='Serve the website locally after building it.')] = False,
    port: te.Annotated[int, typer.Option(help='Port to serve on.')] = _DEFAULT_SERVE_PORT,
) -> None:
    """Build the website that lists the services and their lexicons."""
    try:
        result = site_tool.run(sdk_stars=_fetch_sdk_stars())
    except FileNotFoundError:
        _fail(f'{SUPPORT_JSON_PATH.name} does not exist yet. Run [bold]lex build[/] first.')

    err.print(
        f'[bold green]Built[/] the website: {result.services} services, {result.lexicons} lexicons. '
        f'[dim]Written to {result.directory.name}/.[/]'
    )
    if not serve:
        return

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(result.directory))
    with http.server.ThreadingHTTPServer((_SERVE_HOST, port), handler) as server:
        err.print(f'Serving on [bold]http://{_SERVE_HOST}:{port}[/]. Press Ctrl+C to stop.')

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            err.print('Stopped.')


@app.command()
def version() -> None:
    """Print the version the next release of the package gets: today's date, counted if it is taken."""
    try:
        published = release_tool.fetch_published_versions(PYPI_NAME)
    except httpx.HTTPError as e:
        _fail(f'Could not ask PyPI which versions exist: {e}')

    out.print(release_tool.get_next_version(datetime.now(timezone.utc).date(), published), highlight=False)


def _load_summary() -> list[ServiceSupport]:
    try:
        return support.SupportList.load(SUPPORT_JSON_PATH).services
    except FileNotFoundError:
        _fail(f'{SUPPORT_JSON_PATH.name} does not exist yet. Run [bold]lex build[/] first.')


def _print_service(service: ServiceSupport) -> None:
    out.print(f'[bold]{service.domain}[/]  {_styled(service.status, service.status.label)}')
    out.print(
        f'{service.available} of {service.lexicons} lexicons, {service.provided_by_sdk} of them shipped by the SDK.'
    )

    for title, nsids in (
        ('Skipped lexicons', service.skipped_lexicons),
        ('Skipped methods', service.skipped_methods),
        ('Lexicons with untyped references', service.weakened_lexicons),
    ):
        if not nsids:
            continue

        out.print(f'\n[bold]{title}[/]')
        for value in nsids:
            out.print(f'  {value}', highlight=False)


def _build_table(services: t.Iterable[ServiceSupport]) -> Table:
    table = Table(header_style='bold', box=None, pad_edge=False)
    for index, column in enumerate(support.COLUMNS):
        table.add_column(column, justify='right' if index >= _NUMERIC_COLUMNS_FROM else 'left', no_wrap=True)

    for service in services:
        table.add_row(service.domain, _styled(service.status, service.status.label), *service.get_counts())

    return table


@app.command()
def status(
    domain: te.Annotated[str | None, typer.Argument(help='Show the details of one service.')] = None,
    only: te.Annotated[
        str | None,
        typer.Option(help=f'Show only the services of this status: {_STATUS_NAMES}.'),
    ] = None,
) -> None:
    """Show how well each service is supported by the last build."""
    summary = _load_summary()

    if domain:
        service = next((item for item in summary if item.domain == domain), None)
        if service is None:
            _fail(f'{domain} is not in the support list.')

        _print_service(service)
        return

    if only and only not in {status.value for status in Status}:
        _fail(f'Unknown status {only!r}. Use one of: {_STATUS_NAMES}.')

    out.print(_build_table(service for service in summary if not only or service.status.value == only))
    err.print(f'\n{len(summary)} services: {_status_counts(summary)}.')
