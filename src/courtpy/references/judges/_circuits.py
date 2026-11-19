"""Adds the makeup of the whole circuit of each case on the day it was decided.

Contents:
    AddCircuit: adds the ideology of the active judges of each case's
        circuit when the case was decided.
    _COURT_OF_APPEALS: the Federal Judicial Center's name for the type of a
        court of appeals.
    _SCORES: the columns of a roster that `AddCircuit` summarizes, by the
        word that names them in the added columns.

"""

from __future__ import annotations

import dataclasses
import warnings
from collections.abc import Sequence
from typing import Any

import amos
import numpy as np
import pandas as pd

from ...core import cases, utilities
from .. import courts
from ._biographies import find_roster
from ._roster import Roster

_COURT_OF_APPEALS: str = 'U.S. Court of Appeals'
_SCORES: dict[str, str] = {'party': 'party', 'jcs': 'jcs'}


@dataclasses.dataclass
class AddCircuit(amos.Merger):
    """Adds the ideology of the active judges of each case's circuit.

    For a case of a court of appeals, the circuit is the court's own; for a
    case of a district court, it is the circuit of the court of appeals that
    hears its appeals (see `courtpy.courts.circuits`). The judges of the
    circuit are those of its court of appeals in a roster (see `Roster`) who
    were active on the day the case was decided: they had been appointed,
    had not left the court, and had not taken senior status (senior judges
    do not sit on the court en banc). Their scores are summarized:

    | Column | Meaning |
    | --- | --- |
    | `circuit_median_party` | The median party of the presidents who appointed them (-1 for Democratic and 1 for Republican). |
    | `circuit_total_party` | The sum of those parties, which is how many more were appointed by Republicans than by Democrats. |
    | `circuit_median_jcs` | The median of their Judicial Common Space scores (higher is more conservative). |
    | `circuit_total_jcs` | The sum of their scores. |
    | `circuit_judges` | How many judges were active. |

    The scores of the Judicial Common Space are added if the roster has them
    (make it with `Roster.from_fjc(jcs = True)`). A judge without a score is
    left out of its summaries. A case whose circuit or date is not known (or
    whose circuit had no active judge in the roster) gets missing values.

    Like every merger of `amos`, it never adds, removes, or reorders rows,
    and records how many rows it matched in the dataset's history. It takes
    these parameters:

    | Parameter | Meaning |
    | --- | --- |
    | `source` | The roster: the path of a saved one, a roster, or the table of one. Without it, the roster saved in "judges" in `utilities.data_folder()` is used. |
    | `columns` | The scores to summarize: "party", "jcs", or both (the default, if the roster has "jcs"). |
    | `date` | The column with the date each case was decided. It is "date_filed" unless another is set. |
    | `court_num`, `court` | The columns with courtpy's number for each case's court and CourtListener's id for it. They are "court_num" and "court" unless others are set. |
    | `prefix` | Text to put before the names of the added columns. It is "circuit_" unless another is set. |

    """

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        source: Any = None,
        columns: Sequence[str] | str | None = None,
        date: str = 'date_filed',
        court_num: str = 'court_num',
        court: str = 'court',
        prefix: str | None = 'circuit_',
        **kwargs: Any) -> amos.Dataset:
        """Adds the ideology of the active judges of each case's circuit.

        Args:
            item: the dataset of cases (or of votes).
            source: the roster: a roster, the table of one, or the path of a
                saved one. Defaults to `None`, in which case the roster saved
                in "judges" in `utilities.data_folder()` is used.
            columns: the scores to summarize: "party", "jcs", or both.
                Defaults to `None`, for both if the roster has "jcs", and
                otherwise "party" (with a warning).
            date: the column of `item` with the date each case was decided.
                Defaults to "date_filed".
            court_num: the column of `item` with courtpy's number for each
                case's court. Defaults to "court_num".
            court: the column of `item` with CourtListener's id for each
                case's court. Defaults to "court".
            prefix: text to put before the names of the added columns.
                Defaults to "circuit_".
            **kwargs: not used.

        Raises:
            KeyError: if `item` lacks `date`, or one of `columns` is not a
                score or not in the roster.
            ValueError: if an added column would have the name of a column of
                the data.

        Returns:
            The dataset with the added columns.

        """
        prefix = prefix or ''
        data = item.data
        cases.require_columns(data, [date], repr(self.name))
        roster = find_roster(source, self.clerk)
        chosen = self._choose(roster, columns)
        circuit = courts.circuits(data, court_num = court_num, court = court)
        when = pd.to_datetime(data[date], errors = 'coerce').to_numpy(
            dtype = 'datetime64[D]')
        judges = _active_judges(roster)
        added = {
            f'{prefix}{kind}_{_SCORES[score]}': np.full(len(data), np.nan)
            for score in chosen for kind in ('median', 'total')}
        counts = np.zeros(len(data), dtype = 'int64')
        known = circuit.notna().to_numpy() & ~np.isnat(when)
        numbers = circuit.to_numpy(dtype = 'float64', na_value = np.nan)
        for number in np.unique(numbers[known]):
            rows = np.flatnonzero(known & (numbers == number))
            serving = judges[judges['court_num'] == number]
            if serving.empty:
                continue
            days, place = np.unique(when[rows], return_inverse = True)
            active = _is_active(serving, days)
            counts[rows] = active.sum(axis = 1)[place]
            for score in chosen:
                values = serving[score].to_numpy(dtype = 'float64')
                medians, totals = _summaries(active, values)
                added[f'{prefix}median_{_SCORES[score]}'][rows] = medians[place]
                added[f'{prefix}total_{_SCORES[score]}'][rows] = totals[place]
        table = pd.DataFrame(added, index = data.index)
        table[f'{prefix}judges'] = pd.array(counts, dtype = 'Int64')
        table.loc[~known, f'{prefix}judges'] = pd.NA
        clashes = [c for c in table.columns if c in data.columns]
        if clashes:
            message = (
                f'{self.name!r} would add columns named {clashes}, which the '
                f'data already has: set "prefix" to tell them apart')
            raise ValueError(message)
        item.replace(pd.concat([data, table], axis = 1))
        item.record(
            self.name,
            rows = len(data),
            matched = int((counts > 0).sum()),
            created = list(table.columns))
        return item

    def match(
        self,
        data: pd.DataFrame,
        other: pd.DataFrame,  # noqa: ARG002
        **kwargs: Any) -> Any:
        """Returns no row of a roster for any case.

        The active judges of a circuit are many rows of a roster, which
        `apply` summarizes, rather than one row that each case matches.

        Args:
            data: the cases.
            other: the table of a roster.
            **kwargs: not used.

        Returns:
            -1 for each case.

        """
        return np.full(len(data), -1, dtype = 'int64')

    """ Private Methods """

    def _choose(
        self,
        roster: Roster,
        columns: Sequence[str] | str | None) -> list[str]:
        """Returns the scores to summarize.

        Args:
            roster: the roster.
            columns: the scores that are named, or `None`.

        Raises:
            KeyError: if one of `columns` is not a score or not in the
                roster.

        Returns:
            The scores.

        """
        if columns is None:
            if 'jcs' in roster.data.columns:
                return ['party', 'jcs']
            warnings.warn(
                f'{self.name!r} adds no Judicial Common Space scores, because '
                f'the roster has none: make it with '
                f'Roster.from_fjc(jcs = True)',
                category = amos.AmosWarning,
                stacklevel = 3)
            return ['party']
        chosen = utilities.listify(columns)
        unknown = [c for c in chosen if c not in _SCORES]
        if unknown:
            message = f'{self.name!r} summarizes {list(_SCORES)}, not {unknown}'
            raise KeyError(message)
        cases.require_columns(
            roster.data, chosen, 'the roster for ' + repr(self.name),
            hint = 'Make the roster with Roster.from_fjc(jcs = True)')
        return chosen


""" Private Functions """


def _active_judges(roster: Roster) -> pd.DataFrame:
    """Returns the service of each judge of a court of appeals, as dates.

    A roster that has no dates (only years) has its service begin on the
    first day of its first year, and end (or turn senior) on the last day of
    its last year.

    Args:
        roster: the roster.

    Returns:
        A table with a row for each judge's service on a court of appeals,
            with "court_num", "start", "end", and "senior" (as days, missing
            if the service has not ended or the judge has not taken senior
            status), and the roster's "party" and "jcs" (if it has them).

    """
    table = roster.data
    if 'court_type' in table.columns:
        table = table[table['court_type'] == _COURT_OF_APPEALS]
    table = table[table['court_num'].notna()]
    service = pd.DataFrame({
        'court_num': table['court_num'].astype('float64').to_numpy()})
    for name, fallback in (
            ('start', '-01-01'), ('end', '-12-31'), ('senior', '-12-31')):
        if f'{name}_date' in table.columns:
            dates = pd.to_datetime(table[f'{name}_date'], errors = 'coerce')
        else:
            years = (
                pd.to_numeric(table[f'{name}_year'], errors = 'coerce')
                if f'{name}_year' in table.columns
                else pd.Series(np.nan, index = table.index))
            dates = pd.to_datetime(
                years.astype('Int64').astype('string') + fallback,
                errors = 'coerce')
        service[name] = dates.to_numpy(dtype = 'datetime64[D]')
    for score in _SCORES:
        if score in table.columns:
            service[score] = pd.to_numeric(
                table[score], errors = 'coerce').to_numpy()
    return service


def _is_active(serving: pd.DataFrame, days: np.ndarray) -> np.ndarray:
    """Returns which judges were active on each day.

    Args:
        serving: the service of the judges of one court (see
            `_active_judges`).
        days: the days.

    Returns:
        A table of booleans with a row for each day and a column for each
            judge: whether the judge had begun to serve, had not stopped,
            and had not taken senior status.

    """
    day = days[:, None]
    start = serving['start'].to_numpy(dtype = 'datetime64[D]')[None, :]
    end = serving['end'].to_numpy(dtype = 'datetime64[D]')[None, :]
    senior = serving['senior'].to_numpy(dtype = 'datetime64[D]')[None, :]
    begun: np.ndarray = ~np.isnat(start) & (start <= day)
    serving_still = np.isnat(end) | (day < end)
    not_senior = np.isnat(senior) | (day < senior)
    active: np.ndarray = begun & serving_still & not_senior
    return active


def _summaries(
    active: np.ndarray,
    values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Returns the median and sum of the values of the active judges.

    Args:
        active: which judges were active on each day (see `_is_active`).
        values: each judge's score, missing if the judge has none.

    Returns:
        The median and the sum of the scores of the judges who were active
            on each day, missing on a day when none of them has a score.

    """
    chosen = np.where(active, values[None, :], np.nan)
    scored = (~np.isnan(chosen)).sum(axis = 1) > 0
    medians = np.full(len(active), np.nan)
    totals = np.full(len(active), np.nan)
    if scored.any():
        medians[scored] = np.nanmedian(chosen[scored], axis = 1)
        totals[scored] = np.nansum(chosen[scored], axis = 1)
    return medians, totals
