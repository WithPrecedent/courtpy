"""Tests the courts module."""

from __future__ import annotations

import pandas as pd

from courtpy import courts


def test_federal_courts() -> None:
    table = courts.federal_courts()
    assert list(table.columns) == [
        'court_num', 'court', 'level', 'circuit_num', 'courtlistener', 'fjc_name', 'opinion_name']
    assert table['court'].is_unique
    assert set(table['level']) == {'supreme', 'appellate', 'district', 'specialty'}
    appeals = table[table['courtlistener'].str.fullmatch(r'ca\d+|cadc|cafc', na = False)]
    assert sorted(appeals['court_num']) == list(range(1, 14))
    # Every district court has a circuit, and every current one an id.
    districts = table[table['level'] == 'district']
    assert districts['circuit_num'].notna().all()
    by_id = table.dropna(subset = ['courtlistener']).set_index('courtlistener')
    assert by_id.loc['nysd', 'circuit_num'] == 2
    assert by_id.loc['dcd', 'circuit_num'] == 12
    assert by_id.loc['cand', 'circuit_num'] == 9
    assert by_id.loc['txsd', 'opinion_name'] == r'SOUTHERN DISTRICT OF TEXAS|S\.D\. TEX\.'
    # A copy is returned each time.
    table.loc[0, 'court'] = 'changed'
    assert courts.federal_courts().loc[0, 'court'] != 'changed'


def test_circuits() -> None:
    cases = pd.DataFrame({
        'court': ['ca5', 'NYSD', None, 'scotus', 'nowhere'],
        'court_num': pd.array([5, pd.NA, 12, 99, pd.NA], dtype = 'Int64')})
    assert courts.circuits(cases).tolist() == [5, 2, 12, pd.NA, pd.NA]
    assert courts.circuits(cases[['court_num']]).tolist() == [5, pd.NA, 12, pd.NA, pd.NA]
