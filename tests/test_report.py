from pathlib import Path

import pytest

from atproto_lexicons_tools.core.lock import Changes
from atproto_lexicons_tools.fetch import report


def test_title_counts_each_kind_of_change() -> None:
    assert report.build_title(Changes(['c'], ['b'], ['x'])) == 'Update lexicons: 1 added, 1 changed, 1 removed'
    assert report.build_title(Changes([], ['a', 'b'], [])) == 'Update lexicons: 2 changed'


def test_body_lists_changes_and_untouched_services() -> None:
    body = report.build_body(Changes(['a'], [], ['b']), ['down.example.com'], ['DNS failed'])

    assert '**Added (1)**\n- `a`' in body
    assert '**Removed (1)**\n- `b`' in body
    assert '- `down.example.com`' in body
    assert '- DNS failed' in body
    assert 'Changed' not in body


def test_long_list_of_changes_is_cut() -> None:
    body = report.build_body(Changes([f'com.example.n{index}' for index in range(45)], [], []), [], [])

    assert body.count('- `') == 40
    assert body.endswith('- and 5 more')


def test_outputs_are_written_for_the_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / 'output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))

    report.write_github_outputs(Changes(['a'], [], []), [], ['first\nsecond'])

    lines = output.read_text(encoding='utf-8').splitlines()
    assert lines[1] == 'true'
    assert 'Update lexicons: 1 added' in lines
    assert lines.count('second') == 1


def test_nothing_is_written_outside_a_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('GITHUB_OUTPUT', raising=False)

    report.write_github_outputs(Changes([], [], []), [], [])
