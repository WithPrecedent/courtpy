"""Adds what a roster says about the judge that each row names.

Contents:
    MergeBiographies: adds what a roster says about the judge that each row
        names.

"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Sequence
from typing import Any

import amos
import numpy as np
import pandas as pd

from ...core import cases, utilities
from ._roster import _ROSTER_FILE, Roster, _folder, _whole


@dataclasses.dataclass
class MergeBiographies(amos.Merger):
    """Adds what a roster says about the judge that each row names.

    Each row of the data names one judge, as an opinion writes the name
    (such as "LYNCH"). The name is matched to a judge in a roster (see
    `Roster`) with the court and year of the row's case, and the columns of
    the judge's row of the roster are added, with a prefix before their
    names. So a table with a row for each judge on each case gets
    "judge_party", "judge_woman", and so on. A table of cases gets what is
    known about the author of each opinion with "name" set to "author" and
    "prefix" to "author_". A row whose name is not matched gets missing
    values.

    Like every merger of `amos`, it takes these parameters, never adds,
    removes, or reorders rows, and records how many rows it matched in the
    dataset's history:

    | Parameter | Meaning |
    | --- | --- |
    | `source` | The roster: the path of a saved one (looked for in the current folder and then in the clerk's input folder), a roster, or the table of one. Without it, the roster saved in "judges" in `utilities.data_folder()` is used. |
    | `columns` | The columns to add. By default, they are the roster's attributes (see `Roster.attributes`) and those that depend on the case: "age", "senior", "designated", and "district_judge" (see `Roster.describe`). All of them are added as numbers (1 and 0 for true and false). Any other column of the roster can be named too, such as "judge" (the judge's name, as the roster reports it), "nid", or "president". |
    | `prefix` | Text to put before the names of the added columns. It is "judge_" unless another is set. |
    | `indicator` | The name of a column to make that says whether each row's judge was found. |
    | `name`, `court`, `year` | The columns of the data with the judge's name and the number of the court and the year of the row's case. They are "judge", "court_num", and "year" unless others are set. |

    """

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        source: Any = None,
        columns: Sequence[str] | str | None = None,
        prefix: str | None = 'judge_',
        indicator: str | None = None,
        name: str = 'judge',
        court: str = 'court_num',
        year: str = 'year',
        **kwargs: Any) -> amos.Dataset:
        """Adds the columns of the judge that each row of `item` names.

        Args:
            item: the dataset to add columns to.
            source: the roster: a roster, the table of one, or the path of a
                saved one. Defaults to `None`, in which case the roster saved
                in "judges" in `utilities.data_folder()` is used.
            columns: the columns to add: attributes of the judge (see
                `Roster.described`) or other columns of the roster. Defaults
                to `None`, in which case they are every attribute.
            prefix: text to put before the names of the added columns.
                Defaults to "judge_".
            indicator: name of a boolean column to make that says whether
                each row's judge was found. Defaults to `None`, which makes
                no such column.
            name: the column of `item` with the judge's name, as an opinion
                writes it. Defaults to "judge".
            court: the column of `item` with the number of the court of the
                row's case. Defaults to "court_num".
            year: the column of `item` with the year of the row's case.
                Defaults to "year".
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
        if source is None:
            source = _folder() / _ROSTER_FILE
        roster = (
            Roster.create(utilities.locate(source, self.clerk))
            if isinstance(source, str | pathlib.Path)
            else Roster.create(source))
        data = item.data
        rows = np.asarray(
            self.match(data, roster, name = name, court = court, year = year),
            dtype = 'int64')
        chosen = (
            roster.described if columns is None
            else utilities.listify(columns))
        missing = [
            c for c in chosen
            if c not in roster.described and c not in roster.data.columns]
        if missing:
            message = f'the columns {missing} are not in the roster of judges'
            raise KeyError(message)
        described = pd.DataFrame(columns = roster.described, dtype = 'float64')
        if any(column in roster.described for column in chosen):
            blank: dict[str, float | None] = dict.fromkeys(roster.described)
            cases_of = zip(
                rows.tolist(), data[court].tolist(), data[year].tolist(),
                strict = True)
            described = pd.DataFrame.from_records(
                [roster.describe(row, _whole(number), _whole(when))
                 if row >= 0 else blank for row, number, when in cases_of],
                columns = roster.described).astype('float64')
        # A row of -1 is no row of the roster, so its values are missing.
        listed = roster.data.reindex(rows)
        added = pd.DataFrame({
            f'{prefix or ""}{column}': (
                described[column] if column in roster.described
                else listed[column]).to_numpy()
            for column in chosen}, index = data.index)
        if indicator is not None:
            added[indicator] = rows >= 0
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
                str(source) if isinstance(source, str | pathlib.Path)
                else type(source).__name__),
            rows = len(data),
            matched = int((rows >= 0).sum()),
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
