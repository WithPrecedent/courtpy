"""Tests the plots module: courtpy's figures of cases, courts, and judges."""

from __future__ import annotations

import amos
import numpy as np
import pandas as pd
import pytest

import courtpy

pytest.importorskip('matplotlib')


def make_cases() -> courtpy.Cases:
    """Returns cases of three courts, with what the plots draw."""
    data = pd.DataFrame({
        'court_name': ['tenth_circuit'] * 4 + ['fifth_circuit'] * 3 + ['dc_circuit'],
        'court_num': [10, 10, 10, 10, 5, 5, 5, 12],
        'lower_court_name': [
            'district_of_colorado', 'district_of_colorado', 'district_of_kansas', None,
            'northern_district_of_texas', 'northern_district_of_texas',
            'southern_district_of_texas', 'district_of_columbia'],
        'year': [2008, 2008, 2009, 2010, 2008, 2009, 2009, 2010],
        'outcome_reversal': pd.array([True, False, False, True, False, False, True, pd.NA], dtype = 'boolean'),
        'criminal_firearm': [True, True, False, False, True, False, False, False],
        'type_immigration': [False, False, True, False, False, True, True, False],
        'type_criminal': [True, True, False, False, True, False, False, True],
        'judge_party1': [-1, -1, 1, 1, 1, 1, -1, 1],
        'judge_party2': [-1, 1, 1, 1, 1, -1, -1, 1],
        'judge_party3': [-1, 1, 1, None, 1, -1, 1, 1]},
        index = pd.Index([f'c{n}' for n in range(8)], name = 'case_id'))
    return courtpy.Cases.create(data)


def draw(name: str, item: amos.Dataset, **parameters: object) -> object:
    """Applies a plot from the library and returns its figure."""
    amos.library.borrow(name)().apply(item, **parameters)
    return item.figures[name]


def test_plots_are_in_the_library() -> None:
    for name in (
            'court_rates', 'cases_over_time', 'issues_over_time', 'panel_composition',
            'lower_court_rates', 'trends_by_administration', 'judge_network',
            'idb_confusion_matrices', 'idb_missing_differences'):
        assert amos.library.classify(name) == 'plot'


def test_court_rates_are_measured_rates() -> None:
    figure = draw('court_rates', make_cases())
    axes = figure.axes[0]
    # The courts are in the order of the table of courts, with their names.
    assert [t.get_text() for t in axes.get_yticklabels()] == ['Fifth Circuit', 'Tenth Circuit']
    assert [round(b.get_width(), 4) for b in axes.patches] == [round(1 / 3, 4), 0.5]
    labels = [t.get_text() for t in axes.texts]
    assert labels == [' 33% (n = 3)', ' 50% (n = 4)']
    # The rate of every court is a line, and there are no error bars.
    assert axes.lines[0].get_xdata()[0] == pytest.approx(3 / 7)
    assert not axes.collections


def test_cases_over_time_has_a_panel_for_each_court() -> None:
    figure = draw('cases_over_time', make_cases())
    shown = [a for a in figure.axes if a.get_visible()]
    assert [a.get_title() for a in shown] == ['Fifth Circuit', 'Tenth Circuit', 'D.C. Circuit']
    tenth = shown[1].lines[0]
    assert list(tenth.get_xdata()) == [2008, 2009, 2010]
    assert list(tenth.get_ydata()) == [2, 1, 1]


def test_issues_over_time_counts_each_issue() -> None:
    figure = draw('issues_over_time', make_cases(), issues = 'criminal_firearm, type_immigration')
    fifth = next(a for a in figure.axes if a.get_title() == 'Fifth Circuit')
    firearm, immigration = fifth.lines
    assert firearm.get_label() == 'criminal firearm'
    assert list(firearm.get_ydata()) == [1, 0, 0]
    assert list(immigration.get_ydata()) == [0, 2, 0]
    with pytest.raises(ValueError, match = 'issues'):
        draw('issues_over_time', make_cases())


def test_panel_composition_splits_by_party_and_column() -> None:
    figure = draw('panel_composition', make_cases(), by = 'type_criminal')
    axes = figure.axes[0]
    assert [t.get_text() for t in axes.get_xticklabels()] == ['DDD', 'DDR', 'DRR', 'RRR']
    heights = [round(b.get_height(), 4) for b in axes.patches]
    # Other cases: DDR (c5 and c6) 1 of 2 and RRR (c2) 0; criminal: DDD
    # (c0) 1, DRR (c1) 0, and RRR (c4) 0. c7 has no outcome, and c3 no
    # third party.
    assert heights == [0, 0.5, 0, 0, 1, 0, 0, 0]


def test_lower_court_rates_group_by_reviewing_court() -> None:
    figure = draw('lower_court_rates', make_cases())
    axes = figure.axes[0]
    labels = [t.get_text() for t in axes.get_yticklabels()]
    assert labels == [
        'Northern District of Texas (2)', 'Southern District of Texas (1)',
        'District of Colorado (2)', 'District of Kansas (1)']
    assert [round(b.get_width(), 4) for b in axes.patches] == [0, 1, 0.5, 0]


def test_trends_by_administration_shade_the_presidents() -> None:
    figure = draw('trends_by_administration', make_cases())
    tenth = next(a for a in figure.axes if a.get_title() == 'Tenth Circuit')
    assert list(tenth.lines[0].get_ydata()) == [0.5, 0, 1]
    # Bush's term (Republican) and Obama's (Democratic) are shaded.
    colors = {tuple(np.round(p.get_facecolor()[:3], 3)) for p in tenth.patches}
    assert len(colors) == 2


def test_judge_network() -> None:
    pytest.importorskip('networkx')
    votes = amos.Dataset(pd.DataFrame({
        'case_id': ['a', 'a', 'a', 'b', 'b', 'b'],
        'judge': ['LYNCH', 'HOWARD', 'BOUDIN', 'LYNCH', 'HOWARD', 'TORRUELLA'],
        'judge_party': [-1, 1, 1, -1, 1, None],
        'judge_dissented': [False, False, True, False, False, False]}))
    figure = draw('judge_network', votes)
    axes = figure.axes[0]
    assert len(axes.collections[1].get_offsets()) == 4
    # LYNCH and HOWARD sat together twice; the others once.
    assert len(axes.collections[0].get_paths()) == 5
    dissents = draw('judge_network', votes, dissents = True)
    assert len(dissents.axes[0].collections[0].get_paths()) == 2
    with pytest.raises(KeyError, match = 'cases_to_votes'):
        draw('judge_network', make_cases())
