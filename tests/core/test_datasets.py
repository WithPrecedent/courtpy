"""Tests the datasets module."""

from __future__ import annotations

import pathlib

import amos
import pandas as pd
import pytest

import courtpy
from courtpy import datasets


def table() -> pd.DataFrame:
    """Returns a small table of cases, labeled by their ids."""
    return pd.DataFrame({
        'year': [2019, 2020],
        'published': [True, None],
        'panel_judges': [['LYNCH', 'HOWARD'], []]}, index = pd.Index(['1', '2'], name = 'case_id'))


def test_each_kind_has_its_key() -> None:
    keys = {
        courtpy.Cases: 'case_id', courtpy.Dockets: 'case_docket', courtpy.Votes: 'vote_id', courtpy.Judges: 'judge_nid',
        courtpy.Courts: 'court_num', courtpy.CaseTypes: 'case_type', courtpy.PartyTypes: 'party_type'}
    for kind, key in keys.items():
        assert issubclass(kind, amos.Dataset) and kind.key == key


def test_adopt_and_create() -> None:
    plain = amos.Dataset(table().reset_index(), label = 'year', seed = 7)
    plain.record('something')
    cases = courtpy.Cases.adopt(plain)
    assert isinstance(cases, courtpy.Cases)
    # It keeps everything, and its key labels the rows.
    assert (cases.label, cases.seed, cases.history) == ('year', 7, plain.history)
    assert list(cases.data.index) == ['1', '2'] and cases.data.index.name == 'case_id'
    assert courtpy.Cases.adopt(cases) is cases
    votes = courtpy.Votes.adopt(cases)
    assert isinstance(votes, courtpy.Votes) and votes.data is cases.data
    created = courtpy.Cases.create(table(), label = 'year')
    assert isinstance(created, courtpy.Cases) and created.label == 'year'


def test_save_and_load(tmp_path: pathlib.Path) -> None:
    cases = courtpy.Cases.create(table())
    paths = cases.save(tmp_path / 'nested' / 'cases.csv')
    assert [p.name for p in paths] == ['cases.joblib', 'cases.csv']
    assert sorted(p.name for p in (tmp_path / 'nested').iterdir()) == ['cases.csv', 'cases.joblib']
    assert cases.history[-1]['technique'] == 'save_data'
    # Lists are saved as text, as the rules write them, and the table's
    # labels and types come back.
    loaded = courtpy.Cases.load(tmp_path / 'nested' / 'cases.csv')
    assert list(loaded.data.index) == ['1', '2']
    assert list(loaded.data['panel_judges'].fillna('')) == ['LYNCH; HOWARD', '']
    assert loaded.data['published'].dtype == 'boolean'
    # The joblib file holds the whole dataset, of its kind.
    whole = courtpy.Cases.load(tmp_path / 'nested' / 'cases.joblib')
    assert whole.history[-1]['technique'] == 'save_data'
    assert courtpy.CourtData.load(tmp_path / 'nested' / 'cases.joblib').__class__ is courtpy.Cases
    # Saving to a joblib file saves no table.
    assert [p.name for p in cases.save(tmp_path / 'only.joblib')] == ['only.joblib']
    with pytest.raises(FileNotFoundError, match = 'no file of Votes'):
        courtpy.Votes.load(tmp_path / 'missing.csv')
    with pytest.raises(TypeError, match = 'courtpy.Cases.load'):
        courtpy.Judges.load(tmp_path / 'only.joblib')


def test_join_lists_leaves_other_tables_alone() -> None:
    data = pd.DataFrame({'x': [1, 2]})
    assert datasets._join_lists(data) is data
