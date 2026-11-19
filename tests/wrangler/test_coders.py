"""Tests the coders module."""

from __future__ import annotations

import pathlib

import amos
import pandas as pd
import pytest

import courtpy
from courtpy import coders


@pytest.fixture
def coded(court_listener_folder: pathlib.Path) -> amos.Dataset:
    return courtpy.code(courtpy.parse(court_listener_folder))


def test_coders_are_in_the_library() -> None:
    for name in ('code_parties', 'code_case_type', 'code_outcome'):
        assert amos.library.classify(name) == 'munger'
    assert amos.library.classify('drop_text_columns') == 'cleaner'


def test_mungers_record_their_columns(coded: amos.Dataset) -> None:
    parties, case_type, outcome = coded.history
    assert {'party1_appealing', 'party2_defending'} <= set(parties['created'])
    assert 'type_criminal' in case_type['created']
    assert outcome['created'][0] == 'outcome_reversal'


def test_code_parties(coded: amos.Dataset) -> None:
    data = coded.data
    assert data.loc['1', 'party2_appealing'] and data.loc['1', 'party1_defending']
    assert data.loc['2', 'party1_appealing'] and data.loc['2', 'party2_defending']
    assert not data.loc['3', 'party1_appealing'] and not data.loc['3', 'party1_defending']
    assert [entry['technique'] for entry in coded.history] == [
        'code_parties', 'code_case_type', 'code_outcome']


def test_code_parties_completes_opposites() -> None:
    roles = ['appellant', 'appellee', 'petitioner', 'respondent', 'plaintiff', 'defendant']
    data = pd.DataFrame({f'{s}_{r}': [False] for s in ('party1', 'party2') for r in roles})
    data['party2_appellant'] = True
    data['party1_plaintiff'] = True
    result = coders.CodeParties().apply(amos.Dataset(data)).data
    assert result.loc[0, 'party1_appellee'] and result.loc[0, 'party2_defendant']
    assert result.loc[0, 'party2_appealing'] and result.loc[0, 'party1_defending']


def test_code_case_type(coded: amos.Dataset) -> None:
    data = coded.data
    assert list(data['type_criminal']) == [True, False, False]
    assert data.loc['1', 'party1_prosecution'] and data.loc['1', 'party2_criminal_defendant']
    assert data.loc['2', 'party1_civil_plaintiff'] and data.loc['2', 'party2_civil_defendant']
    # Every case that is not criminal is civil, and each other prefix of the
    # rules of the topics of cases is a type too.
    assert list(data['type_civil']) == [False, True, True]
    assert isinstance(coded, courtpy.Cases)
    types = [c for c in data.columns if c.startswith('type_')]
    assert types[:2] == ['type_criminal', 'type_civil']
    assert {'type_tort', 'type_contract', 'type_ip', 'type_constitutional'} <= set(types)


def test_code_case_type_prefixes() -> None:
    data = pd.DataFrame({
        'party1_united_states': [False, False], 'party2_united_states': [False, False],
        'party1_plaintiff': [True, False], 'party2_plaintiff': [False, False],
        'party1_defendant': [False, False], 'party2_defendant': [True, False],
        'immigration_asylum': [False, True], 'immigration_removal': [False, False],
        'tort_negligence': [True, False]})
    data = coders.CodeCaseType().apply(amos.Dataset(data), prefixes = 'immigration, tort').data
    # A prefix added to the rules is a type once the cases have its columns.
    assert list(data['type_immigration']) == [False, True]
    assert list(data['type_tort']) == [True, False]


def test_code_outcome(coded: amos.Dataset) -> None:
    data = coded.data
    # Case 1 is reversed by its disposition, case 2 affirmed (although its
    # dissent says "reverse"), and case 3 has no disposition, so the opinion's
    # "We vacate" is used.
    assert list(data['outcome_reversal']) == [True, False, True]
    assert data.loc['1', 'outcome_party2_won'] and not data.loc['1', 'outcome_party1_won']
    assert data.loc['1', 'outcome_criminal_defendant_won']
    assert not data.loc['1', 'outcome_prosecution_won']
    assert pd.isna(data.loc['1', 'outcome_civil_plaintiff_won'])
    assert data.loc['1', 'appeal_by_defendant']
    assert not data.loc['2', 'outcome_civil_plaintiff_won']
    assert data.loc['2', 'outcome_civil_defendant_won']
    assert not data.loc['2', 'appeal_by_defendant']
    assert pd.isna(data.loc['3', 'outcome_party1_won'])
    assert data['outcome_party1_won'].dtype == 'boolean'


def test_drop_text_columns(coded: amos.Dataset) -> None:
    coded.data['case_name'] = coded.data['case_name'].astype('category')
    coders.DropTextColumns().apply(coded, keep = ['court'])
    data = coded.data
    for column in ('party1', 'panel_judges', 'date_filed', 'url', 'citations_case'):
        assert column not in data.columns
    for column in ('court', 'case_name', 'court_num', 'published', 'outcome_party1_won', 'year'):
        assert column in data.columns


def test_drop_text_columns_keeps_label() -> None:
    dataset = amos.Dataset(pd.DataFrame({'note': ['a', 'b'], 'x': [1, 2]}), label = 'note')
    coders.DropTextColumns().apply(dataset)
    assert list(dataset.data.columns) == ['note', 'x']


def test_missing_columns() -> None:
    with pytest.raises(KeyError, match = 'federal rules'):
        coders.CodeOutcome().apply(amos.Dataset(pd.DataFrame({'x': [1]})))


def test_code_outcome_prefers_stated_decisions() -> None:
    # The header's disposition, then the decision that the opinion states,
    # and only then "reverse", "vacate", or "remand" anywhere in the opinion.
    data = pd.DataFrame({
        'disposition': ['Affirmed.', None, None, None],
        'decision': ['we reverse.', 'AFFIRMED', 'VACATED AND REMANDED', None],
        'decision_reverse': [True, False, False, False],
        'decision_vacate': [False, False, True, False],
        'decision_remand': [False, False, True, False],
        'opinion_reverse': [True, True, False, True]})
    for column in ('disposition_reverse', 'disposition_vacate', 'disposition_remand',
                   'opinion_vacate', 'opinion_remand'):
        data[column] = False
    result = coders.CodeOutcome().apply(amos.Dataset(data)).data
    assert list(result['outcome_reversal']) == [False, False, True, True]
    # Rules that find no "decision" leave the opinion's words.
    result = coders.CodeOutcome().apply(amos.Dataset(
        data.drop(columns = [c for c in data.columns if c.startswith('decision')]))).data
    assert list(result['outcome_reversal']) == [False, True, False, True]


def test_tidy_cases() -> None:
    assert amos.library.classify('tidy_cases') == 'munger'
    data = pd.DataFrame({
        'published': [True, None, False],
        'year': [2019.0, None, 2020.0],
        'score': [0.5, None, 1.0]})
    tidied = courtpy.code(data, ['tidy_cases']).data
    assert tidied['published'].dtype == 'boolean'
    assert tidied['year'].dtype == 'Int64'
    assert tidied['score'].dtype == 'float64'


def test_split_values() -> None:
    assert amos.library.classify('split_values') == 'munger'
    data = pd.DataFrame({
        'panel_judges': ['LYNCH; HOWARD; THOMPSON', None, 'KAYATTA'],
        'agencies': ['Internal Revenue Service; United States Tax Court', None, None],
        'notes': ['a; b', None, None]})
    listed = coders.SplitValues().apply(amos.Dataset(data.copy())).data
    assert listed['panel_judges'].tolist() == [['LYNCH', 'HOWARD', 'THOMPSON'], [], ['KAYATTA']]
    assert listed['agencies'].tolist() == [['Internal Revenue Service', 'United States Tax Court'], [], []]
    # Only the columns of rules that make several values are split.
    assert listed['notes'].equals(data['notes'])
    wide = coders.SplitValues().apply(
        amos.Dataset(data.copy()), columns = 'agencies', into = 'columns').data
    assert wide['agencies_1'].tolist() == ['Internal Revenue Service', None, None]
    assert wide['agencies_2'].tolist() == ['United States Tax Court', None, None]
    assert 'agencies' in wide.columns and 'agencies_3' not in wide.columns
    with pytest.raises(ValueError, match = 'into'):
        coders.SplitValues().apply(amos.Dataset(data.copy()), into = 'rows')
    with pytest.raises(KeyError):
        coders.SplitValues().apply(amos.Dataset(data.copy()), columns = 'missing')
