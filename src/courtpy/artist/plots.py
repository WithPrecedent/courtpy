"""Techniques that draw figures of cases, courts, panels, and judges.

Each is an `amos` plot (`amos.plots.Plot`), so it is added to the `amos`
library when courtpy is imported, can be named in the settings of an
"artist" worker, takes the parameters that every plot takes ("width",
"height", "title", "style", and so on), and adds its figure to the
dataset's `figures` under its name. Courts are labeled with their
"feature_name" in the jurisdiction's table of courts (such as "Tenth
Circuit"; see `courtpy.courts.court_labels`), in the order of the table.

A rate is the share of the cases that have a flag (or the mean of a
number), measured from the cases themselves, so it is drawn without a
confidence interval. Each bar says how many cases it counts.

| Technique | Draws | Needs |
| --- | --- | --- |
| `court_rates` | The rate of a column in each court, with the rate of every court as a line. | `Cases`, with the column (the label, unless "column" is set). |
| `cases_over_time` | The number of cases of each court in each year, a panel for each court. | `Cases`, with "year". |
| `issues_over_time` | The number of cases with each issue (a column of flags, such as "criminal_firearm") in each court in each year, a panel for each court. | `Cases`, with "year" and the columns in "issues". |
| `panel_composition` | The rate of a column for each composition of the panel by the parties of the presidents who appointed its judges ("DDD" to "RRR"), split by another column if "by" is set. | `Cases`, with the judges' parties (from `add_biography` or `code_panels`). |
| `lower_court_rates` | The rate of a column for each court whose decisions a court reviews, a panel for each reviewing court. | `Cases`, with "lower_court_name" or "lower_court_num". |
| `trends_by_administration` | The yearly rate of a column in each court, a panel for each court, with the terms of Democratic and Republican presidents shaded. | `Cases`, with "year". |
| `judge_network` | The judges as a network, joined by how often they sat together (or, with "dissents", how often one dissented from the other), colored by party. | `Votes` (see `cases_to_votes`). |

Contents:
    CasesOverTime: the number of cases of each court in each year.
    CourtRates: the rate of a column in each court.
    IssuesOverTime: the number of cases with each issue in each court in
        each year.
    JudgeNetwork: the judges as a network of who sat with, or dissented
        from, whom.
    LowerCourtRates: the rate of a column for each court below, by the
        court that reviewed it.
    PanelComposition: the rate of a column for each composition of the
        panel by party.
    TrendsByAdministration: the yearly rate of a column in each court, with
        the presidents' terms shaded.
    _DEFAULT_RATE: the column whose rate is drawn when there is no label and
        none is named.
    _PARTY_COLORS: the colors of Democratic and Republican appointees and
        presidents.

"""

from __future__ import annotations

import dataclasses
import itertools
import math
from collections.abc import Sequence
from typing import Any, ClassVar, Literal

import amos
import numpy as np
import pandas as pd

from ..core import cases, utilities
from ..references import courts, judges, politics

# The column whose rate is drawn when the dataset has no label and none is
# named: whether the court of appeals reversed the court below.
_DEFAULT_RATE: str = 'outcome_reversal'
# The colors of Democratic (-1) and Republican (1) appointees and
# presidents, as the parties are usually drawn.
_PARTY_COLORS: dict[int, str] = {-1: '#1f5aa6', 1: '#c0392b'}


@dataclasses.dataclass
class CourtRates(amos.plots.Plot):
    """Plots the rate of a column in each court, as bars.

    Each bar is the share of the court's cases that have a flag (or the mean
    of a number), with the number of cases it counts. A dashed line is the
    rate of all the cases together.

    """

    starts_at_zero: ClassVar[str] = 'x'

    """ Required Methods """

    def draw(
        self,
        item: amos.Dataset,
        figure: Any,
        *,
        column: str | None = None,
        court_name: str = 'court_name',
        court_num: str = 'court_num',
        jurisdiction: str = 'federal',
        **kwargs: Any) -> None:
        """Draws the rate of `column` in each court.

        Args:
            item: the cases.
            figure: the figure to draw on.
            column: the column whose rate is drawn. Defaults to `None`, which
                uses the dataset's label, or else `_DEFAULT_RATE`.
            court_name: the column with courtpy's name for each case's court.
                Defaults to "court_name".
            court_num: the column with courtpy's number for each case's
                court. Defaults to "court_num".
            jurisdiction: the folder of the jurisdiction's table of courts.
                Defaults to "federal".
            **kwargs: not used.

        """
        data = item.data
        column = _rate_column(item, column)
        table = pd.DataFrame({
            'court': courts.court_labels(
                data, court_name = court_name, court_num = court_num,
                jurisdiction = jurisdiction),
            'value': _numbers(data[column])}).dropna()
        rates = table.groupby('court', observed = True)['value'].agg(
            ['mean', 'size'])
        shares = _is_share(table['value'])
        axes = figure.subplots()
        places = np.arange(len(rates))
        axes.barh(places, rates['mean'])
        axes.set_yticks(places, [str(c) for c in rates.index])
        axes.invert_yaxis()
        for place, (rate, count) in zip(
                places, rates.itertuples(index = False), strict = True):
            axes.annotate(
                f' {_amount(rate, shares)} (n = {count:,})', (rate, place),
                va = 'center', fontsize = 'small')
        overall = table['value'].mean()
        axes.axvline(
            overall, color = '0.35', linestyle = '--',
            label = f'All courts: {_amount(overall, shares)}')
        # Room to the right of the longest bar for its label.
        axes.set_xlim(0, max(rates['mean'].max(), overall) * 1.45 or 1)
        figure.legend(loc = 'outside lower center')
        axes.set_xlabel(_rate_name(column, shares))
        _as_percent(axes.xaxis, shares)


@dataclasses.dataclass
class CasesOverTime(amos.plots.Plot):
    """Plots the number of cases of each court in each year.

    Each court in the data has a panel, labeled with its name, and the
    panels share their axes so that the courts can be compared.

    """

    size: ClassVar[tuple[float, float]] = (9.6, 7.2)
    shared_axes: ClassVar[str] = 'xy'
    starts_at_zero: ClassVar[str] = 'y'

    """ Required Methods """

    def draw(
        self,
        item: amos.Dataset,
        figure: Any,
        *,
        year: str = 'year',
        court_name: str = 'court_name',
        court_num: str = 'court_num',
        jurisdiction: str = 'federal',
        columns: int = 4,
        **kwargs: Any) -> None:
        """Draws the number of cases of each court in each year.

        Args:
            item: the cases.
            figure: the figure to draw on.
            year: the column with each case's year. Defaults to "year".
            court_name: the column with courtpy's name for each case's court.
                Defaults to "court_name".
            court_num: the column with courtpy's number for each case's
                court. Defaults to "court_num".
            jurisdiction: the folder of the jurisdiction's table of courts.
                Defaults to "federal".
            columns: the most panels in a row. Defaults to 4.
            **kwargs: not used.

        """
        data = item.data
        counts = _yearly(
            data, pd.Series(1, index = data.index, name = 'cases'),
            year = year, court_name = court_name, court_num = court_num,
            jurisdiction = jurisdiction, how = 'sum')
        panels = _court_panels(figure, counts.index, columns)
        years = counts.columns.to_numpy()
        for court, axes in panels.items():
            axes.plot(years, counts.loc[court].to_numpy(), marker = '.')
        figure.supxlabel('Year')
        figure.supylabel('Cases')


@dataclasses.dataclass
class IssuesOverTime(amos.plots.Plot):
    """Plots the number of cases with each issue in each court in each year.

    An issue is a column of flags, such as "criminal_firearm" (from the
    rules) or "type_immigration" (from `code_case_type`). Each court in the
    data has a panel, labeled with its name, with a line for each issue,
    and the panels share their axes.

    """

    size: ClassVar[tuple[float, float]] = (9.6, 7.2)
    shared_axes: ClassVar[str] = 'xy'
    starts_at_zero: ClassVar[str] = 'y'

    """ Required Methods """

    def draw(
        self,
        item: amos.Dataset,
        figure: Any,
        *,
        issues: Sequence[str] | str = (),
        year: str = 'year',
        court_name: str = 'court_name',
        court_num: str = 'court_num',
        jurisdiction: str = 'federal',
        columns: int = 4,
        **kwargs: Any) -> None:
        """Draws the number of cases with each issue in each court and year.

        Args:
            item: the cases.
            figure: the figure to draw on.
            issues: the columns of flags to count, as a list or a
                comma-separated `str`. Required.
            year: the column with each case's year. Defaults to "year".
            court_name: the column with courtpy's name for each case's court.
                Defaults to "court_name".
            court_num: the column with courtpy's number for each case's
                court. Defaults to "court_num".
            jurisdiction: the folder of the jurisdiction's table of courts.
                Defaults to "federal".
            columns: the most panels in a row. Defaults to 4.
            **kwargs: not used.

        Raises:
            ValueError: if no issue is named.
            KeyError: if an issue is not a column of the cases.

        """
        data = item.data
        named = utilities.listify(issues)
        if not named:
            message = 'issues_over_time needs "issues": columns of flags'
            raise ValueError(message)
        cases.require_columns(data, named, 'issues_over_time')
        counts = {
            issue: _yearly(
                data, cases.column_as_flags(data, issue).astype('int64'),
                year = year, court_name = court_name, court_num = court_num,
                jurisdiction = jurisdiction, how = 'sum')
            for issue in named}
        every = counts[named[0]].index
        panels = _court_panels(figure, every, columns)
        for issue, table in counts.items():
            years = table.columns.to_numpy()
            for court, axes in panels.items():
                axes.plot(
                    years, table.loc[court].to_numpy(), marker = '.',
                    label = _words(issue))
        first = next(iter(panels.values()))
        handles, labels = first.get_legend_handles_labels()
        figure.legend(
            handles, labels, loc = 'outside upper center',
            ncols = min(len(named), 4))
        figure.supxlabel('Year')
        figure.supylabel('Cases')


@dataclasses.dataclass
class PanelComposition(amos.plots.Plot):
    """Plots the rate of a column for each composition of the panel.

    A panel's composition is the party of the president who appointed each
    of its judges, from all Democratic appointees ("DDD") to all Republican
    ones ("RRR") for a panel of three (see
    `courtpy.judges.panel_compositions`). With "by", the cases are split by
    another column (such as "type_criminal"), with bars side by side.

    """

    starts_at_zero: ClassVar[str] = 'y'

    """ Required Methods """

    def draw(
        self,
        item: amos.Dataset,
        figure: Any,
        *,
        column: str | None = None,
        by: str | None = None,
        size: int = 3,
        **kwargs: Any) -> None:
        """Draws the rate of `column` for each composition of the panel.

        Args:
            item: the cases, with the parties of their judges.
            figure: the figure to draw on.
            column: the column whose rate is drawn. Defaults to `None`, which
                uses the dataset's label, or else `_DEFAULT_RATE`.
            by: a column to split the cases by. A column of flags splits them
                into those with the flag and the others. Defaults to `None`.
            size: the number of judges on the panels to draw. Defaults to 3.
            **kwargs: not used.

        """
        data = item.data
        column = _rate_column(item, column)
        table = pd.DataFrame({
            'composition': judges.panel_compositions(data, size),
            'value': _numbers(data[column]),
            'group': _groups(data, by)}).dropna()
        rates = table.groupby(
            ['group', 'composition'], observed = False)['value'].agg(
                ['mean', 'size'])
        groups = list(dict.fromkeys(rates.index.get_level_values('group')))
        names = list(table['composition'].cat.categories)
        axes = figure.subplots()
        width = 0.8 / len(groups)
        for place, group in enumerate(groups):
            found = rates.loc[group].reindex(names)
            spots = np.arange(len(names)) + (place - (len(groups) - 1) / 2) * (
                width)
            bars = axes.bar(
                spots, found['mean'].fillna(0).to_numpy(), width,
                label = group if by else None)
            for bar, count in zip(
                    bars, found['size'].fillna(0), strict = True):
                if count:
                    axes.annotate(
                        f'n = {int(count):,}',
                        (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        ha = 'center', va = 'bottom', fontsize = 'x-small')
        shares = _is_share(table['value'])
        axes.set_xticks(np.arange(len(names)), names)
        axes.set_xlabel('Panel (D: Democratic appointee, R: Republican)')
        axes.set_ylabel(_rate_name(column, shares))
        _as_percent(axes.yaxis, shares)
        if by:
            axes.legend(title = _words(by))


@dataclasses.dataclass
class LowerCourtRates(amos.plots.Plot):
    """Plots the rate of a column for each court below, by reviewing court.

    Each court whose decisions the courts in the data reviewed (such as each
    district court of a circuit) has a bar, with the number of its cases.
    The bars are grouped and colored by the reviewing court, in the order of
    the table of courts, so that a court of appeals' treatment of its
    districts can be compared.

    """

    size: ClassVar[tuple[float, float]] = (7.2, 9.6)
    starts_at_zero: ClassVar[str] = 'x'

    """ Required Methods """

    def draw(
        self,
        item: amos.Dataset,
        figure: Any,
        *,
        column: str | None = None,
        minimum: int = 1,
        court_name: str = 'court_name',
        court_num: str = 'court_num',
        lower_court_name: str = 'lower_court_name',
        lower_court_num: str = 'lower_court_num',
        jurisdiction: str = 'federal',
        **kwargs: Any) -> None:
        """Draws the rate of `column` for each court below.

        Args:
            item: the cases.
            figure: the figure to draw on.
            column: the column whose rate is drawn. Defaults to `None`, which
                uses the dataset's label, or else `_DEFAULT_RATE`.
            minimum: the fewest cases of a court below to draw it. Defaults
                to 1.
            court_name: the column with courtpy's name for each case's court.
                Defaults to "court_name".
            court_num: the column with courtpy's number for each case's
                court. Defaults to "court_num".
            lower_court_name: the column with courtpy's name for the court
                below. Defaults to "lower_court_name".
            lower_court_num: the column with courtpy's number for the court
                below. Defaults to "lower_court_num".
            jurisdiction: the folder of the jurisdiction's table of courts.
                Defaults to "federal".
            **kwargs: not used.

        """
        data = item.data
        column = _rate_column(item, column)
        table = pd.DataFrame({
            'court': courts.court_labels(
                data, court_name = court_name, court_num = court_num,
                jurisdiction = jurisdiction),
            'lower': courts.court_labels(
                data, court_name = lower_court_name,
                court_num = lower_court_num, jurisdiction = jurisdiction),
            'value': _numbers(data[column])}).dropna()
        shares = _is_share(table['value'])
        rates = table.groupby(['court', 'lower'], observed = True)[
            'value'].agg(['mean', 'size'])
        rates = rates[rates['size'] >= minimum]
        axes = figure.subplots()
        places = np.arange(len(rates))
        reviewing = rates.index.get_level_values('court')
        for number, court in enumerate(dict.fromkeys(reviewing)):
            rows = reviewing == court
            axes.barh(
                places[rows], rates['mean'].to_numpy()[rows],
                color = f'C{number % 10}', label = str(court))
        lowers = rates.index.get_level_values('lower')
        axes.set_yticks(
            places,
            [f'{lower} ({int(n):,})'
             for lower, n in zip(lowers, rates['size'], strict = True)],
            fontsize = 'x-small')
        axes.invert_yaxis()
        axes.set_xlabel(_rate_name(column, shares))
        _as_percent(axes.xaxis, shares)
        figure.legend(
            title = 'Reviewing court', loc = 'outside lower center',
            ncols = 3, fontsize = 'small')


@dataclasses.dataclass
class TrendsByAdministration(amos.plots.Plot):
    """Plots the yearly rate of a column in each court, with presidents.

    Each court in the data has a panel with the yearly rate, and the
    background of every panel is shaded by the party of the president in
    office (blue for a Democrat and red for a Republican; see
    `courtpy.politics.executives`).

    """

    size: ClassVar[tuple[float, float]] = (9.6, 7.2)
    shared_axes: ClassVar[str] = 'xy'
    starts_at_zero: ClassVar[str] = 'y'

    """ Required Methods """

    def draw(
        self,
        item: amos.Dataset,
        figure: Any,
        *,
        column: str | None = None,
        year: str = 'year',
        court_name: str = 'court_name',
        court_num: str = 'court_num',
        jurisdiction: str = 'federal',
        columns: int = 4,
        **kwargs: Any) -> None:
        """Draws the yearly rate of `column` in each court.

        Args:
            item: the cases.
            figure: the figure to draw on.
            column: the column whose rate is drawn. Defaults to `None`, which
                uses the dataset's label, or else `_DEFAULT_RATE`.
            year: the column with each case's year. Defaults to "year".
            court_name: the column with courtpy's name for each case's court.
                Defaults to "court_name".
            court_num: the column with courtpy's number for each case's
                court. Defaults to "court_num".
            jurisdiction: the folder of the jurisdiction's table of courts.
                Defaults to "federal".
            columns: the most panels in a row. Defaults to 4.
            **kwargs: not used.

        """
        data = item.data
        column = _rate_column(item, column)
        rates = _yearly(
            data, _numbers(data[column]), year = year,
            court_name = court_name, court_num = court_num,
            jurisdiction = jurisdiction, how = 'mean')
        shares = _is_share(_numbers(data[column]))
        years = rates.columns.to_numpy(dtype = float)
        terms = _terms(years.min(), years.max() + 1)
        panels = _court_panels(figure, rates.index, columns)
        patch = amos.utilities.import_tool('matplotlib.patches').Patch
        for court, axes in panels.items():
            for start, end, party in terms:
                axes.axvspan(
                    start, end, color = _PARTY_COLORS[party], alpha = 0.12,
                    linewidth = 0)
            axes.plot(
                years, rates.loc[court].to_numpy(), color = '0.15',
                marker = '.')
            _as_percent(axes.yaxis, shares)
        figure.legend(
            handles = [
                patch(color = _PARTY_COLORS[-1], alpha = 0.3,
                      label = 'Democratic president'),
                patch(color = _PARTY_COLORS[1], alpha = 0.3,
                      label = 'Republican president')],
            loc = 'outside upper center', ncols = 2)
        figure.supxlabel('Year')
        figure.supylabel(_rate_name(column, shares))


@dataclasses.dataclass
class JudgeNetwork(amos.plots.Plot):
    """Plots the judges as a network of who sat with, or dissented from, whom.

    Each judge is a node, colored by the party of the president who
    appointed the judge (gray if it is not known), and two judges are joined
    by a line whose width is how many cases they decided together. With
    "dissents", two judges are joined only by the cases in which one of them
    dissented and the other did not, so the lines show who dissented from
    whom.

    """

    size: ClassVar[tuple[float, float]] = (8.0, 8.0)
    starts_at_zero: ClassVar[str] = ''

    """ Required Methods """

    def draw(
        self,
        item: amos.Dataset,
        figure: Any,
        *,
        dissents: bool = False,
        minimum: int = 1,
        labels: bool = True,
        judge: str = 'judge',
        case: str = 'case_id',
        party: str = 'judge_party',
        dissented: str = 'judge_dissented',
        seed: int = 0,
        **kwargs: Any) -> None:
        """Draws the network of the judges.

        Args:
            item: the votes (see `cases_to_votes`), a row for each judge on
                each case.
            figure: the figure to draw on.
            dissents: whether to join judges by the dissents of one from the
                other, instead of by the cases they decided together.
                Defaults to `False`.
            minimum: the fewest cases that join two judges to draw the line
                between them. Defaults to 1.
            labels: whether to write each judge's name. Defaults to `True`.
            judge: the column with each judge's name. Defaults to "judge".
            case: the column with each vote's case. Defaults to "case_id".
            party: the column with the party of the president who appointed
                the judge (-1 or 1). Defaults to "judge_party".
            dissented: the column of flags of whether the judge dissented,
                for `dissents`. Defaults to "judge_dissented".
            seed: the seed of the layout, so that the same data is drawn the
                same way. Defaults to 0.
            **kwargs: not used.

        Raises:
            KeyError: if the votes lack a column that is needed.

        """
        networkx = amos.utilities.import_tool('networkx')
        data = item.data
        needed = [judge, case, *([dissented] if dissents else [])]
        cases.require_columns(
            data, needed, 'judge_network (make votes with cases_to_votes)')
        pairs = _pairs(data, judge, case, dissented if dissents else None)
        pairs = pairs[pairs['cases'] >= minimum]
        graph = networkx.Graph()
        graph.add_nodes_from(data[judge].dropna().astype(str).unique())
        graph.add_weighted_edges_from(
            pairs[['first', 'second', 'cases']].itertuples(index = False))
        parties = (
            pd.to_numeric(data[party], errors = 'coerce').groupby(
                data[judge].astype(str)).first()
            if party in data.columns else pd.Series(dtype = float))
        colors = [
            _PARTY_COLORS.get(int(parties[n]), '0.6')
            if n in parties.index and not pd.isna(parties[n]) else '0.6'
            for n in graph.nodes]
        weights = np.array(
            [graph.edges[e]['weight'] for e in graph.edges], dtype = float)
        widths = 0.5 + 3.5 * weights / weights.max() if len(weights) else []
        axes = figure.subplots()
        layout = networkx.spring_layout(graph, seed = seed, weight = 'weight')
        networkx.draw_networkx_edges(
            graph, layout, ax = axes, width = widths, edge_color = '0.6',
            alpha = 0.7)
        networkx.draw_networkx_nodes(
            graph, layout, ax = axes, node_color = colors, node_size = 120)
        if labels:
            networkx.draw_networkx_labels(
                graph, layout, ax = axes, font_size = 6)
        axes.set_axis_off()


""" Private Functions """


def _amount(value: float, shares: bool) -> str:
    """Returns a rate as text for a label.

    Args:
        value: the rate.
        shares: whether the rate is a share (of cases with a flag).

    Returns:
        The rate as a percent (such as "17%") if it is a share, and otherwise
            to two decimal places.

    """
    return f'{value:.0%}' if shares else f'{value:.2f}'


def _as_percent(axis: Any, shares: bool) -> None:
    """Writes the ticks of an axis of shares as percents.

    Args:
        axis: the axis (such as `axes.xaxis`).
        shares: whether the axis shows shares; if not, it is unchanged.

    """
    if shares:
        ticker = amos.utilities.import_tool('matplotlib.ticker')
        axis.set_major_formatter(ticker.PercentFormatter(1.0, decimals = 0))


def _court_panels(
    figure: Any,
    names: Sequence[Any] | pd.Index,
    columns: int,
    *,
    share_y: bool = True) -> dict[Any, Any]:
    """Makes a panel for each court on a figure.

    Args:
        figure: the figure to draw on.
        names: the courts' labels, in order.
        columns: the most panels in a row.
        share_y: whether the panels share the range of the y axis. Defaults
            to `True`.

    Returns:
        The axes of each court's panel, by its label, each titled with it.
            Panels left over in the last row are hidden.

    """
    names = list(names)
    across = max(1, min(columns, len(names)))
    down = max(1, math.ceil(len(names) / across))
    grid = figure.subplots(
        down, across, sharex = True, sharey = share_y, squeeze = False)
    panels: dict[Any, Any] = {}
    for name, axes in itertools.zip_longest(names, grid.flat):
        if name is None:
            axes.set_visible(False)
            continue
        axes.set_title(str(name), fontsize = 'small')
        panels[name] = axes
    return panels


def _groups(data: pd.DataFrame, by: str | None) -> pd.Series:
    """Returns the group of each case for a plot split by a column.

    Args:
        data: the cases.
        by: the column to split them by, or `None`.

    Raises:
        KeyError: if `by` is not a column of the cases.

    Returns:
        The group of each case as text: "all cases" without `by`, the
            column's name and "other" for a column of flags, and the
            column's values otherwise.

    """
    if by is None:
        return pd.Series('all cases', index = data.index)
    cases.require_columns(data, [by], 'the column to split by')
    values = data[by]
    if pd.api.types.is_bool_dtype(values.dtype) or values.dropna().isin(
            [True, False]).all():
        flags = cases.column_as_flags(data, by)
        return flags.map({True: _words(by), False: 'other'})
    return values.astype('string')


def _numbers(values: pd.Series) -> pd.Series:
    """Returns a column as numbers, so that its mean is its rate.

    Args:
        values: a column of flags or numbers, which may be missing.

    Returns:
        The values as decimals (1 for true and 0 for false), with missing
            values kept missing.

    """
    if values.dtype == object:
        values = values.map(
            lambda v: float(v) if isinstance(v, bool | int | float) else v)
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.astype('Float64').astype(float)
    return pd.to_numeric(values, errors = 'coerce').astype(float)


def _pairs(
    data: pd.DataFrame,
    judge: str,
    case: str,
    dissented: str | None) -> pd.DataFrame:
    """Returns how many cases join each pair of judges.

    Args:
        data: the votes, a row for each judge on each case.
        judge: the column with each judge's name.
        case: the column with each vote's case.
        dissented: the column of flags of whether each judge dissented, to
            count only the cases in which one judge of the pair dissented and
            the other did not, or `None` to count every case the pair
            decided together.

    Returns:
        A table with "first" and "second" (the pair's names, in alphabetical
            order) and "cases".

    """
    votes = pd.DataFrame({
        'case': data[case],
        'judge': data[judge].astype('string'),
        'dissented': (
            cases.column_as_flags(data, dissented) if dissented
            else pd.Series(False, index = data.index))}).dropna(
                subset = ['case', 'judge'])
    joined = votes.merge(votes, on = 'case', suffixes = ('_a', '_b'))
    joined = joined[joined['judge_a'] < joined['judge_b']]
    if dissented:
        joined = joined[joined['dissented_a'] != joined['dissented_b']]
    counted = joined.groupby(['judge_a', 'judge_b']).size()
    return counted.rename('cases').reset_index().rename(
        columns = {'judge_a': 'first', 'judge_b': 'second'})


def _is_share(values: pd.Series) -> bool:
    """Returns whether a column's rate is a share of cases.

    Args:
        values: the column, as numbers.

    Returns:
        Whether every value that is not missing is 0 or 1 (a flag), so that
            its mean is the share of the cases that have it.

    """
    return bool(values.dropna().isin([0, 1]).all())


def _rate_column(item: amos.Dataset, column: str | None) -> str:
    """Returns the column whose rate a plot draws.

    Args:
        item: the cases.
        column: the column named in the plot's parameters, or `None`.

    Raises:
        KeyError: if the column is not in the data.

    Returns:
        `column`, or else the dataset's label, or else `_DEFAULT_RATE`.

    """
    chosen = column or item.label or _DEFAULT_RATE
    cases.require_columns(item.data, [chosen], 'the column of the rate')
    return str(chosen)


def _rate_name(column: str, shares: bool) -> str:
    """Returns the name of the axis of a rate.

    Args:
        column: the column whose rate is drawn.
        shares: whether the rate is a share of cases.

    Returns:
        "Share of cases: ..." for a share, and "Mean: ..." otherwise.

    """
    kind = 'Share of cases' if shares else 'Mean'
    return f'{kind}: {_words(column)}'


def _terms(start: float, stop: float) -> list[tuple[float, float, int]]:
    """Returns the presidents' terms between two years, by party.

    Args:
        start: the first year.
        stop: the year after the last one.

    Returns:
        The start and end of each term (as decimal years, cut to the range)
            and the party of the president (-1 or 1), leaving out a term of
            another party.

    """

    def decimal(day: pd.Timestamp) -> float:
        """Returns a day as a year with a fraction.

        Args:
            day: the day.

        Returns:
            The year, plus the share of it that came before the day.

        """
        return day.year + (day.dayofyear - 1) / 365.25

    terms = politics.executives()
    parties = pd.to_numeric(terms['executive_ideology'], errors = 'coerce')
    found: list[tuple[float, float, int]] = []
    for party, began, ended in zip(
            parties.tolist(), pd.to_datetime(terms['start_date']),
            pd.to_datetime(terms['end_date']), strict = True):
        if pd.isna(party) or int(party) not in _PARTY_COLORS:
            continue
        begins = decimal(began)
        ends = stop if pd.isna(ended) else decimal(ended)
        if ends > start and begins < stop:
            found.append((max(begins, start), min(ends, stop), int(party)))
    return found


def _words(column: str) -> str:
    """Returns the name of a column as words for a figure.

    Args:
        column: the column's name, such as "outcome_reversal".

    Returns:
        The name with spaces for underscores, such as "outcome reversal".

    """
    return str(column).replace('_', ' ')


def _yearly(
    data: pd.DataFrame,
    values: pd.Series,
    *,
    year: str,
    court_name: str,
    court_num: str,
    jurisdiction: str,
    how: Literal['sum', 'mean']) -> pd.DataFrame:
    """Returns a summary of values for each court in each year.

    Args:
        data: the cases.
        values: a value for each case.
        year: the column with each case's year.
        court_name: the column with courtpy's name for each case's court.
        court_num: the column with courtpy's number for each case's court.
        jurisdiction: the folder of the jurisdiction's table of courts.
        how: how to summarize each court's values in a year ("sum" or
            "mean").

    Raises:
        KeyError: if the cases have no `year` column.

    Returns:
        A table with a row for each court (by its label, in order) and a
            column for each year from the first to the last, with 0 for a
            sum (and missing for a mean) where a court has no cases.

    """
    cases.require_columns(data, [year], 'a plot over time')
    table = pd.DataFrame({
        'court': courts.court_labels(
            data, court_name = court_name, court_num = court_num,
            jurisdiction = jurisdiction),
        'year': pd.to_numeric(data[year], errors = 'coerce'),
        'value': values}).dropna(subset = ['court', 'year'])
    table['year'] = table['year'].astype('int64')
    summary = table.pivot_table(
        index = 'court', columns = 'year', values = 'value', aggfunc = how,
        observed = True)
    years = range(int(table['year'].min()), int(table['year'].max()) + 1)
    summary = summary.reindex(columns = years)
    return summary.fillna(0) if how == 'sum' else summary
