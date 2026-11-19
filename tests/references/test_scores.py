"""Tests the scores module."""

from __future__ import annotations

import pathlib

import amos
import pandas as pd
import pytest

import courtpy
from courtpy import scores


@pytest.fixture
def judge_scores() -> pd.DataFrame:
    """Returns behavioral scores of judges from training cases."""
    return pd.DataFrame({'nid': [101, 102], 'reversal_rate': [0.2, 0.6], 'dissent_rate': [0.0, 0.1]})


def test_mergers_are_in_the_library() -> None:
    assert amos.library.classify('add_judge_scores') == 'merger'
    assert amos.library.classify('add_court_scores') == 'merger'


def test_add_judge_scores_to_votes(judge_scores: pd.DataFrame) -> None:
    votes = courtpy.Votes.create(pd.DataFrame({
        'vote_id': ['a-1', 'a-2', 'a-3'], 'judge_nid': pd.array([101, 102, 999], dtype = 'Int64')}))
    data = scores.AddJudgeScores().apply(votes, source = judge_scores).data
    assert list(data.columns) == ['judge_nid', 'judge_score_reversal_rate', 'judge_score_dissent_rate']
    assert list(data['judge_score_reversal_rate'].iloc[:2]) == [0.2, 0.6]
    assert pd.isna(data['judge_score_reversal_rate'].iloc[2])
    # A table of Judges is labeled by the judges' numbers.
    table = courtpy.Judges.create(judge_scores.rename(columns = {'nid': 'judge_nid'}))
    named = scores.AddJudgeScores().apply(
        courtpy.Votes.create(pd.DataFrame({'vote_id': ['a-1'], 'judge_nid': [102]})),
        source = table, columns = 'dissent_rate', prefix = 'train_').data
    assert list(named.columns) == ['judge_nid', 'train_dissent_rate']


def test_add_judge_scores_to_cases(judge_scores: pd.DataFrame, tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'scores.csv'
    judge_scores.to_csv(path, index = False)
    cases = courtpy.Cases.create(pd.DataFrame({
        'case_id': ['a', 'b'],
        'judge_nid1': pd.array([101, 102], dtype = 'Int64'),
        'judge_nid2': pd.array([102, pd.NA], dtype = 'Int64')}))
    dataset = scores.AddJudgeScores().apply(cases, source = str(path), columns = ['reversal_rate'])
    data = dataset.data
    assert list(data.columns) == ['judge_nid1', 'judge_nid2', 'judge_score_reversal_rate1', 'judge_score_reversal_rate2']
    assert list(data['judge_score_reversal_rate1']) == [0.2, 0.6]
    assert data.loc['a', 'judge_score_reversal_rate2'] == 0.6
    assert pd.isna(data.loc['b', 'judge_score_reversal_rate2'])
    assert dataset.history[-1]['matched'] == 3
    with pytest.raises(KeyError, match = 'code_panels'):
        scores.AddJudgeScores().apply(courtpy.Cases.create(pd.DataFrame({'x': [1]})), source = judge_scores)
    with pytest.raises(ValueError, match = 'nothing to merge'):
        scores.AddJudgeScores().apply(cases)


def test_add_court_scores() -> None:
    cases = courtpy.Cases.create(pd.DataFrame({'case_id': ['a', 'b'], 'court_num': [1, 5]}))
    table = courtpy.Courts.create(pd.DataFrame({'court_num': [1, 2], 'reversal_rate': [0.3, 0.4]}))
    data = scores.AddCourtScores().apply(cases, source = table).data
    assert list(data.columns) == ['court_num', 'court_score_reversal_rate']
    assert data.loc['a', 'court_score_reversal_rate'] == 0.3
    assert pd.isna(data.loc['b', 'court_score_reversal_rate'])
