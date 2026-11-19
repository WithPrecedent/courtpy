"""Tests the shapers module."""

from __future__ import annotations

import amos
import pandas as pd
import pytest

import courtpy
from courtpy import shapers


def coded() -> courtpy.Cases:
    """Returns cases with case types, parties' types, and outcomes."""
    data = pd.DataFrame({
        'case_id': ['1', '2', '3', '4'],
        'court_num': [1, 1, 2, 2],
        'court': ['ca1', 'ca1', 'ca2', 'ca2'],
        'year': [2019, 2020, 2020, 2020],
        'docket_number': ['19-1', '20-2', '20-3', '20-4'],
        'type_criminal': [True, False, False, False],
        'type_civil': [False, True, True, True],
        'type_tort': [False, True, False, True],
        'type_contract': [False, True, True, False],
        'party1_type': ['government', 'individual', 'corporation', 'individual'],
        'party2_type': ['individual', 'corporation', 'corporation', None],
        'party1_appealing': [False, True, True, False],
        'party2_appealing': [True, False, False, True],
        'outcome_party1_won': [True, False, True, False],
        'outcome_party2_won': [False, True, False, True],
        'outcome_reversal': [False, True, False, True],
        'judge_nid1': pd.array([101, 101, 201, 202], dtype = 'Int64'),
        'judge_nid2': pd.array([102, 103, 202, pd.NA], dtype = 'Int64')})
    return courtpy.Cases.create(data)


def test_shapers_are_in_the_library() -> None:
    for name in ('cases_to_courts', 'cases_to_case_types', 'cases_to_party_types', 'cases_to_dockets', 'dockets_to_cases'):
        assert amos.library.classify(name) == 'shaper'


def test_cases_to_courts() -> None:
    dataset = shapers.CasesToCourts().apply(coded(), label = 'outcome_reversal')
    assert isinstance(dataset, courtpy.Courts)
    table = dataset.data
    assert table.index.name == 'court_num' and list(table.index) == [1, 2]
    assert list(table['cases']) == [2, 2]
    assert list(table['judges']) == [3, 2]
    assert list(table['type_criminal']) == [0.5, 0.0]
    assert list(table['type_tort']) == [0.5, 0.5]
    assert list(table['party_type_corporation']) == [0.5, 0.5]
    assert list(table['outcome_reversal']) == [0.5, 0.5]
    # Nothing about any one case is kept.
    assert not {'docket_number', 'court', 'case_id', 'judge_nid1', 'party1_type'} & set(table.columns)
    assert (dataset.label, dataset.groups) == ('outcome_reversal', [])
    # "by" makes a row for each court in each year, and "keep" keeps text.
    by_year = shapers.CasesToCourts().shape(coded().data, by = 'year', keep = 'court')
    assert list(by_year.index) == [(1, 2019), (1, 2020), (2, 2020)]
    assert list(by_year['court']) == ['ca1', 'ca1', 'ca2']
    with pytest.raises(KeyError, match = 'no_such'):
        shapers.CasesToCourts().shape(coded().data, court = 'no_such')


def test_cases_to_case_types() -> None:
    dataset = shapers.CasesToCaseTypes().apply(coded())
    assert isinstance(dataset, courtpy.CaseTypes)
    table = dataset.data
    assert table.index.name == 'case_type'
    # A case of several types counts for each of them.
    assert table['cases'].to_dict() == {'criminal': 1, 'civil': 3, 'tort': 2, 'contract': 2}
    assert table.loc['tort', 'outcome_reversal'] == 1.0
    assert table.loc['civil', 'party_type_individual'] == pytest.approx(2 / 3)
    assert 'docket_number' not in table
    by_court = shapers.CasesToCaseTypes().shape(coded().data, by = 'court_num')
    assert by_court.loc[('civil', 2), 'cases'] == 2
    with pytest.raises(KeyError, match = 'code_case_type'):
        shapers.CasesToCaseTypes().shape(pd.DataFrame({'x': [1]}))


def test_cases_to_party_types() -> None:
    dataset = shapers.CasesToPartyTypes().apply(coded())
    assert isinstance(dataset, courtpy.PartyTypes)
    table = dataset.data
    assert table.index.name == 'party_type'
    # Each party is a row: three individuals, three corporations, and one
    # government (the missing type is left out).
    assert table['parties'].to_dict() == {'government': 1, 'individual': 3, 'corporation': 3}
    assert table.loc['individual', 'party_won'] == 0.0
    assert table.loc['corporation', 'party_won'] == pytest.approx(2 / 3)
    assert table.loc['government', 'party_appealing'] == 0.0
    assert table.loc['corporation', 'type_contract'] == 1.0
    assert 'party1_appealing' not in table and 'docket_number' not in table
    with pytest.raises(KeyError, match = 'party1_type'):
        shapers.CasesToPartyTypes().shape(pd.DataFrame({'x': [1]}))


def test_add_party_type_flags() -> None:
    flags = shapers.add_party_type_flags(coded().data)
    assert list(flags['party_type_government']) == [True, False, False, False]
    plain = pd.DataFrame({'x': [1]})
    assert shapers.add_party_type_flags(plain) is plain


def test_summarize() -> None:
    data = pd.DataFrame({
        'group': ['a', 'a', 'b'], 'x': [1.0, 3.0, 5.0], 'flag': [True, False, True],
        'case_id': [1, 2, 3], 'name': ['p', 'q', 'r']})
    table = shapers.summarize(data, ['group'], count = 'n')
    assert list(table.columns) == ['x', 'flag', 'n']
    assert list(table['x']) == [2.0, 5.0] and list(table['flag']) == [0.5, 1.0]
    listed = shapers.summarize(data, ['group'], how = {'name': 'list'}, keep = 'name')
    assert listed.loc['a', 'name'] == ['p', 'q']


def test_cases_to_dockets_and_back() -> None:
    data = pd.DataFrame({
        'case_id': ['a', 'b', 'c', 'd'],
        'docket_numbers': ['17-1; 17-2', '18-5', None, ['19-7', '19-8']],
        'docket_number': ['Nos. 17-1, 17-2', '18-5', None, '19-7'],
        'docket_id': [10, 20, 30, 40],
        'x': [1, 2, 3, 4]})
    cases = courtpy.Cases.create(data.copy())
    dockets = shapers.CasesToDockets().apply(cases, groups = 'case_id', label = 'x')
    assert isinstance(dockets, courtpy.Dockets)
    table = dockets.data
    assert table.index.name == 'case_docket'
    assert list(table.index) == ['a-1', 'a-2', 'b-1', 'c-1', 'd-1', 'd-2']
    assert list(table.columns[:2]) == ['case_id', 'docket']
    assert list(table['docket'].fillna('')) == ['17-1', '17-2', '18-5', '', '19-7', '19-8']
    # Each row has only its own docket number.
    assert 'docket_numbers' not in table
    assert list(table['x']) == [1, 1, 2, 3, 4, 4]
    # CourtListener's id for the docket of each case is kept.
    assert list(table['docket_id']) == [10, 10, 20, 30, 40, 40]
    assert (dockets.label, dockets.groups) == ('x', ['case_id'])
    back = shapers.DocketsToCases().apply(dockets)
    assert isinstance(back, courtpy.Cases)
    assert list(back.data.index) == ['a', 'b', 'c', 'd']
    assert list(back.data['docket_numbers'].fillna('')) == ['17-1; 17-2', '18-5', '', '19-7; 19-8']
    assert back.groups == [] and 'docket' not in back.data
    assert list(back.data['docket_id']) == [10, 20, 30, 40]
    # Without "docket_numbers", the numbers in "docket_number" are used.
    from_text = shapers.CasesToDockets().shape(data.drop(columns = 'docket_numbers').set_index('case_id'))
    assert list(from_text['docket'].iloc[:2]) == ['17-1', '17-2']
    with pytest.raises(KeyError, match = 'docket_numbers'):
        shapers.CasesToDockets().shape(pd.DataFrame({'x': [1]}, index = pd.Index(['a'], name = 'case_id')))
    with pytest.raises(KeyError, match = 'case_id'):
        shapers.DocketsToCases().shape(pd.DataFrame({'x': [1]}))
