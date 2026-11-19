"""The federal courts, and the circuit of each.

The table of the federal courts is "instructions/federal/courts.csv", which
can be opened in a spreadsheet, with one row for each court:

| Column | Meaning |
| --- | --- |
| `court_num` | courtpy's number for the court: 1 to 13 for the courts of appeals (12 for the D.C. Circuit and 13 for the Federal Circuit), as the rules that make "court_num" for cases number them, 99 for the Supreme Court, 101 to 104 for specialized and historical courts, and 1001 and up for the district courts. |
| `court` | A name for the court that can be a folder's name (such as "southern_district_of_new_york"). |
| `level` | "supreme", "appellate", "district", or "specialty". |
| `circuit_num` | The number of the court of appeals that hears its appeals (for a district court, that of its state, as fjc-biographies numbers them). |
| `courtlistener` | CourtListener's id for the court (such as "nysd"), if it has one. |
| `fjc_name` | A regular expression for the Federal Judicial Center's names for the court, matched ignoring case. Several names are separated by a vertical bar. |
| `opinion_name` | A regular expression for how an opinion names the court (its name, or its abbreviation in a citation, such as "S.D.N.Y."), matched ignoring case. |

`circuits` finds the circuit of each case in a table of cases, which
`add_circuit` uses.

Contents:
    circuits: returns the number of the circuit of each case.
    federal_courts: returns the table of the federal courts.
    _COURTS_FILE: the file of the table of the federal courts.

"""

from __future__ import annotations

import functools

import pandas as pd

from ..core import utilities

_COURTS_FILE = utilities.instructions_folder() / 'federal' / 'courts.csv'


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
        by_id = table.dropna(subset = ['courtlistener']).set_index(
            'courtlistener')['circuit_num']
        found = found.fillna(
            data[court].astype('string').str.lower().map(by_id)
            .astype('Int64'))
    if court_num in data.columns:
        numbers = pd.to_numeric(data[court_num], errors = 'coerce')
        by_number = table.drop_duplicates('court_num').set_index(
            'court_num')['circuit_num']
        found = found.fillna(numbers.map(by_number).astype('Int64'))
    return found


def federal_courts() -> pd.DataFrame:
    """Returns the table of the federal courts.

    Returns:
        A copy of the table in `_COURTS_FILE` (see the module's
            documentation), with "court_num" and "circuit_num" as whole
            numbers (missing for a court in no circuit).

    """
    return _read_courts().copy()


""" Private Functions """


@functools.cache
def _read_courts() -> pd.DataFrame:
    """Reads the table of the federal courts once.

    Returns:
        The table in `_COURTS_FILE`.

    """
    table = utilities.read_csv(
        _COURTS_FILE, dtype = {'courtlistener': 'string'},
        keep_default_na = False, na_values = [''])
    return table.astype({'court_num': 'int64', 'circuit_num': 'Int64'})
