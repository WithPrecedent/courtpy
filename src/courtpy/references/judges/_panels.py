"""Techniques for the panels of cases and the votes of their judges.

Contents:
    CodePanels: adds the judges and the composition of each case's panel.
    ReshapeByJudge: makes a table with one row for each judge.
    ReshapeByPanel: makes a table of votes a table of cases again.
    ReshapeByVotes: makes a table with one row for each judge on each case.
    vote_table: returns a table with one row for each judge on each case.
    _CASE: column that holds the label of each row's case while a table is
        made.
    _FOUND: column that holds whether a judge was found while a table is
        made.
    _JUDGE_PREFIXES: the starts of the names of the columns that
        `vote_table` makes for each judge, which `ReshapeByPanel` removes.
    _NAME: column that holds each judge's name while a table is made.
    _NID: the column of a table of votes with each judge's number, which
        labels the table that `ReshapeByJudge` makes.
    _OTHER: column that holds the place of the other judge of each pair
        while a table is made.
    _PLACE: column that holds each judge's place on a panel while a table
        is made.
    _ROLES: the columns of the judges' roles in a case (such as "authors"),
        with the columns of flags that `vote_table` makes from them.
    _SEAT: column that holds each judge's seat on a panel while a table is
        made.

"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Mapping, Sequence
from typing import Any

import amos
import numpy as np
import pandas as pd

from ...core import cases, utilities
from ._biographies import MergeBiographies
from ._roster import Roster

# Names of the columns that the techniques add to the tables that they make
# on the way to their results, which no table of cases or roster has.
_CASE: str = '__case__'
_FOUND: str = '__found__'
_NAME: str = '__name__'
_OTHER: str = '__other__'
_PLACE: str = '__place__'
_SEAT: str = '__seat__'
_ROLES: dict[str, str] = {
    'authors': 'judge_author',
    'concurring': 'judge_concurred',
    'dissenting': 'judge_dissented'}
# The column of a table of votes with the Federal Judicial Center's number
# for each judge, which labels a table of judges.
_NID: str = 'judge_nid'
# The starts of the names of the columns that `vote_table` makes for each
# judge (with "judge" itself), which a table of cases does not have.
_JUDGE_PREFIXES: tuple[str, ...] = ('judge_', 'colleagues_', 'vote_')


@dataclasses.dataclass
class CodePanels(amos.Munger):
    """Adds the judges and the composition of each case's panel.

    Each name in "panel_judges" is matched to a judge in a roster (see
    `Roster`) with the case's court and year. The judges who are found are
    listed in "panel_names" (as the roster names them, such as "Lynch, Sandra
    Lea"), and "panel_found" is how many there are, which can be compared
    with "panel_size". Each of them also has columns of its own, numbered by
    the place of the judge's name in "panel_judges": "judge1" (the judge's
    name as the Federal Judicial Center reports it) and "judge1_nid" (the
    center's number for the judge), "judge2" and "judge2_nid", and so on, for
    as many names as the longest panel lists. A name that is not matched
    leaves its place missing, so the judges after it keep theirs, and a case
    with fewer names has missing values in the rest. For each attribute in
    the roster, "panel_{attribute}" is its mean among those judges:
    "panel_woman" is the share of the judges who are women, and "panel_party"
    is the mean party of the presidents who appointed them (-1 for a Democrat
    and 1 for a Republican). So are
    "panel_age", "panel_senior", "panel_designated", and
    "panel_district_judge" (see `Roster.describe`). A mean is missing if no
    judge was found (or none has the attribute).

    If the cases have "authors", "concurring", or "dissenting" columns, the
    judges they name are added as "author_name" (the first author found),
    "concurring_names", and "dissenting_names".

    The judges of each case are found as `merge_biographies` finds them (see
    `MergeBiographies`), in a table with a row for each judge on each case, and
    the case gets summaries of its rows (as the `merge_summary` technique of
    `amos` adds them).

    Needs "panel_judges", "court_num", and "year".

    """

    def munge(
        self,
        data: pd.DataFrame,
        roster: Roster | pd.DataFrame | pathlib.Path | str | None = None,
        **kwargs: Any) -> pd.DataFrame:
        """Adds the judges and the composition of each panel.

        Args:
            data: the parsed cases.
            roster: a roster, the table of one, or the path of a saved one.
                Defaults to `None`, in which case the roster saved in
                "judges" in `utilities.data_folder()` is used.
            **kwargs: not used.

        Returns:
            The cases, with the new columns.

        """
        cases.require_columns(
            data, ['panel_judges', 'court_num', 'year'], self.name)
        judges = Roster.create(roster)
        described = judges.described
        seated = _named(
            data, 'panel_judges', judges, ['judge', *described],
            unmatched = True)
        panel = seated[seated['nid'].notna()].astype({'nid': 'int64'})
        panels = _summarize(
            panel,
            len(data),
            {'judge': 'list', **dict.fromkeys(described, 'mean')},
            count = _FOUND)
        names = {
            column: _summarize(
                _named(data, column, judges, ['judge']),
                len(data),
                {'judge': 'list'})['judge'].tolist()
            for column in _ROLES if column in data.columns}
        data['panel_names'] = pd.Series(
            panels['judge'].tolist(), index = data.index, dtype = object)
        data['panel_found'] = panels[_FOUND].to_numpy()
        for column, values in _numbered(seated, len(data)).items():
            data[column] = pd.Series(values.array, index = data.index)
        if 'authors' in names:
            data['author_name'] = pd.Series(
                [found[0] if found else None for found in names['authors']],
                index = data.index, dtype = object)
        for column in ('concurring', 'dissenting'):
            if column in names:
                data[f'{column}_names'] = pd.Series(
                    names[column], index = data.index, dtype = object)
        for name in described:
            data[f'panel_{name}'] = panels[name].to_numpy(dtype = 'float64')
        return data


@dataclasses.dataclass
class ReshapeByVotes(amos.Shaper):
    """Makes a table with one row for each judge on each case.

    The table is for studying how judges vote, rather than what courts
    decide. See `vote_table` for its columns. It replaces the table of cases,
    so it should come after the techniques that code the cases (such as
    `code_outcome`) and, like every shaper of `amos`, before the data is
    split. Its "case_id" column can be the "groups" of a study, which keeps
    the judges of a case together.

    Like every shaper, it takes "label", "task", and "groups", which name the
    label and groups of the table of votes (such as "vote_reversal" and
    "case_id"). Without them, the dataset keeps the label and groups that it
    has.

    """

    def shape(
        self,
        data: pd.DataFrame,
        roster: Roster | pd.DataFrame | pathlib.Path | str | None = None,
        outcomes: Sequence[str] | str | None = None,
        **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each judge on each case.

        Args:
            data: the parsed cases.
            roster: a roster, the table of one, or the path of a saved one.
                Defaults to `None`, in which case the roster saved in
                "judges" in `utilities.data_folder()` is used.
            outcomes: names of the columns with the outcomes of the cases,
                for which each judge's vote is added. Defaults to `None`, in
                which case they are the columns whose names start with
                "outcome_".
            **kwargs: not used.

        Returns:
            The table of judges' votes.

        """
        return vote_table(
            data, roster, outcomes = utilities.listify(outcomes) or None)


@dataclasses.dataclass
class ReshapeByPanel(amos.Shaper):
    """Makes a table of votes a table of cases again.

    It undoes `reshape_by_votes`: the rows of each case become one row,
    labeled by "case_id" as a table of parsed cases is, with the case's
    columns in their order. The columns that `reshape_by_votes` makes for
    each judge are removed: "judge", and those whose names begin with
    "judge_", "colleagues_", or "vote_" (such as "judge_party",
    "colleagues_party", "judge_dissented", and "vote_reversal"). Every other
    column is the case's, so each case keeps the value of its first row. A
    case with no judge who was found in the roster has no rows in the table
    of votes, so it is not in the table of cases either. To summarize the
    judges of each case instead, use `code_panels` on the cases, or
    `group_rows` on the votes.

    Like every shaper, it takes "label", "task", and "groups". Without them,
    a label of votes (such as "vote_reversal") becomes the outcome that it
    was made from ("outcome_reversal"), and the groups are those of the
    votes other than "case_id" and the judges' columns.

    """

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        label: str | None = None,
        groups: Sequence[str] | str | None = None,
        **kwargs: Any) -> amos.Dataset:
        """Makes the table of votes of `item` a table of cases.

        Args:
            item: the dataset of votes.
            label: name of the label of the cases. Defaults to `None`, in
                which case it is the outcome that the label of the votes was
                made from, if it was made from one, and otherwise the label
                of `item`.
            groups: names of the groups of the cases. Defaults to `None`, in
                which case they are the groups of `item` that are columns of
                the cases.
            **kwargs: "task", and parameters for `shape`.

        Returns:
            The dataset of cases.

        """
        if label is None and item.label is not None:
            outcome = 'outcome_' + str(item.label).removeprefix('vote_')
            if (str(item.label).startswith('vote_')
                    and outcome in item.data.columns):
                label = outcome
        if groups is None:
            groups = [
                group for group in item.groups
                if group != 'case_id' and not _is_judge_column(group)]
        return super().apply(item, label = label, groups = groups, **kwargs)

    def shape(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each case.

        Args:
            data: the table of votes (see `vote_table`).
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks "case_id".

        Returns:
            The table of cases, labeled by "case_id".

        """
        cases.require_columns(data, ['case_id'], repr(self.name))
        judged = [c for c in data.columns if _is_judge_column(c)]
        table = data.drop(columns = judged).drop_duplicates(subset = 'case_id')
        return table.set_index('case_id')


@dataclasses.dataclass
class ReshapeByJudge(amos.Shaper):
    """Makes a table with one row for each judge.

    The rows of each judge in a table of votes (see `vote_table`) become one
    row, labeled by "judge_nid" (the Federal Judicial Center's number for the
    judge), with "judge" (the judge's name), "cases" (the number of the
    judge's votes), and summaries of the other columns, as `group_rows`
    takes them. A column that has one value among each judge's votes keeps
    it (such as "judge_woman", or "court" for judges of one court). Of the
    other columns of numbers and booleans, the mean is taken, which is a
    share for a boolean: "vote_reversal" is the share of the judge's votes
    to reverse, "judge_dissented" the share of the judge's cases in which
    the judge dissented, and "judge_age" the judge's mean age when deciding
    them. Columns of text or lists that differ among a judge's votes (such
    as "case_id" and the cases' names) are left out, and so are ids (columns
    whose names end with "_id"), unless "how" names a summary for them.

    If the data is a table of cases (it has no "judge_nid" column), the
    table of votes is made first, as `reshape_by_votes` makes it, with
    "roster" and "outcomes".

    Like every shaper, it takes "label", "task", and "groups". Without
    "groups", the table has none, since the groups of votes (such as
    "case_id") are not columns of it. Without "task", the task is inferred
    from the label, since a label that was a vote is now a share.

    """

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        task: str | None = None,
        groups: Sequence[str] | str | None = None,
        **kwargs: Any) -> amos.Dataset:
        """Makes the table of `item` a table of judges.

        Args:
            item: the dataset of votes or of cases.
            task: "classify" or "regress". Defaults to `None`, in which case
                it is inferred from the label (see `amos.Dataset.infer_task`).
            groups: names of the groups of the judges. Defaults to `None`,
                for none.
            **kwargs: "label", and parameters for `shape`.

        Returns:
            The dataset of judges.

        """
        dataset = super().apply(
            item, task = task, groups = [] if groups is None else groups,
            **kwargs)
        if task is None and dataset.label is not None:
            dataset.task = dataset.infer_task()
        return dataset

    def shape(
        self,
        data: pd.DataFrame,
        roster: Roster | pd.DataFrame | pathlib.Path | str | None = None,
        outcomes: Sequence[str] | str | None = None,
        how: Mapping[str, Any] | None = None,
        count: str | None = 'cases',
        **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each judge.

        Args:
            data: a table of votes (see `vote_table`), or the parsed cases.
            roster: for a table of cases, a roster, the table of one, or the
                path of a saved one. Defaults to `None`, in which case the
                roster saved in "judges" in `utilities.data_folder()` is
                used.
            outcomes: for a table of cases, names of the columns with the
                outcomes of the cases, for which each judge's vote is added.
                Defaults to `None`, in which case they are the columns whose
                names start with "outcome_".
            how: the summaries of columns, by their names, which take the
                place of the usual ones (see `group_rows`), such as
                {"court": "list"}. Defaults to `None`.
            count: name of the column with the number of each judge's votes,
                or `None` for no such column. Defaults to "cases".
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks a column that is needed or named.

        Returns:
            The table of judges, labeled by "judge_nid".

        """
        votes = data if _NID in data.columns else vote_table(
            data, roster, outcomes = utilities.listify(outcomes) or None)
        votes = votes.reset_index(drop = True)
        chosen = dict(how or {})
        summarized = [
            column for column in votes.columns
            if column != _NID and (
                column in chosen or column == 'judge'
                or _is_number(votes[column], column))]
        others = [
            column for column in votes.columns
            if column != _NID and column not in summarized]
        constant = _constant(votes, _NID, others)
        kept = [
            column for column in votes.columns
            if column in summarized or column in constant]
        table = amos.shapers.GroupRows().shape(
            votes[[_NID, *kept]], by = _NID, how = chosen or None,
            count = count)
        first = [c for c in ('judge', count) if c is not None and c in table]
        ordered = [_NID, *first, *[
            c for c in table.columns if c != _NID and c not in first]]
        return table[ordered].set_index(_NID)


""" Public Functions """


def vote_table(
    data: pd.DataFrame,
    roster: Roster | pd.DataFrame | pathlib.Path | str | None = None,
    *,
    outcomes: Sequence[str] | None = None) -> pd.DataFrame:
    """Returns a table with one row for each judge on each case.

    Each name in "panel_judges" is matched to a judge in a roster (see
    `Roster`), and each judge who is found gets a row, labeled by the case's
    id and the judge's place among them (such as "4567890-2"). Cases with no
    judge who is found are left out. The table is made as `amos` reshapes
    and merges data: the `lists_to_rows` technique makes a row for each name,
    and `merge_biographies` (see `MergeBiographies`) adds the judge that each
    name refers to. The columns are:

    | Column | Meaning |
    | --- | --- |
    | `case_id` | The case's id, which the rows of its judges share. |
    | `judge`, `judge_nid` | The judge's name and number in the roster. |
    | (the columns of `data`) | The case's columns, repeated for each judge. |
    | `judge_{attribute}` | Each attribute of the judge (see `Roster.describe`), such as `judge_party`, `judge_woman`, and `judge_age`. |
    | `colleagues_{attribute}` | The mean of the attribute among the other judges of the panel who were found. Missing if there are none. |
    | `judge_author`, `judge_concurred`, `judge_dissented` | Whether the judge wrote the opinion of the court, and wrote or joined a concurrence or a dissent. A judge who concurred in part and dissented in part did both. |
    | `vote_{outcome}` | For each outcome of the case, how the judge voted: the outcome itself, or its opposite if the judge dissented. So with "outcome_reversal", `vote_reversal` is whether the judge voted to reverse. Missing if the outcome is. |

    Args:
        data: the parsed cases, which need "panel_judges", "court_num", and
            "year". "authors", "concurring", and "dissenting" are used if
            they are there.
        roster: a roster, the table of one, or the path of a saved one.
            Defaults to `None`, in which case the roster saved in "judges" in
            `utilities.data_folder()` is used.
        outcomes: names of the columns with the outcomes of the cases.
            Defaults to `None`, in which case they are the columns whose
            names start with "outcome_".

    Raises:
        KeyError: if `data` lacks a column that is needed or named.

    Returns:
        The table, labeled by "vote_id".

    """
    cases.require_columns(
        data, ['panel_judges', 'court_num', 'year'], 'a table of votes')
    if outcomes is None:
        outcomes = [c for c in data.columns if str(c).startswith('outcome_')]
    cases.require_columns(data, outcomes, 'a table of votes')
    judges = Roster.create(roster)
    described = judges.described
    panel = _named(data, 'panel_judges', judges, ['judge', *described])
    origins = panel[_CASE].to_numpy()
    labels = data.index[origins]
    places = (panel.groupby(_CASE).cumcount() + 1).tolist()
    index = pd.Index(
        [f'{label}-{place}' for label, place in zip(
            labels, places, strict = True)],
        name = 'vote_id', dtype = object)
    votes = pd.DataFrame({
        'case_id': labels.to_numpy(),
        'judge': panel['judge'].to_numpy(),
        'judge_nid': panel['nid'].to_numpy()}, index = index)
    numbers = pd.concat([
        panel[described].add_prefix('judge_'),
        _colleagues(panel, described).add_prefix('colleagues_')], axis = 1)
    made = numbers[[
        f'{kind}_{name}' for name in described
        for kind in ('judge', 'colleagues')]].astype('float64')
    made.index = index
    # Whether each judge is one of the judges that each kind of opinion
    # names, which are found in the roster as the judges of the panel are.
    keys = pd.MultiIndex.from_arrays([origins, votes['judge_nid']])
    for column, role in _ROLES.items():
        made[role] = False
        if column in data.columns:
            acted = _named(data, column, judges)
            made[role] = keys.isin(
                pd.MultiIndex.from_arrays([acted[_CASE], acted['nid']]))
    repeated = data.iloc[origins].drop(columns = [
        c for c in data.columns if c in votes.columns or c in made.columns])
    repeated.index = index
    table = pd.concat([votes, repeated, made], axis = 1)
    dissented = table['judge_dissented'].astype('boolean')
    for column in outcomes:
        name = str(column).removeprefix('outcome_')
        table[f'vote_{name}'] = table[column].astype('boolean') ^ dissented
    return table


""" Private Functions """


def _colleagues(panel: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """Returns the means of columns among the other judges of each case.

    Each judge is paired with every other judge of the same case, and the
    means are taken of the pairs of each judge.

    Args:
        panel: a table with a row for each judge on each case (as `_named`
            returns it), labeled 0, 1, 2, and so on.
        columns: names of the columns of numbers to take the means of.

    Returns:
        A table with a row for each row of `panel`, in order, and a column
            for each of `columns` with the mean of the values that are known
            among the other judges of the row's case. It is missing if there
            are no other judges, or none has a value.

    """
    place = panel.groupby(_CASE).cumcount()
    judges = pd.DataFrame({_CASE: panel[_CASE], _PLACE: place})
    pairs = judges.merge(
        panel[[_CASE, *columns]].assign(**{_OTHER: place}), on = _CASE)
    pairs = pairs[pairs[_PLACE] != pairs[_OTHER]]
    means = pairs.groupby([_CASE, _PLACE])[list(columns)].mean()
    others: pd.DataFrame = means.reindex(
        pd.MultiIndex.from_frame(judges)).reset_index(drop = True)
    return others


def _constant(
    data: pd.DataFrame,
    key: str,
    columns: Sequence[str]) -> list[str]:
    """Returns the columns that have one value among each group's rows.

    Args:
        data: the table.
        key: the column that says which group each row belongs to.
        columns: the columns to check.

    Returns:
        Those of `columns`, in order, whose values (missing ones included)
            are the same in every row of each group. A column with lists (or
            other values that cannot be compared as wholes) is left out.

    """
    whole = [
        column for column in columns
        if data[column].dtype != object
        or not data[column].map(_is_container).any()]
    if not whole:
        return []
    counts = data.groupby(key, sort = False)[whole].nunique(dropna = False)
    return [column for column in whole if bool((counts[column] <= 1).all())]


def _is_container(value: Any) -> bool:
    """Returns whether a value holds other values, such as a list.

    Args:
        value: a value of a table.

    Returns:
        Whether it is a list, tuple, set, `dict`, or array.

    """
    return isinstance(value, list | tuple | set | frozenset | dict | np.ndarray)


def _is_judge_column(column: Any) -> bool:
    """Returns whether a column of a table of votes is about one judge.

    Args:
        column: the name of the column.

    Returns:
        Whether it is "judge" or begins with one of `_JUDGE_PREFIXES`.

    """
    name = str(column)
    return name == 'judge' or name.startswith(_JUDGE_PREFIXES)


def _is_number(values: pd.Series, column: Any) -> bool:
    """Returns whether a column is numbers or booleans that can be averaged.

    Args:
        values: the column.
        column: the name of the column.

    Returns:
        Whether it is numbers or booleans and is not an id (a column whose
            name is "id" or ends with "_id").

    """
    name = str(column)
    return (
        pd.api.types.is_numeric_dtype(values.dtype)
        and name != 'id' and not name.endswith('_id'))


def _named(
    data: pd.DataFrame,
    column: str,
    roster: Roster,
    columns: Sequence[str] = (),
    *,
    unmatched: bool = False) -> pd.DataFrame:
    """Finds the judges that a column of the cases names.

    The `lists_to_rows` technique of `amos` makes a row for each name that a
    case lists, and `MergeBiographies` finds the judge that each name refers to.

    Args:
        data: the parsed cases, with "court_num" and "year".
        column: name of the column that lists judges' names: text with
            "; " between the names, as the federal rules write them, or
            lists of names (as `split_values` makes them).
        roster: the roster to find the judges in.
        columns: the columns to add for each judge, other than "nid" (see
            `MergeBiographies`). Defaults to an empty `tuple`.
        unmatched: whether to keep the names that are not matched, with
            missing values. Defaults to `False`.

    Returns:
        A table with a row for each judge who was found (and, with
            `unmatched`, each name that was not), in the order of the cases
            and then of the names, with each judge once for a case. Its
            columns are the position of the judge's case in `data`, the
            place of the judge's name in the case's list (1 for the first),
            the judge's "nid" (missing for a name that was not matched), and
            `columns`, and its rows are labeled 0, 1, 2, and so on.

    """
    names = pd.DataFrame({
        _CASE: np.arange(len(data)),
        _NAME: pd.Series(data[column].tolist(), dtype = object),
        'court_num': pd.Series(data['court_num'].tolist(), dtype = object),
        'year': pd.Series(data['year'].tolist(), dtype = object)})
    listed = amos.shapers.ListsToRows().shape(
        names, column = _NAME, separator = cases._SEPARATOR.strip())
    # A case with no names has one row, whose name is missing, so each name's
    # place is its row among its case's.
    listed[_SEAT] = listed.groupby(_CASE).cumcount() + 1
    merged = MergeBiographies().apply(
        amos.Dataset(listed),
        source = roster,
        name = _NAME,
        columns = ['nid', *columns],
        prefix = None,
        indicator = _FOUND).data
    repeated = merged[_FOUND] & merged.duplicated([_CASE, 'nid'])
    kept = (merged[_FOUND] | (unmatched & merged[_NAME].notna())) & ~repeated
    found: pd.DataFrame = merged[kept][[_CASE, _SEAT, 'nid', *columns]]
    return found.astype(
        {'nid': 'Int64' if unmatched else 'int64'}).reset_index(drop = True)


def _numbered(panel: pd.DataFrame, size: int) -> pd.DataFrame:
    """Returns the name and number of each judge of each case, in columns.

    Args:
        panel: a table with a row for each name on each case, with "judge"
            and "nid" (as `_named` returns it with `unmatched`).
        size: the number of cases.

    Returns:
        A table with a row for each case, in order, and "judge1",
            "judge1_nid", "judge2", "judge2_nid", and so on, numbered by the
            places of the names in the cases' lists, for as many as the
            longest list has. A name that was not matched leaves its place
            missing. It has no columns if `panel` has no rows.

    """
    place = panel[_SEAT].to_numpy()
    columns: dict[str, pd.Series] = {}
    for number in range(1, int(place.max(initial = 0)) + 1):
        judges = panel[place == number].set_index(_CASE)
        columns[f'judge{number}'] = judges['judge'].astype(object).reindex(
            range(size))
        columns[f'judge{number}_nid'] = judges['nid'].astype('Int64').reindex(
            range(size))
    return pd.DataFrame(columns, index = pd.RangeIndex(size))


def _summarize(
    named: pd.DataFrame,
    size: int,
    how: Mapping[str, str],
    count: str | None = None) -> pd.DataFrame:
    """Returns summaries of the judges of each case.

    The `merge_summary` technique of `amos` adds summaries of the rows of
    another table that have the same keys: here, of the judges of each case.

    Args:
        named: a table with a row for each judge on each case (as `_named`
            returns it).
        size: the number of cases.
        how: the summary to take of each column of `named` to summarize,
            such as "mean" or "list", by the name of the column.
        count: name of a column to make with the number of judges of each
            case. Defaults to `None`, which makes no such column.

    Returns:
        A table with a row for each case, in order, and the summaries of its
            judges as columns. A case with no judges has an empty `list` for
            a "list", no judges for `count`, and other summaries that are
            missing.

    """
    table = amos.Dataset(pd.DataFrame({_CASE: np.arange(size)}))
    if named.empty:
        # There is nothing to summarize, so every summary is missing.
        blank = pd.DataFrame(
            np.nan, index = table.data.index,
            columns = [*how, *([count] if count else [])])
        table.replace(pd.concat([table.data, blank], axis = 1))
    else:
        amos.mergers.MergeSummary().apply(
            table, source = named, on = _CASE, how = dict(how), count = count)
    summaries = table.data.drop(columns = _CASE)
    for column, summary in how.items():
        if summary == 'list':
            summaries[column] = pd.Series(
                [found if isinstance(found, list) else []
                 for found in summaries[column].tolist()],
                index = summaries.index, dtype = object)
    if count is not None:
        summaries[count] = summaries[count].fillna(0).astype('int64')
    return summaries
