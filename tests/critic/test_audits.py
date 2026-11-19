"""Tests the audits module: courtpy's checks of court data."""

from __future__ import annotations

import amos
import numpy as np
import pandas as pd
import pytest

import courtpy
from courtpy.critic import _strata


def make_panels(size: int = 600, seed: int = 0) -> pd.DataFrame:
    """Returns cases with panels drawn at random within each court and year."""
    generator = np.random.default_rng(seed)
    parties = generator.choice([-1, 1], (size, 3))
    data = pd.DataFrame({
        'court_num': generator.choice([1, 5, 9], size),
        'year': generator.integers(2005, 2010, size),
        'judge_party1': parties[:, 0], 'judge_party2': parties[:, 1], 'judge_party3': parties[:, 2],
        'type_criminal': generator.random(size) < 0.5},
        index = pd.Index([f'c{n}' for n in range(size)], name = 'case_id'))
    # A trait that Republican panels get more often, as if panels were not
    # assigned at random.
    data['chosen'] = (parties == 1).sum(axis = 1) + generator.normal(0, 0.5, size) > 2
    return data


def test_audits_are_in_the_library() -> None:
    for name in ('audit_random_assignment', 'audit_parsing', 'audit_coverage', 'validate_coding'):
        assert amos.library.classify(name) == 'evaluator'


def test_permute_within_keeps_each_stratum() -> None:
    codes = np.array([0, 0, 0, 1, 1, 2])
    values = np.array([1.0, 2.0, 3.0, 10.0, 20.0, 7.0])
    shuffled = _strata.permute_within(values, codes, np.random.default_rng(1))
    for code in range(3):
        assert sorted(shuffled[codes == code]) == sorted(values[codes == code])
    centered = _strata.demean(values, codes)
    assert np.allclose(np.bincount(codes, weights = centered), 0)
    data = pd.DataFrame({'court_num': [1, 1, 2, None], 'year': [2008, 2008, 2008, 2008]})
    assert _strata.stratum_codes(data, ['court_num', 'year']).tolist() == [0, 0, 1, -1]


def test_audit_random_assignment() -> None:
    item = courtpy.Cases.create(make_panels())
    courtpy.audits.AuditRandomAssignment().apply(
        item, traits = 'type_criminal, chosen', n_permutations = 200)
    table = item.tables['audit_random_assignment']
    assert list(table.index) == ['type_criminal', 'chosen']
    assert list(table.columns) == [
        'DDD', 'DDR', 'DRR', 'RRR', 'correlation', 'p_value', 'balanced', 'cases']
    assert table.loc['type_criminal', 'balanced']
    assert not table.loc['chosen', 'balanced'] and table.loc['chosen', 'p_value'] < 0.01
    assert table.loc['chosen', 'RRR'] > table.loc['chosen', 'DDD']
    assert table.loc['chosen', 'cases'] == 600
    # The same seed gives the same test.
    again = courtpy.Cases.create(make_panels())
    courtpy.audits.AuditRandomAssignment().apply(
        again, traits = 'type_criminal, chosen', n_permutations = 200)
    pd.testing.assert_frame_equal(again.tables['audit_random_assignment'], table)


def test_audit_random_assignment_needs_panels() -> None:
    data = make_panels().drop(columns = ['judge_party3']).assign(panel_party = np.nan, panel_found = 2)
    with pytest.raises(ValueError, match = 'no case has a panel of 3'):
        courtpy.audits.AuditRandomAssignment().apply(
            courtpy.Cases.create(data), traits = 'type_criminal')


def test_audit_parsing() -> None:
    data = pd.DataFrame({
        'court_num': [1, None, 9, 9],
        'lower_court_num': [1026, None, None, 1084],
        'review_agency': [False, False, True, False],
        'panel_judges': ['A; B; C', '', 'A; B', 'A; B; C'],
        'panel_size': [3, 0, 2, 3],
        'year': [2008, 2008, None, 2009],
        'outcome_reversal': pd.array([True, pd.NA, False, False], dtype = 'boolean'),
        'disposition_affirm': [False, False, True, True],
        'decision_affirm': [False, False, False, True],
        'disposition_reverse': [True, False, False, False],
        'decision_reverse': [True, False, True, False]},
        index = pd.Index(['a', 'b', 'c', 'd'], name = 'case_id'))
    item = courtpy.Cases.create(data)
    courtpy.audits.AuditParsing().apply(item)
    table = item.tables['audit_parsing']
    assert table['cases'].to_dict() == {
        'no court': 1, 'no court below': 1, 'no judges': 1, 'panel not of 3': 2,
        'no year': 1, 'no outcome': 1, 'disposition and decision disagree': 1}
    assert table.loc['panel not of 3', 'examples'] == 'b; c'
    assert table.loc['disposition and decision disagree', 'examples'] == 'c'
    assert table.loc['no court', 'share'] == 0.25


def test_audit_coverage() -> None:
    data = pd.DataFrame({
        'court_num': [1, 1, 1, 10],
        'year': [2008, 2008, 2009, 2008],
        'published': [True, False, True, True]},
        index = pd.Index(['a', 'b', 'c', 'd'], name = 'case_id'))
    appeals = pd.DataFrame({
        'circuit': ['First Circuit'] * 4 + ['Tenth Circuit'] * 2 + ['Ninth Circuit'],
        'judgment_date': pd.to_datetime([
            '2008-03-01', '2008-05-01', '2008-07-01', '2009-01-01', '2008-02-01',
            '2008-03-01', '2008-01-01']),
        'published': [1, 0, 1, 0, 1, 1, 1]})
    item = courtpy.Cases.create(data)
    courtpy.audits.AuditCoverage().apply(item, source = appeals)
    table = item.tables['audit_coverage']
    assert list(table.index) == [('First Circuit', 2008), ('First Circuit', 2009), ('Tenth Circuit', 2008)]
    assert table['cases'].tolist() == [2, 1, 1]
    assert table['idb_appeals'].tolist() == [3, 1, 2]
    assert table['coverage'].round(3).tolist() == [0.667, 1.0, 0.5]
    assert table['published'].tolist() == [1, 1, 1]
    assert table['idb_published'].tolist() == [2, 0, 2]
    assert pd.isna(table.loc[('First Circuit', 2009), 'published_coverage'])


def test_validate_coding() -> None:
    data = pd.DataFrame({
        'published': [True, True, False, False, None],
        'idb_published': [1, 0, 0, 0, 1],
        'type_criminal': [True, False, True, False, True],
        'idb_appeal_type': ['15', '3', '19', '4', None]},
        index = pd.Index(list('abcde'), name = 'case_id'))
    item = courtpy.Cases.create(data)
    courtpy.audits.ValidateCoding().apply(item)
    table = item.tables['validate_coding']
    assert list(table.index) == ['published', 'type_criminal']
    assert table.loc['published', 'cases'] == 4
    assert table.loc['published', 'agreement'] == 0.75
    assert table.loc['published', 'courtpy_only'] == 1
    assert table.loc['published', 'kappa'] == pytest.approx(0.5)
    assert table.loc['type_criminal', 'reference'] == 'idb_appeal_type'
    assert table.loc['type_criminal', 'kappa'] == 1
    # Codes of one's own, and pairs named as text.
    courtpy.audits.ValidateCoding().apply(
        item, pairs = 'type_criminal = idb_appeal_type', true_values = {'idb_appeal_type': '3|4'})
    assert item.tables['validate_coding'].loc['type_criminal', 'agreement'] == 0
    with pytest.raises(ValueError, match = 'pairs'):
        courtpy.audits.ValidateCoding().apply(courtpy.Cases.create(data[['published']]))
