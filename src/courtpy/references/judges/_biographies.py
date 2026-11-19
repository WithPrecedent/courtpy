"""Adds what is known about the judges that the rows name.

Contents:
    AddBiography: adds what a roster says about each judge that each row
        names.
    AddJcs: adds the Judicial Common Space score of each judge that each row
        names.
    by_seat: returns columns of each judge of each case, numbered by the
        judge's seat.
    find_roster: returns the roster that a technique's "source" names.
    _IDENTITY: the columns that name the judge in each seat.
    _ROW: column that holds the position of each row's case while a table
        is made.
    _SEAT: column that holds each judge's seat on a panel while a table is
        made.
    _WRITTEN: column that holds each judge's name, as the opinion writes it,
        while a table is made.

"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Callable, Mapping, Sequence
from typing import Any, ClassVar

import amos
import numpy as np
import pandas as pd

from ...core import cases, datasets, utilities
from ._roster import _ROSTER_FILE, Roster, _folder, _whole

# A function that finds what is known about a judge, from the judge's name
# as an opinion writes it, the number of the case's court, and its year.
Lookup = Callable[[str, int | None, int | None], Mapping[str, Any] | None]

_IDENTITY: tuple[str, ...] = ('name', 'nid')
_ROW: str = '__row__'
_SEAT: str = '__seat__'
_WRITTEN: str = '__written__'


@dataclasses.dataclass
class AddBiography(amos.Merger):
    """Adds what a roster says about each judge that each row names.

    A name, as an opinion writes it (such as "LYNCH"), is matched to a judge
    in a roster (see `Roster`) with the court and year of the row's case, and
    the columns of the judge's row of the roster are added, with a prefix
    before their names. A name that is not matched gets missing values.

    In `Votes` (or any table with a row for each judge), each row names one
    judge ("judge"), so it gets "judge_party", "judge_woman", and so on. With
    "name" set to "author" and "prefix" to "author_", a table of cases gets
    what is known about the author of each opinion.

    In `Cases`, each case names several judges ("panel_judges", with "; "
    between the names), so the columns are numbered by each judge's seat
    (the place of the judge's name in the list): "judge_name1" (the judge's
    name, as the roster reports it), "judge_nid1" (the Federal Judicial
    Center's number for the judge), "judge_party1", "judge_woman1", and so on
    for the first judge, "judge_name2" and the rest for the second, for as
    many seats as the longest panel has. A name that is not matched leaves
    its seat missing, so the judges after it keep theirs. "judge_name" and
    "judge_nid" columns that the cases already have (from `code_panels`) are
    left as they are.

    Instead of a roster, "lookup" can be a function that takes a judge's name
    (as the opinion writes it), the number of the case's court, and its year,
    and returns what is known about the judge, by the names of its columns
    (or `None` if nothing is). Then "judge_name1" is the name as the opinion
    writes it.

    Like every merger of `amos`, it takes these parameters, never adds,
    removes, or reorders rows, and records how many rows it matched in the
    dataset's history:

    | Parameter | Meaning |
    | --- | --- |
    | `source` | The roster: the path of a saved one (looked for in the current folder and then in the clerk's input folder), a roster, or the table of one. Without it, the roster saved in "judges" in `utilities.data_folder()` is used. |
    | `columns` | The columns to add. By default, they are the roster's attributes (see `Roster.attributes`) and those that depend on the case: "age", "senior", "designated", and "district_judge" (see `Roster.describe`). All of them are added as numbers (1 and 0 for true and false). Any other column of the roster can be named too, such as "judge" (the judge's name, as the roster reports it), "nid", or "president". |
    | `prefix` | Text to put before the names of the added columns. It is "judge_" unless another is set. |
    | `indicator` | The name of a column to make that says whether each row's judge was found (or, numbered, how many of its judges were). |
    | `name`, `court`, `year` | The columns of the data with the judges' names and the number of the court and the year of the row's case. They are "panel_judges" (for `Cases`) or "judge", "court_num", and "year" unless others are set. |
    | `numbered` | Whether each row names several judges, whose columns are numbered by their seats. Unless it is set, it is true for `Cases` without a "name", and false otherwise. |
    | `lookup` | A function that finds what is known about a judge, used instead of a roster. |

    Attributes:
        default_columns: the columns to add when "columns" is not set, or
            `None` for every attribute of the judges.

    """

    default_columns: ClassVar[tuple[str, ...] | None] = None

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        source: Any = None,
        columns: Sequence[str] | str | None = None,
        prefix: str | None = 'judge_',
        indicator: str | None = None,
        name: str | None = None,
        court: str = 'court_num',
        year: str = 'year',
        numbered: bool | None = None,
        lookup: Lookup | None = None,
        **kwargs: Any) -> amos.Dataset:
        """Adds the columns of each judge that each row of `item` names.

        Args:
            item: the dataset to add columns to.
            source: the roster: a roster, the table of one, or the path of a
                saved one. Defaults to `None`, in which case the roster saved
                in "judges" in `utilities.data_folder()` is used. It is not
                used with `lookup`.
            columns: the columns to add: attributes of the judge (see
                `Roster.described`) or other columns of the roster (or, with
                `lookup`, names that it returns). Defaults to `None`, in
                which case they are every attribute (or, with `lookup`, every
                name that it returns).
            prefix: text to put before the names of the added columns.
                Defaults to "judge_".
            indicator: name of a column to make that says whether each row's
                judge was found, or (numbered) how many of its judges were.
                Defaults to `None`, which makes no such column.
            name: the column of `item` with the judges' names, as an opinion
                writes them. Defaults to `None`, in which case it is
                "panel_judges" if `numbered`, and otherwise "judge".
            court: the column of `item` with the number of the court of the
                row's case. Defaults to "court_num".
            year: the column of `item` with the year of the row's case.
                Defaults to "year".
            numbered: whether each row names several judges, separated by
                "; " (or in a list), whose columns are numbered by their
                seats. Defaults to `None`, in which case it is true if `item`
                is `Cases` and `name` is `None`.
            lookup: a function that takes a judge's name, the number of the
                case's court, and its year, and returns what is known about
                the judge (or `None`). Defaults to `None`, in which case the
                roster is used.
            **kwargs: not used.

        Raises:
            KeyError: if `item` lacks one of the columns `name`, `court`, and
                `year`, or one of `columns` is not in the roster.
            ValueError: if an added column would have the name of a column
                of the data.

        Returns:
            The dataset with the added columns. Its rows and index are not
                changed.

        """
        if numbered is None:
            numbered = isinstance(item, datasets.Cases) and name is None
        if name is None:
            name = 'panel_judges' if numbered else 'judge'
        if columns is None and self.default_columns is not None:
            columns = list(self.default_columns)
        data = item.data
        cases.require_columns(data, [name, court, year], repr(self.name))
        named = _listed(data, name, court, year) if numbered else pd.DataFrame({
            _ROW: np.arange(len(data)),
            _SEAT: 1,
            _WRITTEN: data[name].to_numpy(),
            court: data[court].to_numpy(),
            year: data[year].to_numpy()})
        if lookup is None:
            roster = self._roster(source)
            found, rows = self._from_roster(
                named, roster, columns, court = court, year = year)
            matched = rows >= 0
            identity = pd.DataFrame({
                'name': roster.data['judge'].reindex(rows).to_numpy(),
                'nid': roster.data['nid'].reindex(rows).astype(
                    'Int64').array})
        else:
            found = _from_lookup(named, lookup, columns, court, year)
            matched = found.notna().any(axis = 1).to_numpy()
            identity = pd.DataFrame({
                'name': named[_WRITTEN].where(matched).to_numpy()})
        start = prefix or ''
        if numbered:
            identity = identity[[
                key for key in identity.columns
                if f'{start}{key}1' not in data.columns]]
            seated = pd.concat([
                named[[_ROW, _SEAT]].reset_index(drop = True),
                identity.add_prefix(start),
                found.add_prefix(start)], axis = 1)
            added = by_seat(seated, len(data))
            if indicator is not None:
                added[indicator] = pd.Series(matched).groupby(
                    named[_ROW].to_numpy()).sum().reindex(
                        range(len(data)), fill_value = 0).to_numpy()
        else:
            added = found.add_prefix(start)
            if indicator is not None:
                added[indicator] = matched
        added.index = data.index
        clashes = [c for c in added.columns if c in data.columns]
        if clashes:
            message = (
                f'{self.name!r} would add columns named {clashes}, which the '
                f'data already has: set "prefix" to tell them apart, or name '
                f'the columns to add in "columns"'
            )
            raise ValueError(message)
        item.replace(pd.concat([data, added], axis = 1))
        item.record(
            self.name,
            source = (
                'lookup' if lookup is not None
                else str(source) if isinstance(source, str | pathlib.Path)
                else type(source).__name__),
            rows = len(data),
            judges = int(named[_WRITTEN].notna().sum()),
            matched = int(matched.sum()),
            created = list(added.columns))
        return item

    def match(
        self,
        data: pd.DataFrame,
        other: pd.DataFrame | Roster,
        *,
        name: str = 'judge',
        court: str = 'court_num',
        year: str = 'year',
        **kwargs: Any) -> Any:
        """Returns the row of a roster for the judge that each row names.

        Args:
            data: the data, with a row for each judge to find.
            other: a roster, or the table of one.
            name: the column of `data` with the judge's name, as an opinion
                writes it. Defaults to "judge".
            court: the column of `data` with the number of the court of the
                row's case. Defaults to "court_num".
            year: the column of `data` with the year of the row's case.
                Defaults to "year".
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks one of the columns.

        Returns:
            The position of the judge's row in the roster for each row of
                `data` (see `Roster.match`), or -1 if the name is missing or
                is not matched.

        """
        cases.require_columns(data, [name, court, year], repr(self.name))
        roster = Roster.create(other)
        named = zip(
            data[name].tolist(), data[court].tolist(), data[year].tolist(),
            strict = True)
        found = (
            roster.match(written, _whole(number), _whole(when))
            if isinstance(written, str) and written.strip() else None
            for written, number, when in named)
        return np.array(
            [-1 if row is None else row for row in found], dtype = 'int64')

    """ Private Methods """

    def _from_roster(
        self,
        named: pd.DataFrame,
        roster: Roster,
        columns: Sequence[str] | str | None,
        *,
        court: str,
        year: str) -> tuple[pd.DataFrame, np.ndarray]:
        """Returns what the roster says about each named judge.

        Args:
            named: a table with a row for each name, with `_WRITTEN`, `court`,
                and `year`.
            roster: the roster.
            columns: the columns to add, or `None` for every attribute.
            court: the column of `named` with the number of the case's court.
            year: the column of `named` with the year of the case.

        Raises:
            KeyError: if one of `columns` is not in the roster.

        Returns:
            A table with a row for each row of `named` and a column for each
                of the chosen columns, and the judge's row of the roster for
                each row of `named` (or -1 if the name is not matched).

        """
        rows = np.asarray(
            self.match(
                named, roster, name = _WRITTEN, court = court, year = year),
            dtype = 'int64')
        chosen = (
            roster.described if columns is None
            else utilities.listify(columns))
        missing = [
            c for c in chosen
            if c not in roster.described and c not in roster.data.columns]
        if missing:
            message = (
                f'the columns {missing} are not in the roster of judges'
                + (': make the roster with Roster.from_fjc(jcs = True)'
                   if 'jcs' in missing else ''))
            raise KeyError(message)
        described = pd.DataFrame(columns = roster.described, dtype = 'float64')
        if any(column in roster.described for column in chosen):
            blank: dict[str, float | None] = dict.fromkeys(roster.described)
            cases_of = zip(
                rows.tolist(), named[court].tolist(), named[year].tolist(),
                strict = True)
            described = pd.DataFrame.from_records(
                [roster.describe(row, _whole(number), _whole(when))
                 if row >= 0 else blank for row, number, when in cases_of],
                columns = roster.described).astype('float64')
        # A row of -1 is no row of the roster, so its values are missing.
        listed = roster.data.reindex(rows)
        found = pd.DataFrame({
            column: (
                described[column] if column in roster.described
                else listed[column]).to_numpy()
            for column in chosen})
        return found, rows

    def _roster(self, source: Any) -> Roster:
        """Returns the roster that `source` names.

        Args:
            source: a roster, the table of one, the path of a saved one, or
                `None` for the roster saved in "judges" in
                `utilities.data_folder()`.

        Returns:
            The roster.

        """
        return find_roster(source, self.clerk)


@dataclasses.dataclass
class AddJcs(AddBiography):
    """Adds the Judicial Common Space score of each judge that each row names.

    It is `add_biography` with "jcs" as its only column: the score of each
    judge's appointment on the scale of the Judicial Common Space (higher is
    more conservative), which a roster has if it was made with
    `Roster.from_fjc(jcs = True)` (see `courtpy.jcs`). So `Votes` gets
    "judge_jcs", and `Cases` gets "judge_name1", "judge_nid1", and
    "judge_jcs1" for the first judge, and so on for each seat. It takes the
    parameters of `add_biography`, so "lookup" can be a function that finds
    each judge's score instead (returning {"jcs": score}).

    """

    default_columns: ClassVar[tuple[str, ...] | None] = ('jcs',)


""" Public Functions """


def find_roster(source: Any, clerk: Any = None) -> Roster:
    """Returns the roster that a technique's "source" names.

    Args:
        source: a roster, the table of one, the path of a saved one (looked
            for in the current folder and then in the clerk's input folder),
            or `None` for the roster saved in "judges" in
            `utilities.data_folder()`.
        clerk: the file manager of the technique. Defaults to `None`.

    Returns:
        The roster.

    """
    if source is None:
        source = _folder() / _ROSTER_FILE
    return (
        Roster.create(utilities.locate(source, clerk))
        if isinstance(source, str | pathlib.Path)
        else Roster.create(source))


def by_seat(seated: pd.DataFrame, size: int) -> pd.DataFrame:
    """Returns columns of each judge of each case, numbered by the judge's seat.

    The `long_to_wide` technique of `amos` makes a column for each seat of
    each column.

    Args:
        seated: a table with a row for each judge on each case, with the
            position of the judge's case (`_ROW`), the judge's seat
            (`_SEAT`, 1 for the first), and columns to number.
        size: the number of cases.

    Returns:
        A table with a row for each case, in order, and, for each column of
            `seated` and each seat, the column named for it and the seat
            ("judge_party1", "judge_party2", and so on), for as many seats
            as any case has. A case with fewer judges has missing values in
            the rest. It has no columns if `seated` has no rows.

    """
    values = [c for c in seated.columns if c not in (_ROW, _SEAT)]
    if seated.empty or not values:
        return pd.DataFrame(index = pd.RangeIndex(size))
    seats = int(seated[_SEAT].max())
    renamed = {column: f'{column}__' for column in values}
    wide = amos.shapers.LongToWide().shape(
        seated.rename(columns = renamed), names = _SEAT,
        stubs = list(renamed.values()), ids = _ROW, separator = '')
    wide = wide.set_index(_ROW).reindex(range(size))
    # Each column keeps its type (such as "Int64" for the judges' numbers).
    columns = {
        f'{column}{seat}': wide[f'{column}__{seat}'].astype(
            seated[column].dtype)
        for seat in range(1, seats + 1) for column in values
        if f'{column}__{seat}' in wide.columns}
    return pd.DataFrame(columns).reset_index(drop = True)


""" Private Functions """


def _from_lookup(
    named: pd.DataFrame,
    lookup: Lookup,
    columns: Sequence[str] | str | None,
    court: str,
    year: str) -> pd.DataFrame:
    """Returns what a function says about each named judge.

    Args:
        named: a table with a row for each name, with `_WRITTEN`, `court`,
            and `year`.
        lookup: the function.
        columns: the columns to add, or `None` for every name that the
            function returns.
        court: the column of `named` with the number of the case's court.
        year: the column of `named` with the year of the case.

    Returns:
        A table with a row for each row of `named` and a column for each of
            the chosen columns, missing where the function says nothing.

    """
    found = [
        dict(lookup(written, _whole(number), _whole(when)) or {})
        if isinstance(written, str) and written.strip() else {}
        for written, number, when in zip(
            named[_WRITTEN].tolist(), named[court].tolist(),
            named[year].tolist(), strict = True)]
    chosen = (
        list(dict.fromkeys(key for record in found for key in record))
        if columns is None else utilities.listify(columns))
    return pd.DataFrame.from_records(found, columns = chosen)


def _listed(
    data: pd.DataFrame,
    name: str,
    court: str,
    year: str) -> pd.DataFrame:
    """Returns a table with a row for each name that each row lists.

    The `lists_to_rows` technique of `amos` makes the rows.

    Args:
        data: the data.
        name: the column with the names, separated by "; " (or in lists).
        court: the column with the number of each row's court.
        year: the column with each row's year.

    Returns:
        A table with the position of each name's row in `data` (`_ROW`), the
            place of the name in its row's list (`_SEAT`), the name
            (`_WRITTEN`), and `court` and `year`. A row with no names has
            one row, whose name is missing.

    """
    names = pd.DataFrame({
        _ROW: np.arange(len(data)),
        _WRITTEN: pd.Series(data[name].tolist(), dtype = object),
        court: pd.Series(data[court].tolist(), dtype = object),
        year: pd.Series(data[year].tolist(), dtype = object)})
    listed = amos.shapers.ListsToRows().shape(
        names, column = _WRITTEN, separator = cases._SEPARATOR.strip())
    listed[_SEAT] = listed.groupby(_ROW).cumcount() + 1
    return listed.reset_index(drop = True)
