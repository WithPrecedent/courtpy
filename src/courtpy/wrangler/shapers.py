"""Shapers that make dockets of cases, and summarize cases.

`cases_to_dockets` makes a row for each docket number of each case
(`Dockets`), as records kept by docket (such as the Integrated Database that
`add_idb` adds) need, and `dockets_to_cases` makes the dockets cases again.

The other shapers summarize cases by court, case type, and party type.

Like every shaper of `amos`, each makes a new table from the data and must
come before the data is split. Each returns a courtpy dataset of the kind
that its rows are (see `courtpy.datasets`), and none of them can be undone:
the rows summarize many cases and keep nothing about any one case (such as
its docket number, its date, or its parties' names). Only columns of numbers
and booleans are summarized (by their means, so the mean of a boolean is a
share), along with the columns named in "keep" or "how":

| Technique | One row for each | Labeled by |
| --- | --- | --- |
| `cases_to_courts` | Court, with "cases", "judges" (if `code_panels` found them), and the means of its cases' columns. | `court_num` |
| `cases_to_case_types` | Case type (see `code_case_type`), with "cases" and the means of its cases' columns. A case of several types counts for each. | `case_type` |
| `cases_to_party_types` | Party type ("party1_type" and "party2_type"), with "parties", the share of them that won ("party_won"), the means of their other columns (such as "party_appealing"), and the means of their cases' columns. | `party_type` |

Each takes "by", other columns to group by as well, so `by = year` makes a
row for each court (or type) in each year.

The shares of each case type and party type are among the means, so a table
of courts (or of judges, made by `cases_to_judges`) shows the mix of cases
that each court (or judge) decides: "type_criminal" is the share of its
cases that are criminal, and "party_type_corporation" the share with a
corporation as a party.

Contents:
    CasesToCaseTypes: makes a table with one row for each case type.
    CasesToCourts: makes a table with one row for each court.
    CasesToDockets: makes a table with one row for each docket number of
        each case.
    CasesToPartyTypes: makes a table with one row for each party type.
    Converter: makes a shaper return a courtpy dataset of the kind it makes.
    DocketsToCases: makes a table of dockets a table of cases again.
    add_party_type_flags: adds whether a party of each type is in each case.
    summarize: returns a table with one row for each group of rows.
    _DOCKET: pattern of a docket number, such as "17-1234".
    _DOCKET_COLUMNS: the columns that `CasesToDockets` makes, which
        `DocketsToCases` removes.
    _ID: pattern of the names of columns that identify something, which
        are not summarized.
    _PARTY_TYPE: the start of the names of the columns of each party's
        type.
    _SIDE: column that says which side each party is on while a table is
        made.
    _SIDES: the starts of the names of the columns of each side's party.

"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

import amos
import numpy as np
import pandas as pd

from ..core import cases, datasets, utilities

_DOCKET: re.Pattern[str] = re.compile(r'\d+-\d+')
_DOCKET_COLUMNS: tuple[str, ...] = ('case_docket', 'docket')
_ID: re.Pattern[str] = re.compile(r'(?:^|_)(?:id|nid|num)\d*$')
_PARTY_TYPE: str = 'party_type'
_SIDE: str = '__side__'
_SIDES: tuple[str, ...] = ('party1', 'party2')


class Converter:
    """Makes a shaper return a courtpy dataset of the kind that it makes.

    A shaper of courtpy subclasses it before `amos.Shaper` (as in
    `class CasesToVotes(Converter, amos.Shaper)`) and sets `output`. It is a
    mixin rather than a base class so that the shaper stays a shaper in the
    `amos` library.

    Attributes:
        output: the kind of dataset that the shaper makes.

    """

    output: ClassVar[type[datasets.CourtData]]

    """ Public Methods """

    def apply(self, item: amos.Dataset, **kwargs: Any) -> amos.Dataset:
        """Reshapes `item` and returns it as a dataset of `output`.

        Args:
            item: the dataset to reshape.
            **kwargs: parameters of the shaper.

        Returns:
            The reshaped dataset, as a dataset of `output`.

        """
        shaped = super().apply(item, **kwargs)  # type: ignore[misc]
        return self.output.adopt(shaped)


@dataclasses.dataclass
class CasesToDockets(Converter, amos.Shaper):
    """Makes a table with one row for each docket number of each case.

    A case that decided several consolidated appeals has several docket
    numbers ("docket_numbers", with "; " between them, as the rules find
    them, or else those in the text of "docket_number"). The
    `lists_to_rows` technique of `amos` makes a row for each, labeled by
    "case_docket" (the case's id and the docket's place, such as "4567890-2"),
    with "case_id", "docket" (the row's one docket number), and the case's
    other columns. "docket_numbers" is left out, so each row has only its
    own docket number. A case with no docket number keeps one row, whose
    "docket" is missing, so `dockets_to_cases` can make every case again.

    Like every shaper, it takes "label", "task", and "groups". Its "case_id"
    column can be the "groups" of a study, which keeps the dockets of a case
    together.

    """

    output: ClassVar[type[datasets.CourtData]] = datasets.Dockets

    def shape(
        self,
        data: pd.DataFrame,
        column: str | None = None,
        **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each docket number of each case.

        Args:
            data: the cases, labeled by their ids.
            column: the column with each case's docket numbers: lists, or
                text in which each "{year}-{number}" is one. Defaults to
                `None`, in which case it is "docket_numbers" (or else
                "docket_number").
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks `column` (or both of the defaults).

        Returns:
            The table of dockets, labeled by "case_docket".

        """
        if column is None:
            column = next(
                (c for c in ('docket_numbers', 'docket_number')
                 if c in data.columns), 'docket_numbers')
        cases.require_columns(data, [column], repr(self.name))
        cases.require_columns(
            data.reset_index(), ['case_id'], repr(self.name),
            hint = 'The cases must be labeled by "case_id"')
        numbers = data[column].map(_docket_numbers)
        dropped = [
            c for c in ('docket_numbers', *_DOCKET_COLUMNS) if c in data]
        table = data.drop(columns = dropped).assign(docket = numbers)
        table.index = table.index.rename('case_id')
        dockets = amos.shapers.ListsToRows().shape(
            table, column = 'docket', position = '__place__')
        places = dockets['__place__'].fillna(1).astype(int).astype(str)
        dockets.insert(
            0, 'case_docket', dockets['case_id'].astype(str) + '-' + places)
        order = ['case_docket', 'case_id', 'docket']
        dockets = dockets.drop(columns = '__place__')
        dockets = dockets[[
            *order, *[c for c in dockets.columns if c not in order]]]
        return dockets.set_index('case_docket')


@dataclasses.dataclass
class DocketsToCases(Converter, amos.Shaper):
    """Makes a table of dockets a table of cases again.

    It undoes `cases_to_dockets`: the rows of each case become one row,
    labeled by "case_id", and the docket numbers of its rows become its
    "docket_numbers" again (with "; " between them). Every other column
    keeps the value of the case's first docket, so a column that was added
    to the dockets (such as the Integrated Database's, from `add_idb`) has
    the first docket's value.

    Like every shaper, it takes "label", "task", and "groups". Without
    "groups", the groups are those of the dockets other than "case_id".

    """

    output: ClassVar[type[datasets.CourtData]] = datasets.Cases

    def apply(
        self,
        item: amos.Dataset,
        *,
        groups: Sequence[str] | str | None = None,
        **kwargs: Any) -> amos.Dataset:
        """Makes the table of dockets of `item` a table of cases.

        Args:
            item: the dataset of dockets.
            groups: names of the groups of the cases. Defaults to `None`, in
                which case they are the groups of `item` other than
                "case_id" and the dockets' columns.
            **kwargs: "label", "task", and parameters for `shape`.

        Returns:
            The dataset of cases.

        """
        if groups is None:
            groups = [
                group for group in item.groups
                if group not in ('case_id', *_DOCKET_COLUMNS)]
        return super().apply(item, groups = groups, **kwargs)

    def shape(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each case.

        Args:
            data: the table of dockets (see `CasesToDockets`).
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks "case_id".

        Returns:
            The table of cases, labeled by "case_id".

        """
        cases.require_columns(data, ['case_id'], repr(self.name))
        table = data.drop(
            columns = [c for c in _DOCKET_COLUMNS if c in data.columns])
        table = table.drop_duplicates(subset = 'case_id').set_index('case_id')
        if 'docket' in data.columns:
            joined = data.groupby('case_id', sort = False)['docket'].agg(
                _join_dockets)
            table['docket_numbers'] = joined.reindex(table.index).astype(
                object)
        return table


@dataclasses.dataclass
class CasesToCourts(Converter, amos.Shaper):
    """Makes a table with one row for each court.

    Each court's row has "cases" (the number of its cases), "judges" (the
    number of different judges on its panels, if `code_panels` found them),
    and the mean of each column of numbers and booleans of its cases: the
    share of its cases of each case type ("type_criminal", ...), with a party
    of each party type ("party_type_corporation", ...), and with each
    outcome ("outcome_reversal", ...), and the mean composition of its
    panels ("panel_party", ...). See the module's documentation.

    Like every shaper, it takes "label", "task", and "groups". Without
    "groups", the table has none.

    """

    output: ClassVar[type[datasets.CourtData]] = datasets.Courts

    def apply(
        self,
        item: amos.Dataset,
        *,
        groups: Sequence[str] | str | None = None,
        **kwargs: Any) -> amos.Dataset:
        """Makes the table of `item` a table of courts.

        Args:
            item: the dataset of cases.
            groups: names of the groups of the courts. Defaults to `None`,
                for none.
            **kwargs: "label", "task", and parameters for `shape`.

        Returns:
            The dataset of courts.

        """
        return super().apply(
            item, groups = [] if groups is None else groups, **kwargs)

    def shape(
        self,
        data: pd.DataFrame,
        court: str = 'court_num',
        by: Sequence[str] | str | None = None,
        how: Mapping[str, Any] | None = None,
        keep: Sequence[str] | str | None = None,
        **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each court.

        Args:
            data: the cases.
            court: the column that names each case's court. Defaults to
                "court_num".
            by: other columns to group the cases by, such as "year".
                Defaults to `None`.
            how: summaries of columns that take the place of the means, or
                that add columns of text, as `group_rows` takes them (such
                as {"court": "first"}). Defaults to `None`.
            keep: columns of text to keep, with the first value of each
                court's cases (such as "court", CourtListener's id).
                Defaults to `None`.
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks `court` or a column that is named.

        Returns:
            The table of courts, labeled by `court` (and `by`).

        """
        keys = [court, *utilities.listify(by)]
        cases.require_columns(data, keys, repr(self.name))
        data = add_party_type_flags(data)
        nids = [c for c in data.columns if re.fullmatch(r'judge_nid\d+', c)]
        table = summarize(
            data, keys, how = how, keep = keep, count = 'cases')
        if nids:
            stacked = data[keys].join(data[nids]).melt(
                id_vars = keys, value_name = 'nid').dropna(subset = ['nid'])
            judges = stacked.groupby(keys, dropna = False)['nid'].nunique()
            table['judges'] = judges.reindex(table.index).fillna(0).astype(
                'int64')
        return table


@dataclasses.dataclass
class CasesToCaseTypes(Converter, amos.Shaper):
    """Makes a table with one row for each case type.

    The case types are the "type_..." columns that `code_case_type` adds
    (such as "type_criminal", "type_civil", "type_tort", and
    "type_contract"). The `wide_to_long` technique of `amos` makes a row for
    each type of each case, and the rows of each type are summarized: each
    type's row has "cases" (the number of its cases) and the mean of each
    column of numbers and booleans of its cases (see the module's
    documentation). A case of several types (such as a tort case that is
    also a contract case) counts for each of them.

    Like every shaper, it takes "label", "task", and "groups". Without
    "groups", the table has none.

    """

    output: ClassVar[type[datasets.CourtData]] = datasets.CaseTypes

    def apply(
        self,
        item: amos.Dataset,
        *,
        groups: Sequence[str] | str | None = None,
        **kwargs: Any) -> amos.Dataset:
        """Makes the table of `item` a table of case types.

        Args:
            item: the dataset of cases.
            groups: names of the groups of the case types. Defaults to
                `None`, for none.
            **kwargs: "label", "task", and parameters for `shape`.

        Returns:
            The dataset of case types.

        """
        return super().apply(
            item, groups = [] if groups is None else groups, **kwargs)

    def shape(
        self,
        data: pd.DataFrame,
        by: Sequence[str] | str | None = None,
        how: Mapping[str, Any] | None = None,
        keep: Sequence[str] | str | None = None,
        **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each case type.

        Args:
            data: the cases, with the "type_..." columns of `code_case_type`.
            by: other columns to group the cases by, such as "court_num".
                Defaults to `None`.
            how: summaries of columns that take the place of the means, as
                `group_rows` takes them. Defaults to `None`.
            keep: columns of text to keep, with the first value of each
                type's cases. Defaults to `None`.
            **kwargs: not used.

        Raises:
            KeyError: if `data` has no "type_..." columns, or lacks a column
                that is named.

        Returns:
            The table of case types, labeled by "case_type" (and `by`).

        """
        extra = utilities.listify(by)
        cases.require_columns(data, extra, repr(self.name))
        types = [c for c in data.columns if str(c).startswith('type_')]
        if not types:
            message = (
                f'{self.name!r} needs the "type_..." columns of each case '
                f'type: apply "code_case_type" first')
            raise KeyError(message)
        flags = pd.DataFrame(
            {c: cases.column_as_flags(data, c) for c in types})
        data = add_party_type_flags(data.drop(columns = types)).join(flags)
        long = amos.shapers.WideToLong().shape(
            data, stubs = 'type', name = 'case_type')
        long = long[long['type'].astype(bool)].drop(columns = 'type')
        return summarize(
            long, ['case_type', *extra], how = how, keep = keep,
            count = 'cases')


@dataclasses.dataclass
class CasesToPartyTypes(Converter, amos.Shaper):
    """Makes a table with one row for each party type.

    Each party's type is in "party1_type" and "party2_type" (such as
    "individual", "corporation", or "agency"). The `wide_to_long` technique
    of `amos` makes a row for each party of each case, and the rows of each
    type are summarized. Each type's row has "parties" (how many parties
    were of the type), "party_won" (the share of them that won, from
    "outcome_party1_won" and "outcome_party2_won", if `code_outcome` made
    them), the mean of each column of numbers and booleans that both sides
    have (such as "party1_appealing" and "party2_appealing", which become
    "party_appealing"), and the mean of each other column of numbers and
    booleans of their cases (see the module's documentation).

    Like every shaper, it takes "label", "task", and "groups". Without
    "groups", the table has none.

    """

    output: ClassVar[type[datasets.CourtData]] = datasets.PartyTypes

    def apply(
        self,
        item: amos.Dataset,
        *,
        groups: Sequence[str] | str | None = None,
        **kwargs: Any) -> amos.Dataset:
        """Makes the table of `item` a table of party types.

        Args:
            item: the dataset of cases.
            groups: names of the groups of the party types. Defaults to
                `None`, for none.
            **kwargs: "label", "task", and parameters for `shape`.

        Returns:
            The dataset of party types.

        """
        return super().apply(
            item, groups = [] if groups is None else groups, **kwargs)

    def shape(
        self,
        data: pd.DataFrame,
        by: Sequence[str] | str | None = None,
        how: Mapping[str, Any] | None = None,
        keep: Sequence[str] | str | None = None,
        **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each party type.

        Args:
            data: the cases, with "party1_type" and "party2_type".
            by: other columns to group the parties by, such as "court_num".
                Defaults to `None`.
            how: summaries of columns that take the place of the means, as
                `group_rows` takes them. Defaults to `None`.
            keep: columns of text to keep, with the first value of each
                type's parties. Defaults to `None`.
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks "party1_type", "party2_type", or a
                column that is named.

        Returns:
            The table of party types, labeled by "party_type" (and `by`).

        """
        extra = utilities.listify(by)
        typed = [f'{side}_type' for side in _SIDES]
        cases.require_columns(
            data, [*typed, *extra], repr(self.name),
            hint = 'Each party needs a type, which rules can find')
        sided = {
            str(column).removeprefix('party1_') for column in data.columns
            if str(column).startswith('party1_')
            and f'party2_{str(column).removeprefix("party1_")}' in data.columns
            and (column in typed or _is_number(data[column], column))}
        renamed = {
            f'{side}_{name}': f'party_{name}__{number}'
            for number, side in enumerate(_SIDES, start = 1)
            for name in sided}
        for number, side in enumerate(_SIDES, start = 1):
            won = f'outcome_{side}_won'
            if won in data.columns:
                renamed[won] = f'party_won__{number}'
        stubs = sorted({name.rpartition('__')[0] for name in renamed.values()})
        data = data.rename(columns = renamed)
        long = amos.shapers.WideToLong().shape(
            data, stubs = stubs, name = _SIDE, separator = '__')
        long = long[long[_PARTY_TYPE].notna()].drop(columns = _SIDE)
        return summarize(
            long, [_PARTY_TYPE, *extra], how = how, keep = keep,
            count = 'parties')


""" Public Functions """


def add_party_type_flags(data: pd.DataFrame) -> pd.DataFrame:
    """Adds whether a party of each type is in each case.

    Args:
        data: the cases. Without "party1_type" and "party2_type", nothing is
            added.

    Returns:
        `data`, with a column "party_type_{type}" for each type that either
            party has, which is true if either party of the case has it.

    """
    typed = [f'{side}_type' for side in _SIDES if f'{side}_type' in data]
    if not typed:
        return data
    kinds = pd.unique(data[typed].melt()['value'].dropna().astype(str))
    flags = {
        f'{_PARTY_TYPE}_{"_".join(kind.lower().split())}': (
            data[typed].astype('string').eq(kind).any(axis = 1))
        for kind in sorted(kinds)}
    added = pd.DataFrame(flags, index = data.index)
    return pd.concat(
        [data.drop(columns = [c for c in added if c in data]), added],
        axis = 1)


def summarize(
    data: pd.DataFrame,
    by: Sequence[str],
    *,
    how: Mapping[str, Any] | None = None,
    keep: Sequence[str] | str | None = None,
    count: str | None = None) -> pd.DataFrame:
    """Returns a table with one row for each group of rows.

    The `group_rows` technique of `amos` summarizes the groups. Only the
    columns of numbers and booleans are summarized (by their means), except
    columns that identify something (such as "case_id", "judge_nid", or
    "court_num", unless they are in `by`), so nothing about any one row
    (such as a case's docket number or date) is kept.

    Args:
        data: the table.
        by: the columns that say which group each row belongs to.
        how: summaries of columns that take the place of the means, or that
            add columns, by their names (such as {"court": "first"}).
            Defaults to `None`.
        keep: columns of text to keep, with the first value of each group.
            Defaults to `None`.
        count: name of a column to make with the number of rows of each
            group. Defaults to `None`, for none.

    Raises:
        KeyError: if a column of `by`, `how`, or `keep` is not in `data`.

    Returns:
        The table, labeled by `by`.

    """
    keys = list(by)
    summaries = {
        column: 'mean' for column in data.columns
        if column not in keys and _is_number(data[column], column)}
    summaries.update(dict.fromkeys(utilities.listify(keep), 'first'))
    summaries.update(how or {})
    cases.require_columns(data, [*keys, *summaries], 'summarize')
    table = amos.shapers.GroupRows().shape(
        data[[*keys, *summaries]].reset_index(drop = True),
        by = keys, how = summaries, count = count)
    return table.set_index(keys)


""" Private Functions """


def _docket_numbers(value: Any) -> list[str]:
    """Returns the docket numbers in a cell of a table of cases.

    Args:
        value: a list of docket numbers, text with any number of them (such
            as "17-1234; 17-1235" or "Nos. 17-1234, 17-1235"), or a missing
            value.

    Returns:
        The docket numbers, in order and without repeats.

    """
    if isinstance(value, list | tuple | np.ndarray):
        found = [str(v).strip() for v in value if str(v).strip()]
    elif isinstance(value, str):
        found = _DOCKET.findall(value)
    else:
        found = []
    return list(dict.fromkeys(found))


def _join_dockets(found: pd.Series) -> str | None:
    """Returns the docket numbers of a case's dockets, as one cell of text.

    Args:
        found: the docket number of each of the case's dockets.

    Returns:
        The docket numbers that are not missing, with "; " between them, or
            `None` if there are none.

    """
    numbers = [str(number) for number in found if pd.notna(number)]
    return cases._SEPARATOR.join(numbers) or None


def _is_number(values: pd.Series, column: Any) -> bool:
    """Returns whether a column is numbers or booleans that can be averaged.

    Args:
        values: the column.
        column: the name of the column.

    Returns:
        Whether it is numbers or booleans and does not identify something
            (see `_ID`).

    """
    return (
        (pd.api.types.is_numeric_dtype(values.dtype)
         or pd.api.types.is_bool_dtype(values.dtype))
        and not _ID.search(str(column)))
