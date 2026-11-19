"""The courts of each jurisdiction, and the circuit of each federal case.

The table of a jurisdiction's courts is "courts.csv" in its folder of
"instructions" (such as "instructions/federal/courts.csv"), which can be
opened in a spreadsheet, with one row for each court:

| Column | Meaning |
| --- | --- |
| `court_num` | courtpy's number for the court: 1 to 13 for the courts of appeals (12 for the D.C. Circuit and 13 for the Federal Circuit), as the rules that make "court_num" for cases number them, 99 for the Supreme Court, 101 and up for specialized and historical courts (such as the bankruptcy appellate panels), and 1001 and up for the district courts. |
| `court` | A name for the court that can be a folder's name (such as "southern_district_of_new_york", or "scotus" for the Supreme Court). |
| `feature_name` | The court's name as a label for tables and plots (such as "Southern District of New York"). |
| `level` | "high", "appellate", "trial", or "specialty", which state courts will share. |
| `circuit_num` | The number of the court of appeals that hears its appeals (for a district court, that of its state, as fjc-biographies numbers them). |
| `courtlistener_name` | CourtListener's id for the court (such as "nysd"), if it has one. |
| `fjc_name` | A regular expression for the Federal Judicial Center's names for the court, matched ignoring case. Several names are separated by a vertical bar. |
| `opinion_name` | A regular expression for how an opinion names the court (its name, or its abbreviation in a citation, such as "S.D.N.Y.", "S. D. N.Y.", or "S.D. New York"), matched ignoring case. The header rules of a source whose cases name their court in text (such as Lexis-Nexis) find "court_num" and "court_name" with it, and then with `fjc_name`, and every source's header rules find the trial or specialized court whose decision is reviewed in the history the same way ("lower_court_num" and "lower_court_name"; see `courtpy.rules.make_court_rules`). |

The header rules have no names of courts of their own, so a court added to
the table is found in cases without changing any rules. CourtListener cases
find "court_num" and "court_name" by CourtListener's id for the court
instead (see `court_numbers_by_courtlistener_name` and
`court_names_by_courtlistener_name`), and "lower_court_num" and
"lower_court_name" by the id of the court appealed from, if the docket has
it.

`circuits` finds the circuit of each case in a table of cases, which
`add_circuit` uses.

Contents:
    circuits: returns the number of the circuit of each case.
    court_labels: returns the label of each case's court for tables and
        plots, in the order of the table of courts.
    court_names_by_courtlistener_name: returns courtpy's name for each
        court, by CourtListener's id for it.
    court_numbers_by_courtlistener_name: returns courtpy's number for each
        court, by CourtListener's id for it.
    court_table: returns the table of a jurisdiction's courts.
    federal_courts: returns the table of the federal courts.
    _COURTS_FILE_NAME: the name of the file of each jurisdiction's courts.

"""

from __future__ import annotations

import functools
import types
from collections.abc import Mapping
from typing import Any

import pandas as pd

from ..core import utilities

_COURTS_FILE_NAME = 'courts.csv'


""" Public Functions """


def circuits(
    data: pd.DataFrame,
    *,
    court_num: str = 'court_num',
    court: str = 'court') -> pd.Series:
    """Returns the number of the circuit of each case.

    A case of a court of appeals is in its own circuit ("court_num" from 1 to
    13). Any other case is in the circuit that `federal_courts` gives its
    court, which is found by CourtListener's id for the court (the "court"
    column of CourtListener cases, such as "nysd") or else by courtpy's
    number for it.

    Args:
        data: the cases.
        court_num: the column with courtpy's number for each case's court.
            Defaults to "court_num".
        court: the column with CourtListener's id for each case's court.
            Defaults to "court".

    Returns:
        The number of each case's circuit, as whole numbers, missing for a
            case whose court is not known or (like the Supreme Court) is in
            no circuit.

    """
    table = federal_courts()
    found = pd.Series(pd.NA, index = data.index, dtype = 'Int64')
    if court in data.columns:
        by_id = table.dropna(subset = ['courtlistener_name']).set_index(
            'courtlistener_name')['circuit_num']
        found = found.fillna(
            data[court].astype('string').str.lower().map(by_id)
            .astype('Int64'))
    if court_num in data.columns:
        numbers = pd.to_numeric(data[court_num], errors = 'coerce')
        by_number = table.drop_duplicates('court_num').set_index(
            'court_num')['circuit_num']
        found = found.fillna(numbers.map(by_number).astype('Int64'))
    return found


def court_labels(
    data: pd.DataFrame,
    *,
    court_name: str = 'court_name',
    court_num: str = 'court_num',
    jurisdiction: str = 'federal') -> pd.Series:
    """Returns the label of each case's court for tables and plots.

    A court's label is its "feature_name" in the table of courts (such as
    "Southern District of New York"), found by courtpy's name for the court
    (such as "southern_district_of_new_york") or else by its number. A
    number that several courts share (as 9 is the Ninth Circuit's and the
    old Circuit Court for the Districts of California's) labels the court
    that CourtListener has.

    Args:
        data: the cases.
        court_name: the column with courtpy's name for each case's court.
            Defaults to "court_name".
        court_num: the column with courtpy's number for each case's court.
            Defaults to "court_num".
        jurisdiction: the folder of the jurisdiction's instructions, such as
            "federal". Defaults to "federal".

    Raises:
        KeyError: if `data` has neither column.
        FileNotFoundError: if the jurisdiction has no table of courts.

    Returns:
        The labels, as an ordered category whose categories are the courts
            that the cases have, in the order of the table of courts (so the
            courts of appeals come first, by number). A case whose court is
            not known has a missing label.

    """
    if court_name not in data.columns and court_num not in data.columns:
        message = (
            f'the cases have neither {court_name!r} nor {court_num!r}, so '
            f'their courts cannot be labeled')
        raise KeyError(message)
    table = court_table(jurisdiction)
    labels = pd.Series(pd.NA, index = data.index, dtype = object)
    if court_name in data.columns:
        by_name = dict(zip(table['court'], table['feature_name'], strict = True))
        labels = data[court_name].map(by_name)
    if court_num in data.columns:
        # The courts that CourtListener has come first, so that a shared
        # number labels the court that cases come from.
        modern = table.sort_values(
            'courtlistener_name', key = lambda found: found.isna(),
            kind = 'stable').drop_duplicates('court_num')
        by_number = dict(zip(
            modern['court_num'], modern['feature_name'], strict = True))
        numbers = pd.to_numeric(data[court_num], errors = 'coerce')
        labels = labels.fillna(numbers.map(by_number))
    present = set(labels.dropna())
    order = [c for c in dict.fromkeys(table['feature_name']) if c in present]
    return pd.Series(
        pd.Categorical(labels, categories = order, ordered = True),
        index = data.index, name = 'court')


def court_names_by_courtlistener_name(
    jurisdiction: str = 'federal') -> Mapping[str, str]:
    """Returns courtpy's name for each court, by CourtListener's id for it.

    Args:
        jurisdiction: the folder of the jurisdiction's instructions, such as
            "federal". Defaults to "federal".

    Raises:
        FileNotFoundError: if the jurisdiction has no table of courts.

    Returns:
        The "court" of each court that has a "courtlistener_name" (such as
            "first_circuit" for "ca1"), by that id in lower case. It is read
            only, and made once for each jurisdiction, since it is used for
            every case.

    """
    return _index_courtlistener_courts(jurisdiction, 'court')


def court_numbers_by_courtlistener_name(
    jurisdiction: str = 'federal') -> Mapping[str, int]:
    """Returns courtpy's number for each court, by CourtListener's id for it.

    Args:
        jurisdiction: the folder of the jurisdiction's instructions, such as
            "federal". Defaults to "federal".

    Raises:
        FileNotFoundError: if the jurisdiction has no table of courts.

    Returns:
        The "court_num" of each court that has a "courtlistener_name" (such
            as 1 for "ca1"), by that id in lower case. It is read only, and
            made once for each jurisdiction, since it is used for every
            case.

    """
    return _index_courtlistener_courts(jurisdiction, 'court_num')


def court_table(jurisdiction: str = 'federal') -> pd.DataFrame:
    """Returns the table of a jurisdiction's courts.

    Args:
        jurisdiction: the folder of the jurisdiction's instructions, such as
            "federal". Defaults to "federal".

    Raises:
        FileNotFoundError: if the jurisdiction has no table of courts.

    Returns:
        A copy of the jurisdiction's "courts.csv" (see the module's
            documentation), with "court_num" and "circuit_num" as whole
            numbers (missing for a court in no circuit).

    """
    return _read_courts(jurisdiction).copy()


def federal_courts() -> pd.DataFrame:
    """Returns the table of the federal courts.

    Returns:
        A copy of the table of the federal courts (see `court_table`).

    """
    return court_table('federal')


""" Private Functions """


@functools.cache
def _index_courtlistener_courts(
    jurisdiction: str,
    column: str) -> Mapping[str, Any]:
    """Maps CourtListener's id for each court to a column of its row, once.

    Args:
        jurisdiction: the folder of the jurisdiction's instructions.
        column: the column of the table of courts, such as "court_num".

    Raises:
        FileNotFoundError: if the jurisdiction has no table of courts.

    Returns:
        The value of `column` for each court that has an id (as a Python
            `int` or `str`), by the id in lower case, as a read-only
            mapping.

    """
    table = _read_courts(jurisdiction).dropna(subset = ['courtlistener_name'])
    values = table[column].tolist()
    return types.MappingProxyType(dict(zip(
        table['courtlistener_name'].str.lower(), values, strict = True)))


@functools.cache
def _read_courts(jurisdiction: str) -> pd.DataFrame:
    """Reads the table of a jurisdiction's courts once.

    Args:
        jurisdiction: the folder of the jurisdiction's instructions.

    Raises:
        FileNotFoundError: if the jurisdiction has no table of courts.

    Returns:
        The table in the jurisdiction's `_COURTS_FILE_NAME`.

    """
    path = utilities.instructions_folder() / jurisdiction / _COURTS_FILE_NAME
    if not path.is_file():
        message = f'there is no table of courts for {jurisdiction!r}: {path}'
        raise FileNotFoundError(message)
    table = utilities.read_csv(
        path, dtype = {'courtlistener_name': 'string'},
        keep_default_na = False, na_values = [''])
    return table.astype({'court_num': 'int64', 'circuit_num': 'Int64'})
