"""Tests the command line interface."""

from __future__ import annotations

import io
import pathlib
from typing import Any

import pandas as pd
import pytest

import courtpy
from courtpy import cli


def test_rules(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(['rules', 'federal']) == 0
    output = capsys.readouterr().out
    assert 'rules are valid' in output and 'outcome' not in output
    assert '  review_district' in output and '  party1_appellant' not in output
    assert cli.main(['rules', 'lexis_nexis_header']) == 0
    output = capsys.readouterr().out
    assert '  party1_appellant' in output and '  court_name' in output


def test_bad_rules(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / 'bad.csv'
    path.write_text('target,variable,kind,pattern,ignorecase,dotall\nopinion,x,oops,x,TRUE,FALSE\n',
                    encoding = 'utf-8')
    assert cli.main(['rules', str(path)]) == 1
    assert 'row 2' in capsys.readouterr().err


def test_parse(court_listener_folder: pathlib.Path, tmp_path: pathlib.Path) -> None:
    output = tmp_path / 'cases.csv'
    assert cli.main(['-q', 'parse', str(court_listener_folder), '--output', str(output)]) == 0
    table = courtpy.Cases.load(output).data
    assert 'outcome_reversal' in table.columns
    # The whole dataset is saved beside the table.
    whole = courtpy.Cases.load(output.with_suffix('.joblib'))
    assert [e['technique'] for e in whole.history][-1] == 'save_data'


def test_split_and_parse_lexis(tmp_path: pathlib.Path) -> None:
    fixtures = pathlib.Path(__file__).parent / 'fixtures'
    folder = tmp_path / 'lexis'
    assert cli.main(['-q', 'split', str(fixtures), '--folder', str(folder)]) == 0
    output = tmp_path / 'lexis.csv'
    assert cli.main([
        '-q', 'parse', str(folder), '--source', 'lexis_nexis', '--output', str(output),
        '--no-code']) == 0
    assert len(courtpy.Cases.load(output).data) == 2


def test_key_commands(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(['key', 'show']) == 1
    monkeypatch.setattr('sys.stdin', io.StringIO('abcd1234efgh5678\n'))
    assert cli.main(['key', 'set', '--stdin', '--store', 'file']) == 0
    assert cli.main(['key', 'show']) == 0
    output = capsys.readouterr().out
    assert 'abcd' in output and '5678' in output and 'abcd1234efgh5678' not in output
    assert cli.main(['key', 'delete']) == 0
    assert courtpy.secrets.find_api_key() is None


def test_download(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str]) -> None:
    calls = []

    def record(self: courtpy.CourtListener, *args: object, **kwargs: object) -> list[pathlib.Path]:
        calls.append((self, args, kwargs))
        return []

    monkeypatch.setattr(courtpy.CourtListener, 'download', record)
    monkeypatch.chdir(tmp_path)
    assert cli.main([
        '-q', 'download', '--courts', 'federal_geographic_circuits', 'scotus',
        '--max-cases', '3', '--bulk-date', '2026-09-30', '--stream']) == 0
    client, args, kwargs = calls[0]
    assert client.bulk_date == '2026-09-30' and client.stream
    assert args == (
        ['federal_geographic_circuits', 'scotus'], None, None, pathlib.Path('courtlistener'))
    assert kwargs == {
        'method': 'bulk', 'max_cases': 3, 'dockets': False, 'refresh': False}
    assert '0 cases saved in courtlistener' in capsys.readouterr().out


def test_download_needs_a_key(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(['-q', 'download', '--method', 'api', '--courts', 'ca1']) == 1
    assert 'no CourtListener API key' in capsys.readouterr().err


def test_judges(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    asked: dict[str, Any] = {}

    def from_fjc(**kwargs: Any) -> courtpy.judges.Roster:
        asked.update(kwargs)
        return courtpy.judges.Roster(pd.DataFrame({
            'nid': [1, 1, 2], 'judge': ['A', 'A', 'B'], 'last_name': ['A', 'A', 'B'],
            'first_name': ['X', 'X', 'Y'], 'court_num': [1, 2, 1], 'circuit_num': [1, 2, 1],
            'start_year': [1990, 2000, 1995], 'end_year': [2000, 2010, 2005]}))

    monkeypatch.setattr(courtpy.judges.Roster, 'from_fjc', from_fjc)
    output = tmp_path / 'roster.csv'
    assert cli.main(['-q', 'judges', '--no-jcs', '--output', str(output)]) == 0
    assert asked == {'update': False, 'jcs': False, 'martin_quinn': False, 'rulebook': 'judges'}
    assert output.is_file()
    assert 'A roster of 2 judges was saved' in capsys.readouterr().out


def test_study_commands(capsys: pytest.CaptureFixture[str]) -> None:
    # A study adds a command of its own and changes a default of courtpy's.

    def greet(arguments: Any) -> int:
        print(f'hello {arguments.name} with {arguments.rulebook}')
        return 0

    def add_commands(commands: Any) -> None:
        hello = commands.add_parser('hello')
        hello.add_argument('name')
        hello.set_defaults(command = greet, rulebook = 'careers.csv')
        commands.choices['judges'].set_defaults(rulebook = 'careers.csv')

    assert cli.main(['hello', 'court'], prog = 'study', add_commands = add_commands) == 0
    assert capsys.readouterr().out == 'hello court with careers.csv\n'
    assert cli.main(['rules', 'no_such_rules'], prog = 'study', add_commands = add_commands) == 1
    assert capsys.readouterr().err.startswith('study: ')
    with pytest.raises(SystemExit):
        cli.main(['--help'], prog = 'study', add_commands = add_commands)
    assert 'hello' in capsys.readouterr().out
