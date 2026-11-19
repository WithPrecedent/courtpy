"""Tests the inferers module: the effects of panels on judges' votes."""

from __future__ import annotations

import amos
import numpy as np
import pandas as pd
import pytest

import courtpy


def make_votes(effect: float, cases: int = 1500, seed: int = 0) -> pd.DataFrame:
    """Returns votes in which colleagues' party moves each vote by `effect`."""
    generator = np.random.default_rng(seed)
    court = generator.choice([1, 5, 9], cases)
    year = generator.integers(2005, 2010, cases)
    parties = generator.choice([-1, 1], (cases, 3))
    rows = []
    for case in range(cases):
        for seat in range(3):
            own = parties[case, seat]
            others = np.delete(parties[case], seat).mean()
            chance = 0.25 + effect * others + 0.05 * own + 0.05 * (court[case] == 9)
            rows.append({
                'case_id': f'c{case}', 'court_num': court[case], 'year': year[case],
                'judge_party': own, 'colleagues_party': others,
                'vote_reversal': generator.random() < chance})
    return pd.DataFrame(rows)


def test_panel_effects_is_an_inferer() -> None:
    assert amos.library.classify('panel_effects') == 'inferer'


def test_panel_effects_finds_an_effect() -> None:
    item = amos.Dataset(make_votes(0.08))
    courtpy.inferers.PanelEffects().apply(item, n_permutations = 200)
    table = item.tables['panel_effects']
    assert list(table.index) == ['colleagues_party', 'colleagues_party x judge_party', 'judge_party']
    assert list(table.columns) == [
        'coefficient', 'std_error', 't_statistic', 'p_value', 'ri_p_value', 'ci_lower', 'ci_upper']
    effect = table.loc['colleagues_party']
    assert effect['ci_lower'] < 0.08 < effect['ci_upper']
    assert effect['p_value'] < 0.01 and effect['ri_p_value'] < 0.01
    assert pd.isna(table.loc['judge_party', 'ri_p_value'])
    assert item.history[-1]['votes'] == 4500 and item.history[-1]['clusters'] == 1500


def test_panel_effects_finds_none_without_one() -> None:
    item = amos.Dataset(make_votes(0.0, seed = 2))
    courtpy.inferers.PanelEffects().apply(item, n_permutations = 200, interact = False)
    table = item.tables['panel_effects']
    assert list(table.index) == ['colleagues_party', 'judge_party']
    assert table.loc['colleagues_party', 'ri_p_value'] > 0.05


def test_panel_effects_matches_a_regression_with_dummies() -> None:
    votes = make_votes(0.05, cases = 300, seed = 4)
    item = amos.Dataset(votes)
    courtpy.inferers.PanelEffects().apply(item, n_permutations = 0, interact = False)
    table = item.tables['panel_effects']
    stratum = votes['court_num'].astype(str) + votes['year'].astype(str)
    x = np.column_stack([
        votes['colleagues_party'], votes['judge_party'],
        pd.get_dummies(stratum).to_numpy(dtype = float)])
    found, *_ = np.linalg.lstsq(x, votes['vote_reversal'].to_numpy(dtype = float), rcond = None)
    assert table['coefficient'].to_numpy() == pytest.approx(found[:2])
    assert table['ri_p_value'].isna().all()


def test_panel_effects_needs_its_columns() -> None:
    with pytest.raises(KeyError, match = 'colleagues_party'):
        courtpy.inferers.PanelEffects().apply(amos.Dataset(pd.DataFrame({'vote_reversal': [True]})))
