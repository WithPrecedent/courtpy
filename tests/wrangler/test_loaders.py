"""Tests the loaders module."""

from __future__ import annotations

import pathlib

import amos
import nagata
import pandas as pd
import pytest

import courtpy
from courtpy import loaders

FIXTURES = pathlib.Path(__file__).parents[1] / 'fixtures'


def test_loaders_are_in_the_library() -> None:
    assert sorted(amos.library.get_genre('case_loader')) == [
        'load_cases', 'source_loader']
    assert sorted(amos.library.get_genre('source_loader')) == [
        'download_courtlistener', 'load_courtlistener', 'load_lexis_nexis']
    assert issubclass(loaders.LoadCourtlistener, amos.Loader)


def test_load_courtlistener(court_listener_folder: pathlib.Path) -> None:
    dataset = loaders.LoadCourtlistener().apply(
        None, source = court_listener_folder, label = 'outcome_reversal')
    assert dataset.label == 'outcome_reversal'
    assert dataset.task == 'classify'
    assert len(dataset.data) == 3
    assert [e['technique'] for e in dataset.history] == [
        'load_courtlistener', 'code_parties', 'code_case_type', 'code_outcome']
    assert dataset.history[0]['rows'] == 3


def test_coders_none(court_listener_folder: pathlib.Path) -> None:
    dataset = loaders.LoadCourtlistener().apply(
        None, source = court_listener_folder, coders = 'none')
    assert 'outcome_reversal' not in dataset.data.columns
    pending = loaders.LoadCourtlistener().apply(
        None, source = court_listener_folder, coders = 'none',
        label = 'outcome_reversal')
    assert pending.label == 'outcome_reversal'
    assert not pending.has_label
    with pytest.raises(ValueError, match = 'label'):
        pending.require_label()


def test_save_and_reuse(court_listener_folder: pathlib.Path, tmp_path: pathlib.Path) -> None:
    clerk = nagata.FileManager(root_folder = tmp_path, interim_folder = 'interim')
    loader = loaders.LoadCourtlistener(clerk = clerk)
    loader.apply(None, source = court_listener_folder, save = 'cases.csv')
    saved = pathlib.Path(clerk.interim_folder) / 'cases.csv'
    whole = saved.with_suffix('.joblib')
    assert saved.is_file() and whole.is_file()
    reused = loader.apply(
        None, source = tmp_path / 'missing', save = 'cases.csv', reuse = 'true',
        label = 'outcome_reversal')
    assert isinstance(reused, courtpy.Cases)
    # The saved dataset goes on from where it was saved, history and all.
    assert reused.history[-1]['reused'] == str(whole)
    assert [e['technique'] for e in reused.history] == [
        'load_courtlistener', 'code_parties', 'code_case_type', 'code_outcome', 'save_data',
        'load_courtlistener']
    assert reused.data.loc['1', 'panel_judges'] == 'LYNCH; HOWARD; THOMPSON'
    # Without the joblib file, the table is reused.
    whole.unlink()
    reused = loader.apply(None, source = tmp_path / 'missing', save = 'cases.csv', reuse = 'true')
    assert isinstance(reused, courtpy.Cases)
    assert reused.history[-1]['reused'] == str(saved)
    assert reused.data.loc['1', 'panel_judges'] == 'LYNCH; HOWARD; THOMPSON'


def test_project_with_a_loader(court_listener_folder: pathlib.Path, tmp_path: pathlib.Path) -> None:
    folder = tmp_path / 'data' / 'courtlistener'
    folder.parent.mkdir()
    court_listener_folder.rename(folder)
    settings = {
        'general': {'seed': 43, 'label': 'outcome_reversal'},
        'files': {'input_folder': 'data'},
        'appeals_project': {'appeals_workers': 'wrangler, explorer'},
        'wrangler': {'techniques': 'load_courtlistener, drop_text_columns'},
        'explorer': {'techniques': 'summarize, label_balance'}}
    project = courtpy.Project.create(settings, clerk = tmp_path)
    result = project.result
    assert result.label == 'outcome_reversal'
    assert result.history[0] == {
        'technique': 'load_courtlistener', 'source': 'courtlistener',
        'rows': 3, 'columns': result.history[0]['columns']}
    assert 'party1' not in result.data.columns
    assert set(result.tables) == {'summarize', 'label_balance'}


def test_amos_parsers_search_kept_text(court_listener_folder: pathlib.Path, tmp_path: pathlib.Path) -> None:
    folder = tmp_path / 'data' / 'courtlistener'
    folder.parent.mkdir()
    court_listener_folder.rename(folder)
    settings = tmp_path / 'coding.toml'
    settings.write_text(
        '[files]\n'
        'input_folder = "data"\n'
        '[coding_project]\n'
        'coding_workers = "wrangler"\n'
        '[wrangler]\n'
        'techniques = "load_courtlistener, parse_flags, parse_counts, drop_text_columns"\n'
        '[load_courtlistener_parameters]\n'
        'keep_text = true\n'
        '[parse_flags_parameters]\n'
        'column = "opinion"\n'
        'name = "affirmed"\n'
        "pattern = 'we affirm'\n"
        'flags = "ignorecase"\n'
        '[parse_counts_parameters]\n'
        'column = "opinion"\n'
        'name = "title_vii"\n'
        "pattern = '\\bTitle VII\\b'\n",
        encoding = 'utf-8')
    result = courtpy.Project.create(settings, clerk = tmp_path).result
    assert [e['technique'] for e in result.history] == [
        'load_courtlistener', 'code_parties', 'code_case_type', 'code_outcome',
        'parse_flags', 'parse_counts', 'drop_text_columns']
    assert result.data.loc['2', 'affirmed']
    assert result.data.loc['2', 'title_vii'] == 1
    assert 'opinion' not in result.data.columns


def test_parse_all_in_a_wrangler(court_listener_folder: pathlib.Path, tmp_path: pathlib.Path) -> None:
    folder = tmp_path / 'data' / 'courtlistener'
    folder.parent.mkdir()
    court_listener_folder.rename(folder)
    rules = tmp_path / 'heller.csv'
    rules.write_text('column,name,kind,pattern\nopinion,cites_heller,flags,554 U\\.S\\. 570\n', encoding = 'utf-8')
    settings = tmp_path / 'reparse.toml'
    settings.write_text(
        '[files]\n'
        'input_folder = "data"\n'
        '[reparse_project]\n'
        'reparse_workers = "wrangler"\n'
        '[wrangler]\n'
        'techniques = "load_courtlistener, parse_all, drop_text_columns"\n'
        '[load_courtlistener_parameters]\n'
        'keep_text = true\n'
        '[parse_all_parameters]\n'
        f'rulebooks = "federal, {rules.as_posix()}"\n',
        encoding = 'utf-8')
    result = courtpy.Project.create(settings, clerk = tmp_path).result
    assert [e['technique'] for e in result.history][-2:] == ['parse_all', 'drop_text_columns']
    assert result.data.loc['1', 'cites_heller'] and not result.data.loc['2', 'cites_heller']
    assert 'opinion' not in result.data.columns


def test_no_cases(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match = 'no courtlistener cases were found'):
        loaders.LoadCourtlistener().apply(None, source = tmp_path)


def test_download_courtlistener(
    court_listener_folder: pathlib.Path,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def record(self: courtpy.CourtListener, *args: object, **kwargs: object) -> list[pathlib.Path]:
        calls.append((self, args, kwargs))
        return []

    monkeypatch.setattr(courtpy.CourtListener, 'download', record)
    monkeypatch.chdir(tmp_path)
    loader = loaders.DownloadCourtlistener()
    dataset = loader.apply(
        None, source = court_listener_folder, courts = 'ca1, ca2',
        start_date = '2020-01-01 00:00:00', bulk_date = '2026-09-30', max_cases = '5',
        refresh = 'yes', bulk_folder = 'bulk_files', rulebooks = 'federal')
    assert len(dataset.data) == 3
    assert dataset.history[0]['technique'] == 'download_courtlistener'
    client, args, kwargs = calls[0]
    assert client.bulk_date == '2026-09-30'
    assert client.bulk_folder == pathlib.Path(loader._get_clerk().input_folder) / 'bulk_files'
    assert args == ('ca1, ca2', '2020-01-01', None, court_listener_folder)
    assert kwargs == {
        'method': 'bulk', 'max_cases': 5, 'dockets': False, 'refresh': True}


def test_download_courtlistener_fails_clearly(court_listener_folder: pathlib.Path) -> None:
    with pytest.raises(ValueError, match = 'method must be'):
        loaders.DownloadCourtlistener().apply(
            None, source = court_listener_folder, method = 'ftp', courts = 'ca1')
    with pytest.raises(ValueError, match = 'name at least one court'):
        loaders.DownloadCourtlistener().apply(None, source = court_listener_folder)
    with pytest.raises(courtpy.secrets.MissingAPIKeyError):
        loaders.DownloadCourtlistener().apply(
            None, source = court_listener_folder, method = 'api', courts = 'ca1')


def test_load_lexis_nexis(tmp_path: pathlib.Path) -> None:
    dataset = loaders.LoadLexisNexis().apply(
        None, source = tmp_path / 'lexis', batches = str(FIXTURES))
    assert len(dataset.data) == 2
    assert len(list((tmp_path / 'lexis').glob('*.txt'))) == 2
    assert dataset.data.loc['lexis_batch_00001', 'outcome_reversal']


def test_load_cases(court_listener_folder: pathlib.Path, tmp_path: pathlib.Path) -> None:
    coded = courtpy.code(courtpy.parse(court_listener_folder))
    path = tmp_path / 'cases.csv'
    coded.save(path)
    path.with_suffix('.joblib').unlink()
    dataset = loaders.LoadCases().apply(None, source = path, label = 'outcome_reversal')
    assert isinstance(dataset, courtpy.Cases)
    assert [e['technique'] for e in dataset.history] == ['load_cases']
    assert dataset.data.loc['1', 'panel_judges'] == 'LYNCH; HOWARD; THOMPSON'
    # A saved dataset of votes is votes again.
    votes = courtpy.Votes.create(pd.DataFrame({'vote_id': ['1-1'], 'case_id': ['1'], 'judge': ['LYNCH']}))
    votes.save(tmp_path / 'votes.joblib')
    loaded = loaders.LoadCases().apply(None, source = tmp_path / 'votes.joblib')
    assert isinstance(loaded, courtpy.Votes)
    assert list(loaded.data.index) == ['1-1']
    with pytest.raises(ValueError, match = 'has nothing to load'):
        loaders.LoadCases().apply(None)
    with pytest.raises(FileNotFoundError, match = 'no file of'):
        loaders.LoadCases().apply(None, source = tmp_path / 'missing.csv')
