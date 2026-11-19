"""Adds behavioral scores of judges and courts, computed from training data.

A study can score each judge or court from the cases of a training set (such
as the share of a judge's votes to reverse, or how often a court sides with
the government) and add the scores to the cases of a test set. These
mergers add such scores from a table that has them, as the `merge_keys`
technique of `amos` adds the columns of another table's row with the same
keys:

| Technique | Adds | Matched by |
| --- | --- | --- |
| `add_judge_scores` | Each column of the table of scores, for each judge: "judge_score_{column}" in `Votes`, and "judge_score_{column}1", "judge_score_{column}2", and so on (by each judge's seat) in `Cases`. | The judge's number ("judge_nid", which `code_panels`, `add_biography`, and `cases_to_votes` add) unless "on" names another column, such as the judge's name. |
| `add_court_scores` | Each column of the table of scores: "court_score_{column}". | The court's number ("court_num") unless "on" names another column. |

The table is a data file (looked for in the current folder and then in the
clerk's input folder) or a table, such as a table of `Judges` or `Courts`
made from the training cases (see `cases_to_judges` and `cases_to_courts`).

Contents:
    AddCourtScores: adds scores of each case's court from a table of them.
    AddJudgeScores: adds scores of each judge of each row from a table of
        them.

"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Sequence
from typing import Any

import amos
import numpy as np
import pandas as pd

from ..core import cases, datasets, utilities


@dataclasses.dataclass
class AddJudgeScores(amos.mergers.MergeKeys):
    """Adds scores of each judge of each row from a table of them.

    Each row of the table of scores is a judge, with the judge's number
    ("judge_nid" or "nid") or another key (such as the judge's name) and
    columns of scores. In `Votes` (or any table with a row for each judge),
    each row gets the scores of its judge, as "judge_score_{column}". In
    `Cases`, each case gets the scores of each judge on its panel, numbered
    by the judge's seat: "judge_score_{column}1" for the judge in
    "judge_nid1", and so on (so `code_panels` or `add_biography` must come
    first). A judge who is not in the table gets missing values.

    It takes the parameters of the `merge_keys` technique of `amos`:
    "source" (the table of scores), "columns" (the scores to add, which are
    every column but the key by default), "prefix" ("judge_score_" unless
    another is set), "on" (the column of the data with each judge's key,
    "judge_nid" unless another is set: in `Cases`, the columns are that name
    followed by each seat's number), "other_on" (the key of the table of
    scores, which is "judge_nid" or else "nid" if the table has one, and
    otherwise the same as "on"), and "duplicates". "numbered" says whether
    each row has several judges, whose columns are numbered; it is true for
    `Cases` unless it is set.

    """

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        source: Any = None,
        columns: Sequence[str] | str | None = None,
        prefix: str | None = 'judge_score_',
        on: str = 'judge_nid',
        other_on: str | None = None,
        numbered: bool | None = None,
        duplicates: str = 'error',
        **kwargs: Any) -> amos.Dataset:
        """Adds the scores of each judge of each row of `item`.

        Args:
            item: the dataset of votes or of cases.
            source: the table of scores, or the path of a data file of one.
            columns: the scores to add. Defaults to `None`, for every column
                of the table but its key.
            prefix: text to put before the names of the added columns.
                Defaults to "judge_score_".
            on: the column of `item` with each judge's key, or (numbered) the
                start of the names of the columns of each seat's key.
                Defaults to "judge_nid".
            other_on: the column of the table with each judge's key.
                Defaults to `None`, for "judge_nid" or "nid" if the table has
                one, and otherwise `on`.
            numbered: whether each row has several judges, whose columns are
                numbered by their seats. Defaults to `None`, in which case it
                is true if `item` is `Cases`.
            duplicates: what to do if the table has several rows for a judge
                (see `amos.mergers.MergeKeys.match`). Defaults to "error".
            **kwargs: other parameters of `merge_keys`, such as "reader" and
                "indicator".

        Raises:
            KeyError: if `item` lacks the judges' keys, or the table lacks
                its key or one of `columns`.
            ValueError: if there is no `source`, or an added column would
                have the name of a column of the data.

        Returns:
            The dataset with the added columns.

        """
        if numbered is None:
            numbered = isinstance(item, datasets.Cases)
        if not numbered:
            other = _unlabeled(self.read(source)) if source is not None else (
                None)
            return super().apply(
                item,
                source = other if other is not None else source,
                columns = None if columns is None else utilities.listify(
                    columns),
                prefix = prefix,
                on = on,
                other_on = other_on or _key_of(other, on),
                duplicates = duplicates,
                **kwargs)
        if source is None:
            message = (
                f'{self.name!r} has nothing to merge: set its "source" in the '
                f'"{self.name}_parameters" section of the settings')
            raise ValueError(message)
        other = _unlabeled(
            self.read(source, **dict(kwargs.pop('reader', None) or {})))
        key = other_on or _key_of(other, on)
        data = item.data
        pattern = re.compile(rf'{re.escape(on)}(\d+)')
        seats = sorted(
            int(numbered_column.group(1)) for column in data.columns
            if (numbered_column := pattern.fullmatch(str(column))))
        if not seats:
            message = (
                f'{self.name!r} needs the columns "{on}1", "{on}2", and so on, '
                f'with the key of the judge in each seat: apply "code_panels" '
                f'or "add_biography" first')
            raise KeyError(message)
        chosen = (
            [c for c in other.columns if c != key] if columns is None
            else utilities.listify(columns))
        cases.require_columns(
            other, [key, *chosen], 'the table of ' + repr(self.name))
        added: dict[str, Any] = {}
        matched = 0
        for seat in seats:
            positions = np.asarray(self.match(
                data, other, on = f'{on}{seat}', other_on = key,
                duplicates = duplicates), dtype = 'int64')
            matched += int((positions >= 0).sum())
            found = other[chosen].reset_index(drop = True).reindex(positions)
            for column in chosen:
                added[f'{prefix or ""}{column}{seat}'] = found[
                    column].to_numpy()
        table = pd.DataFrame(added, index = data.index)
        clashes = [c for c in table.columns if c in data.columns]
        if clashes:
            message = (
                f'{self.name!r} would add columns named {clashes}, which the '
                f'data already has: set "prefix" to tell them apart')
            raise ValueError(message)
        item.replace(pd.concat([data, table], axis = 1))
        item.record(
            self.name,
            source = (
                type(source).__name__ if isinstance(source, pd.DataFrame)
                else str(source)),
            rows = len(data),
            matched = matched,
            created = list(table.columns))
        return item


@dataclasses.dataclass
class AddCourtScores(amos.mergers.MergeKeys):
    """Adds scores of each case's court from a table of them.

    Each row of the table of scores is a court, with its number
    ("court_num", unless "other_on" names another column) and columns of
    scores, and each case gets the scores of its court as
    "court_score_{column}". A court that is not in the table gets missing
    values. It takes the parameters of the `merge_keys` technique of `amos`:
    "source", "columns", "prefix" ("court_score_" unless another is set),
    "on" (the column of the cases with each court, "court_num" unless
    another is set), "other_on", and "duplicates".

    """

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        source: Any = None,
        columns: Sequence[str] | str | None = None,
        prefix: str | None = 'court_score_',
        on: str = 'court_num',
        **kwargs: Any) -> amos.Dataset:
        """Adds the scores of each case's court.

        Args:
            item: the dataset of cases (or of votes).
            source: the table of scores, or the path of a data file of one.
            columns: the scores to add. Defaults to `None`, for every column
                of the table but its key.
            prefix: text to put before the names of the added columns.
                Defaults to "court_score_".
            on: the column of `item` with each case's court. Defaults to
                "court_num".
            **kwargs: other parameters of `merge_keys`, such as "other_on",
                "indicator", and "duplicates".

        Raises:
            KeyError: if `item` or the table lacks its key, or the table
                lacks one of `columns`.
            ValueError: if there is no `source`, or an added column would
                have the name of a column of the data.

        Returns:
            The dataset with the added columns.

        """
        other = _unlabeled(self.read(source)) if source is not None else None
        return super().apply(
            item,
            source = other if other is not None else source,
            columns = None if columns is None else utilities.listify(columns),
            prefix = prefix,
            on = on,
            **kwargs)


""" Private Functions """


def _key_of(other: pd.DataFrame | None, on: str) -> str:
    """Returns the column of a table of judges' scores with each judge's key.

    Args:
        other: the table of scores, or `None`.
        on: the key of the data.

    Returns:
        `on` if the table has it (or there is no table), and otherwise
            "judge_nid" or "nid", whichever the table has, or `on`.

    """
    if other is None or on in other.columns:
        return on
    for name in ('judge_nid', 'nid'):
        if name in other.columns:
            return name
    return on


def _unlabeled(other: pd.DataFrame) -> pd.DataFrame:
    """Returns a table with the names of its labels as a column.

    A table of `Judges` or `Courts` is labeled by its key ("judge_nid" or
    "court_num"), which the merger matches as a column.

    Args:
        other: the table of scores.

    Returns:
        `other`, with its labels as a column if they have a name that is not
            a column already.

    """
    name = other.index.name
    if name is not None and name not in other.columns:
        return other.reset_index()
    return other
