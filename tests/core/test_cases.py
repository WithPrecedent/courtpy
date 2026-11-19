"""Tests the helpers for tables of cases in the cases module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from courtpy import cases


def test_split_cell() -> None:
    assert cases.split_cell('LYNCH; HOWARD;  ; THOMPSON') == ['LYNCH', 'HOWARD', 'THOMPSON']
    assert cases.split_cell(['A', ' ', 'B']) == ['A', 'B']
    assert cases.split_cell(np.array(['A'])) == ['A']
    assert cases.split_cell(None) == [] and cases.split_cell(np.nan) == []
    assert cases.split_cell('') == []
    assert cases.split_cell('a, b', ', ') == ['a', 'b']


def test_column_as_flags_and_numbers() -> None:
    data = pd.DataFrame({
        'text': ['TRUE', 'no', None, 'yes'],
        'flags': pd.array([True, False, None, True], dtype = 'boolean')})
    assert cases.column_as_flags(data, 'text').tolist() == [True, False, False, True]
    assert cases.column_as_flags(data, 'flags').dtype == bool
    assert cases.column_as_flags(data, 'missing').tolist() == [False] * 4
    numbers = cases.flags_as_numbers(data['flags'])
    assert numbers.dtype == 'float64'
    assert numbers.iloc[:2].tolist() == [1.0, 0.0] and np.isnan(numbers.iloc[2])


def test_require_columns() -> None:
    data = pd.DataFrame({'year': [2020]})
    cases.require_columns(data, ['year'], 'a table')
    with pytest.raises(KeyError, match = r"a table needs the columns \['court'\].*Parse first"):
        cases.require_columns(data, ['year', 'court'], 'a table', hint = 'Parse first.')


def test_select_whole_cases() -> None:
    votes = pd.DataFrame({
        'case_id': ['1', '1', '2', '2'],
        'year': [2010, 2010, 2012, 2012],
        'dissent': [False, True, False, False]})
    assert cases.select_whole_cases(votes, None).all()
    assert cases.select_whole_cases(votes, 'not dissent').tolist() == [False, False, True, True]
    assert cases.select_whole_cases(votes, 'year > 2011').tolist() == [False, False, True, True]
    with pytest.raises(KeyError, match = 'docket'):
        cases.select_whole_cases(votes, 'year > 0', case_column = 'docket')
    for query in ('year + 1', '1 > 0'):
        with pytest.raises(ValueError, match = 'must say whether each row'):
            cases.select_whole_cases(votes, query)
    # Flags read from a CSV file as text still select rows.
    text = votes.assign(dissent = ['TRUE', 'TRUE', 'FALSE', 'TRUE'])
    assert cases.select_whole_cases(text, 'dissent').tolist() == [
        True, True, False, False]
