"""Tests the courts module."""

from __future__ import annotations

import pandas as pd
import pytest

from courtpy import courts


def test_federal_courts() -> None:
    table = courts.federal_courts()
    assert list(table.columns) == [
        'court_num', 'court', 'feature_name', 'level', 'circuit_num', 'courtlistener_name',
        'fjc_name', 'opinion_name']
    assert table['court'].is_unique
    assert set(table['level']) == {'high', 'appellate', 'trial', 'specialty'}
    appeals = table[table['courtlistener_name'].str.fullmatch(r'ca\d+|cadc|cafc', na = False)]
    assert sorted(appeals['court_num']) == list(range(1, 14))
    # Every trial court has a circuit, and every current one an id.
    districts = table[table['level'] == 'trial']
    assert districts['circuit_num'].notna().all()
    by_id = table.dropna(subset = ['courtlistener_name']).set_index('courtlistener_name')
    assert by_id.loc['nysd', 'circuit_num'] == 2
    assert by_id.loc['dcd', 'circuit_num'] == 12
    assert by_id.loc['cand', 'circuit_num'] == 9
    assert by_id.loc['scotus', 'court'] == 'scotus'
    assert by_id.loc['scotus', 'feature_name'] == 'SCOTUS'
    assert by_id.loc['bap9', 'court_num'] == 110
    assert by_id.loc['nysd', 'feature_name'] == 'Southern District of New York'
    assert by_id.loc['txsd', 'opinion_name'].startswith('SOUTHERN DISTRICT OF TEXAS|')
    # A copy is returned each time.
    table.loc[0, 'court'] = 'changed'
    assert courts.federal_courts().loc[0, 'court'] != 'changed'


def test_court_table() -> None:
    assert courts.court_table('federal').equals(courts.federal_courts())
    with pytest.raises(FileNotFoundError, match = 'nowhere'):
        courts.court_table('nowhere')


def test_courtlistener_lookups() -> None:
    numbers = courts.court_numbers_by_courtlistener_name()
    names = courts.court_names_by_courtlistener_name()
    assert (numbers['ca1'], names['ca1']) == (1, 'first_circuit')
    assert (numbers['scotus'], names['scotus']) == (99, 'scotus')
    assert (numbers['mad'], names['mad']) == (1026, 'district_of_massachusetts')
    assert 'nowhere' not in numbers
    with pytest.raises(TypeError):
        numbers['ca1'] = 2  # type: ignore[index]


def test_circuits() -> None:
    cases = pd.DataFrame({
        'court': ['ca5', 'NYSD', None, 'scotus', 'nowhere'],
        'court_num': pd.array([5, pd.NA, 12, 99, pd.NA], dtype = 'Int64')})
    assert courts.circuits(cases).tolist() == [5, 2, 12, pd.NA, pd.NA]
    assert courts.circuits(cases[['court_num']]).tolist() == [5, pd.NA, 12, pd.NA, pd.NA]


def test_court_labels() -> None:
    cases = pd.DataFrame({
        'court_name': ['tenth_circuit', None, 'dc_circuit', None, None],
        'court_num': [10, 9, 12, 1026, None]})
    labels = courts.court_labels(cases)
    assert labels.tolist()[:4] == [
        'Tenth Circuit', 'Ninth Circuit', 'D.C. Circuit', 'District of Massachusetts']
    assert pd.isna(labels.iloc[4])
    # The categories are the courts of the cases, in the table's order.
    assert list(labels.cat.categories) == [
        'Ninth Circuit', 'Tenth Circuit', 'D.C. Circuit', 'District of Massachusetts']
    assert courts.court_labels(cases[['court_num']]).tolist()[:3] == [
        'Tenth Circuit', 'Ninth Circuit', 'D.C. Circuit']
    with pytest.raises(KeyError, match = 'labeled'):
        courts.court_labels(pd.DataFrame({'year': [2008]}))
