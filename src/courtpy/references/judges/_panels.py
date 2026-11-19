"""Techniques for the panels of cases and the votes of their judges.

Contents:
    CasesToJudges: makes a table with one row for each judge.
    CasesToVotes: makes a table with one row for each judge on each case.
    CodePanels: adds the judges and the composition of each case's panel.
    DocketsToVotes: makes a table with one row for each judge on each
        docket.
    VotesToCases: makes a table of votes a table of cases again.
    panel_compositions: returns the composition of each case's panel by the
        parties of the presidents who appointed its judges, such as "DDR".
    republican_appointees: returns how many judges of each case's panel a
        Republican president appointed.
    vote_table: returns a table with one row for each judge on each case.
    _CASE: column that holds the label of each row's case while a table is
        made.
    _FOUND: column that holds whether a judge was found while a table is
        made.
    _JUDGE_PREFIXES: the starts of the names of the columns that
        `vote_table` makes for each judge, which `VotesToCases` removes.
    _NAME: column that holds each judge's name while a table is made.
    _NID: the column of a table of votes with each judge's number, which
        labels the table that `CasesToJudges` makes.
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
from typing import Any, ClassVar

import amos
import numpy as np
import pandas as pd

from ...core import cases, datasets, utilities
from ...wrangler import shapers
from ._biographies import _ROW, AddBiography, by_seat
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
    the place of the judge's name in "panel_judges": "judge_name1" (the
    judge's name as the Federal Judicial Center reports it) and "judge_nid1"
    (the center's number for the judge), "judge_name2" and "judge_nid2", and
    so on (as `add_biography` numbers the judges of cases), for
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

    The judges of each case are found as `add_biography` finds them (see
    `AddBiography`), in a table with a row for each judge on each case, and
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
class CasesToVotes(shapers.Converter, amos.Shaper):
    """Makes a table with one row for each judge on each case (`Votes`).

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

    output: ClassVar[type[datasets.CourtData]] = datasets.Votes

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
class DocketsToVotes(shapers.Converter, amos.Shaper):
    """Makes a table with one row for each judge on each docket (`Votes`).

    It is `cases_to_votes` for `Dockets` (see `vote_table`): each docket of a
    case that consolidated several appeals has a row for each of the case's
    judges, so each vote has the docket's columns (such as the Integrated
    Database's, from `add_idb`). The rows are labeled by "vote_id" (the
    docket's id and the judge's place, such as "4567890-2-1"), and have
    "case_docket", "case_id", and "docket". A judge's vote on a case is counted
    once for each of its dockets, so group by "case_id" (or keep one docket
    of each case) to count each case once.

    Like every shaper, it takes "label", "task", and "groups" (such as
    "case_id", which keeps the votes of a case together).

    """

    output: ClassVar[type[datasets.CourtData]] = datasets.Votes

    def shape(
        self,
        data: pd.DataFrame,
        roster: Roster | pd.DataFrame | pathlib.Path | str | None = None,
        outcomes: Sequence[str] | str | None = None,
        **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each judge on each docket.

        Args:
            data: the table of dockets, labeled by "case_docket".
            roster: a roster, the table of one, or the path of a saved one.
                Defaults to `None`, in which case the roster saved in
                "judges" in `utilities.data_folder()` is used.
            outcomes: names of the columns with the outcomes of the cases,
                for which each judge's vote is added. Defaults to `None`, in
                which case they are the columns whose names start with
                "outcome_".
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks "case_id" or a column that is needed.

        Returns:
            The table of judges' votes.

        """
        cases.require_columns(
            data, ['case_id'], repr(self.name),
            hint = 'Make the dockets with "cases_to_dockets"')
        return vote_table(
            data, roster, outcomes = utilities.listify(outcomes) or None,
            label = 'case_docket')


@dataclasses.dataclass
class VotesToCases(shapers.Converter, amos.Shaper):
    """Makes a table of votes a table of cases again (`Cases`).

    It undoes `cases_to_votes`: the rows of each case become one row,
    labeled by "case_id" as a table of parsed cases is, with the case's
    columns in their order. The columns that `cases_to_votes` makes for
    each judge are removed: "judge", and those whose names begin with
    "judge_", "colleagues_", or "vote_" (such as "judge_party",
    "colleagues_party", "judge_dissented", and "vote_reversal"). Every other
    column is the case's, so each case keeps the value of its first row
    (for votes made from dockets, "case_docket" and "docket" are removed too,
    and other columns keep the first docket's values). A
    case with no judge who was found in the roster has no rows in the table
    of votes, so it is not in the table of cases either. To summarize the
    judges of each case instead, use `code_panels` on the cases, or
    `group_rows` on the votes.

    Like every shaper, it takes "label", "task", and "groups". Without them,
    a label of votes (such as "vote_reversal") becomes the outcome that it
    was made from ("outcome_reversal"), and the groups are those of the
    votes other than "case_id" and the judges' columns.

    """

    output: ClassVar[type[datasets.CourtData]] = datasets.Cases

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
        judged = [
            c for c in data.columns
            if _is_judge_column(c) or c in ('case_docket', 'docket')]
        table = data.drop(columns = judged).drop_duplicates(subset = 'case_id')
        return table.set_index('case_id')


@dataclasses.dataclass
class CasesToJudges(shapers.Converter, amos.Shaper):
    """Makes a table with one row for each judge (`Judges`).

    The rows of each judge in a table of votes (see `vote_table`) become one
    row, labeled by "judge_nid" (the Federal Judicial Center's number for the
    judge), with "judge" (the judge's name), "cases" (the number of the
    judge's votes), and the means of the columns of numbers and booleans, as
    `group_rows` takes them (see `courtpy.shapers.summarize`). The mean of a
    boolean is a share: "vote_reversal" is the share of the judge's votes to
    reverse, "judge_dissented" the share of the judge's cases in which the
    judge dissented, "type_criminal" the share of the judge's cases that
    were criminal, "party_type_corporation" (if the parties have types) the
    share with a corporation as a party, and "judge_age" the judge's mean
    age when deciding them. Nothing about any one case is kept: columns of
    text (such as the cases' names and dates) and ids (such as "case_id")
    are left out, unless "keep" or "how" names them.

    If the data is a table of cases (it has no "judge_nid" column), the
    table of votes is made first, as `cases_to_votes` makes it, with
    "roster" and "outcomes".

    Like every shaper, it takes "label", "task", and "groups". Without
    "groups", the table has none, since the groups of votes (such as
    "case_id") are not columns of it. Without "task", the task is inferred
    from the label, since a label that was a vote is now a share.

    """

    output: ClassVar[type[datasets.CourtData]] = datasets.Judges

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
        *,
        how: Mapping[str, Any] | None = None,
        keep: Sequence[str] | str | None = None,
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
                place of the means or add columns, such as
                {"court": "list"}. Defaults to `None`.
            keep: columns of text to keep, with the first value of each
                judge's votes. Defaults to `None`, which keeps "judge".
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
        votes = shapers.add_party_type_flags(votes)
        kept = ['judge'] if keep is None else utilities.listify(keep)
        table = shapers.summarize(
            votes, [_NID], how = how, keep = kept, count = count)
        first = [c for c in ('judge', count) if c is not None and c in table]
        return table[[*first, *[c for c in table.columns if c not in first]]]


""" Public Functions """


def panel_compositions(
    data: pd.DataFrame,
    size: int = 3) -> pd.Series:
    """Returns the composition of each case's panel by its judges' parties.

    The composition names the party of the president who appointed each
    judge, Democratic ("D") ones first: "DDD", "DDR", "DRR", and "RRR" for a
    panel of three (see `republican_appointees`).

    Args:
        data: the cases, with "judge_party1" and so on (from
            `add_biography`) or "panel_party" and "panel_found" (from
            `code_panels`).
        size: the number of judges on the panels to describe. Defaults to 3.

    Returns:
        The composition of each case's panel, as an ordered category from all
            Democratic appointees to all Republican ones, missing for a case
            whose panel is not of `size` judges whose parties are known.

    """
    found = republican_appointees(data, size)
    names = ['D' * (size - r) + 'R' * r for r in range(size + 1)]
    # The number of Republican appointees is the place of the composition
    # among `names`, and -1 marks a missing one.
    codes = found.fillna(-1).astype('int64').to_numpy()
    return pd.Series(
        pd.Categorical.from_codes(
            codes, categories = pd.Index(names), ordered = True),
        index = data.index, name = 'panel_composition')


def republican_appointees(
    data: pd.DataFrame,
    size: int = 3) -> pd.Series:
    """Returns how many judges of each case's panel a Republican appointed.

    The judges' parties are those of the presidents who appointed them (-1
    for a Democrat and 1 for a Republican). They are read from each seat's
    "judge_party1", "judge_party2", and so on (which `add_biography` adds to
    cases), or else from "panel_party" (the mean party) and "panel_found"
    (the number of judges found), which `code_panels` adds.

    Args:
        data: the cases.
        size: the number of judges on the panels to count. Defaults to 3.

    Raises:
        KeyError: if `data` has neither the parties of the seats nor
            "panel_party" and "panel_found".

    Returns:
        The number of Republican appointees on each case's panel, as whole
            numbers, missing for a case whose panel is not of `size` judges
            whose parties are all known (as for a judge appointed by a
            president of another party).

    """
    seats = [f'judge_party{n}' for n in range(1, size + 1)]
    if all(c in data.columns for c in seats):
        parties = data[seats].apply(pd.to_numeric, errors = 'coerce')
        complete = parties.isin([-1, 1]).all(axis = 1)
        # A panel with more seats than `size` is a panel of another size.
        extra = f'judge_party{size + 1}'
        if extra in data.columns:
            complete &= pd.to_numeric(data[extra], errors = 'coerce').isna()
        counted = (parties == 1).sum(axis = 1)
        seated: pd.Series = counted.where(complete).astype('Int64')
        return seated.rename('republican_appointees')
    if 'panel_party' in data.columns and 'panel_found' in data.columns:
        party = pd.to_numeric(data['panel_party'], errors = 'coerce')
        found = pd.to_numeric(data['panel_found'], errors = 'coerce')
        counted = (found * (party + 1) / 2).round()
        averaged: pd.Series = counted.where(found == size).astype('Int64')
        return averaged.rename('republican_appointees')
    message = (
        f'counting the Republican appointees of panels needs {seats} (from '
        f'add_biography) or "panel_party" and "panel_found" (from '
        f'code_panels)')
    raise KeyError(message)


def vote_table(
    data: pd.DataFrame,
    roster: Roster | pd.DataFrame | pathlib.Path | str | None = None,
    *,
    outcomes: Sequence[str] | None = None,
    label: str = 'case_id') -> pd.DataFrame:
    """Returns a table with one row for each judge on each case.

    Each name in "panel_judges" is matched to a judge in a roster (see
    `Roster`), and each judge who is found gets a row, labeled by the case's
    id and the judge's place among them (such as "4567890-2"). Cases with no
    judge who is found are left out. The table is made as `amos` reshapes
    and merges data: the `lists_to_rows` technique makes a row for each name,
    and `add_biography` (see `AddBiography`) adds the judge that each
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
        label: the name of the column of the labels of the rows of `data`
            (which the rows of each case's judges share). Defaults to
            "case_id". For a table of dockets, it is "case_docket", and
            their "case_id" column is kept.

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
        [f'{row}-{place}' for row, place in zip(
            labels, places, strict = True)],
        name = 'vote_id', dtype = object)
    votes = pd.DataFrame({
        label: labels.to_numpy(),
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


def _is_judge_column(column: Any) -> bool:
    """Returns whether a column of a table of votes is about one judge.

    Args:
        column: the name of the column.

    Returns:
        Whether it is "judge" or begins with one of `_JUDGE_PREFIXES`.

    """
    name = str(column)
    return name == 'judge' or name.startswith(_JUDGE_PREFIXES)


def _named(
    data: pd.DataFrame,
    column: str,
    roster: Roster,
    columns: Sequence[str] = (),
    *,
    unmatched: bool = False) -> pd.DataFrame:
    """Finds the judges that a column of the cases names.

    The `lists_to_rows` technique of `amos` makes a row for each name that a
    case lists, and `AddBiography` finds the judge that each name refers to.

    Args:
        data: the parsed cases, with "court_num" and "year".
        column: name of the column that lists judges' names: text with
            "; " between the names, as the federal rules write them, or
            lists of names (as `split_values` makes them).
        roster: the roster to find the judges in.
        columns: the columns to add for each judge, other than "nid" (see
            `AddBiography`). Defaults to an empty `tuple`.
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
    merged = AddBiography().apply(
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
        A table with a row for each case, in order, and "judge_name1",
            "judge_nid1", "judge_name2", "judge_nid2", and so on, numbered by
            the places of the names in the cases' lists, for as many as the
            longest list has (see `by_seat`). A name that was not matched
            leaves its place missing. It has no columns if `panel` has no
            rows.

    """
    seated = pd.DataFrame({
        _ROW: panel[_CASE].to_numpy(),
        _SEAT: panel[_SEAT].to_numpy(),
        'judge_name': panel['judge'].astype(object).array,
        'judge_nid': panel['nid'].astype('Int64').array})
    return by_seat(seated, size)


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
