"""Tests the parsers and cases modules with CourtListener cases."""

from __future__ import annotations

import logging
import pathlib

import amos
import pandas as pd
import pytest
from conftest import make_cluster, make_opinion, write_case

import courtpy
from courtpy import cases, options, parsers


def test_parse_court_listener(court_listener_folder: pathlib.Path) -> None:
    table = courtpy.parse(court_listener_folder)
    assert list(table.index) == ['1', '2', '3']
    assert table.index.name == 'case_id'
    assert list(table.columns[:4]) == ['source', 'cluster_id', 'docket_id', 'court']
    doe = table.loc['1']
    assert doe['court'] == 'ca1' and doe['court_num'] == 1
    assert doe['court_name'] == 'first_circuit'
    assert doe['party1'] == 'UNITED STATES of America, Plaintiff-Appellee,'
    assert doe['party2_appellant'] and doe['party1_united_states']
    assert doe['disposition_reverse'] and doe['disposition_remand']
    assert doe['panel_judges'] == 'LYNCH; HOWARD; THOMPSON'
    assert doe['panel_size'] == 3 and doe['author'] == 'LYNCH'
    assert doe['citations_case'] == '554 U.S. 570'
    assert doe['citations_statute'].startswith('18 U.S.C. § 922')
    assert doe['cite_federal_reporter'] and doe['published']
    assert table.loc['2', 'dissenting'] == 'THOMPSON'
    assert table.loc['2', 'civil_titlevii']
    assert pd.api.types.is_bool_dtype(table['published'].dtype)
    assert table['year'].dtype == 'int64'


def test_parse_finds_agencies(tmp_path: pathlib.Path) -> None:
    # The agencies of the caption, the history, and the opinion are listed
    # once each, in alphabetical order.
    folder = tmp_path / 'courtlistener'
    write_case(folder, make_cluster(
        4, case_name_full = 'NATIONAL LABOR RELATIONS BOARD, Petitioner, v. ACME CORP., Respondent',
        procedural_history = 'On application for enforcement of an order of the NLRB.'),
        [make_opinion(41, 4, html_with_citations = (
            '<p>The Board relied on a ruling of the IRS. The NLRB is right.</p>'))])
    write_case(folder, make_cluster(5), [make_opinion(51, 5)])
    table = courtpy.parse(folder)
    assert table.loc['4', 'agencies'] == 'Internal Revenue Service; National Labor Relations Board'
    assert pd.isna(table.loc['5', 'agencies'])


def test_missing_values_get_nullable_types() -> None:
    data = pd.DataFrame({'published': [True, None], 'year': [2020.0, None], 'x': ['a', None]})
    tidied = cases.tidy(data)
    assert tidied['published'].dtype == 'boolean'
    assert tidied['year'].dtype == 'Int64'
    assert tidied['x'].dtype != 'boolean'


def test_find_files_skips_hidden_folders(court_listener_folder: pathlib.Path) -> None:
    hidden = court_listener_folder / '.courtpy'
    hidden.mkdir()
    (hidden / 'state.json').write_text('{}', encoding = 'utf-8')
    assert len(parsers.find_files(court_listener_folder)) == 3
    with pytest.raises(ValueError, match = 'source must be one of'):
        parsers.find_files(court_listener_folder, 'westlaw')


def test_unreadable_case_is_skipped(
    court_listener_folder: pathlib.Path,
    caplog: pytest.LogCaptureFixture) -> None:
    (court_listener_folder / 'ca1' / '9.json').write_text('not json', encoding = 'utf-8')
    with caplog.at_level(logging.WARNING):
        table = courtpy.parse(court_listener_folder)
    assert len(table) == 3
    assert 'could not be parsed' in caplog.text


def test_parse_with_workers(court_listener_folder: pathlib.Path) -> None:
    table = courtpy.parse(court_listener_folder, workers = 2)
    assert list(table.index) == ['1', '2', '3']


def test_chunked_workers_match_one_process(
    court_listener_folder: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture) -> None:
    # With chunks of two cases, the four cases (one unreadable) are two
    # tasks for the pool, and the table is the same as with one process.
    (court_listener_folder / 'ca1' / '9.json').write_text('not json', encoding = 'utf-8')
    monkeypatch.setattr(options, '_CHUNK_SIZE', 2)
    serial = courtpy.parse(court_listener_folder, workers = 1)
    with caplog.at_level(logging.INFO, logger = 'courtpy.wrangler.parsers'):
        chunked = courtpy.parse(court_listener_folder, workers = 2)
    pd.testing.assert_frame_equal(chunked, serial)
    assert list(chunked.index) == ['1', '2', '3']
    assert '2 of 4 cases parsed' in caplog.text
    assert '4 of 4 cases parsed' in caplog.text
    assert 'could not be parsed' in caplog.text


def test_custom_rulebook(court_listener_folder: pathlib.Path, tmp_path: pathlib.Path) -> None:
    rules = tmp_path / 'mine.csv'
    rules.write_text(
        'target,variable,kind,pattern,value,ignorecase,dotall,note\n'
        'opinion,mentions_firearm,flag,firearm,,TRUE,FALSE,\n'
        'opinion,we_count,count,\\bwe\\b,,TRUE,FALSE,\n', encoding = 'utf-8')
    table = courtpy.parse(court_listener_folder, rulebooks = [rules])
    assert table.loc['1', 'mentions_firearm'] and not table.loc['2', 'mentions_firearm']
    assert table.loc['1', 'we_count'] == 2
    assert 'party1_appellant' in table.columns and 'decision' in table.columns
    assert 'criminal_firearm' not in table.columns


def test_save_and_load(court_listener_folder: pathlib.Path, tmp_path: pathlib.Path) -> None:
    table = courtpy.parse(court_listener_folder)
    path = tmp_path / 'out' / 'cases.csv'
    saved = courtpy.Cases.create(table).save(path)
    assert saved == [path.with_suffix('.joblib'), path]
    # Nothing else is made beside the files.
    assert sorted(p.name for p in path.parent.iterdir()) == ['cases.csv', 'cases.joblib']
    loaded = courtpy.Cases.load(path).data
    assert list(loaded.index) == ['1', '2', '3']
    assert loaded.loc['1', 'panel_judges'] == 'LYNCH; HOWARD; THOMPSON'
    assert pd.isna(loaded.loc['3', 'dissenting'])
    # Lists that `split_values` makes are saved as text, as the rules write
    # them, in the table and in the dataset.
    listed = courtpy.code(table, 'split_values')
    listed.save(tmp_path / 'lists.parquet')
    assert listed.data.loc['1', 'panel_judges'] == ['LYNCH', 'HOWARD', 'THOMPSON']
    for name in ('lists.parquet', 'lists.joblib'):
        loaded = courtpy.Cases.load(tmp_path / name).data
        assert loaded.loc['1', 'panel_judges'] == 'LYNCH; HOWARD; THOMPSON'
        assert pd.api.types.is_bool_dtype(loaded['published'].dtype)
        pd.testing.assert_series_equal(loaded['court_num'], table['court_num'], check_dtype = False)
    assert listed.history[-1]['technique'] == 'save_data'
    with pytest.raises(ValueError, match = 'must end in'):
        listed.save(tmp_path / 'lists.txt')
    with pytest.raises(TypeError, match = 'holds Cases'):
        courtpy.Votes.load(tmp_path / 'lists.joblib')


def test_parser_metadata_wins(court_listener_folder: pathlib.Path) -> None:
    parser = parsers.Parser.create('federal')
    case = cases.Case(
        id = 'x', source = 'courtlistener',
        sections = {'court': 'Court of Appeals for the First Circuit'},
        metadata = {'court_num': 99, 'agency': None})
    row = parser.parse(case)
    assert row['court_num'] == 99
    assert row['agency'] is None
    assert row['word_count'] == 0


def test_parse_recent_court_listener(recent_folder: pathlib.Path) -> None:
    # CourtListener has no full case name, judges, or disposition for the
    # case, so they are read from its opinion.
    table = courtpy.parse(recent_folder)
    doe = table.loc['4']
    assert pd.isna(doe['judges']) and pd.isna(doe['disposition'])
    assert doe['caption'] == 'Appellee, versus JOHN DOE, Defendant-Appellant'
    assert doe['party2_appellant'] and doe['party1_appellee']
    assert not doe['party1_appellant'] and not doe['party2_appellee']
    assert doe['panel_judges'] == 'LYNCH; HOWARD; R THOMPSON'
    assert doe['panel_size'] == 3
    assert doe['decision'] == 'AFFIRMED'
    assert doe['decision_affirm'] and not doe['decision_reverse']
    assert doe['opinion_reverse'] and not doe['disposition_affirm']
    assert 'opening_lines' not in table.columns
    coded = courtpy.code(table).data.loc['4']
    assert coded['type_criminal'] and coded['appeal_by_defendant']
    assert not coded['outcome_reversal']
    assert not coded['outcome_criminal_defendant_won']


def test_keep_text_keeps_every_section(court_listener_folder: pathlib.Path) -> None:
    table = courtpy.parse(court_listener_folder, keep_text = True)
    for section in ('party', 'history', 'judges', 'opinion_by', 'opinion'):
        assert section in table.columns
    assert table.loc['2', 'party'].startswith('Mary SMITH')
    # The court's id from CourtListener's data is kept, not its name.
    assert table.loc['1', 'court'] == 'ca1'
    assert 'opinion' not in courtpy.parse(court_listener_folder).columns


def test_parse_all_is_amos_parse_all() -> None:
    assert amos.library.borrow('parse_all') is parsers.ParseAll
    assert issubclass(parsers.ParseAll, amos.parsers.ParseAll)


def test_parse_all_parses_kept_text_again(court_listener_folder: pathlib.Path) -> None:
    table = courtpy.parse(court_listener_folder, keep_text = True)
    dropped = ['panel_judges', 'party1_appellant', 'disposition_affirm', 'author', 'citations_case']
    again = parsers.ParseAll().parse(table.drop(columns = dropped))
    assert set(again.columns) == set(table.columns)
    for column in [*dropped, 'court_num', 'court_name', 'word_count', 'panel_size']:
        pd.testing.assert_series_equal(
            again[column], table[column], check_dtype = False, check_names = False)


def test_parse_all_applies_rulebooks(court_listener_folder: pathlib.Path, tmp_path: pathlib.Path) -> None:
    rules = tmp_path / 'heller.csv'
    rules.write_text('column,name,kind,pattern\nopinion,cites_heller,flags,554 U\\.S\\. 570\n', encoding = 'utf-8')
    table = courtpy.parse(court_listener_folder, keep_text = True)
    again = parsers.ParseAll().parse(table, rulebooks = [str(rules)])
    assert again['cites_heller'].tolist() == [True, False, False]
    # Only the header rules, "general", and the rulebooks named are applied.
    assert 'citations_case' in again.columns and 'cites_heller' not in table.columns


def test_parse_all_with_rules_is_amos_parse_all(court_listener_folder: pathlib.Path) -> None:
    table = courtpy.parse(court_listener_folder)
    rules = [{'column': 'case_name', 'name': 'doe', 'kind': 'flags', 'pattern': 'Doe'}]
    found = parsers.ParseAll().parse(table, rules = rules)
    assert found['doe'].tolist() == [True, False, False]
    assert list(found.columns) == [*table.columns, 'doe']


def test_parse_all_needs_kept_text(court_listener_folder: pathlib.Path) -> None:
    with pytest.raises(ValueError, match = 'keep_text'):
        parsers.ParseAll().parse(courtpy.parse(court_listener_folder))
