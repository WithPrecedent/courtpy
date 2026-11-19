"""Court cases and tables of them.

Contents:
    Case: the text and information of one case, ready to be parsed.
    column_as_flags: returns a column of a table of cases as plain booleans.
    flags_as_numbers: returns a column of flags as numbers, keeping missing
        values.
    require_columns: raises an error if a table lacks columns.
    select_whole_cases: returns which rows a query selects, keeping each
        case whole.
    split_cell: returns the values in a cell of a table of cases, as a list.
    tidy: gives columns with missing values the right type.
    _SEPARATOR: the text between several values in one cell.
    _TRUE: text that `column_as_flags` reads as true.
    _WHOLE_NUMBERS: columns that hold whole numbers.

"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

_SEPARATOR: str = '; '
_TRUE: frozenset[str] = frozenset({'true', 't', '1', 'yes'})
_WHOLE_NUMBERS: frozenset[str] = frozenset({
    'year', 'court_num', 'cluster_id', 'docket_id', 'author_id',
    'citation_count'})


@dataclasses.dataclass
class Case:
    """The text and information of one case, ready to be parsed.

    Readers (such as `courtlistener.read_case` and `lexis.read_case`) make
    cases from files, and a `Parser` turns each case into a row of a table.

    Args:
        id: a unique name for the case, which becomes the row's label in the
            table (such as the CourtListener cluster id or the file name).
        source: where the case came from: "court_listener" or "lexis_nexis".
        sections: sections of text that rules search, by name (such as
            "party", "disposition", and "opinion"). Defaults to an empty
            `dict`.
        metadata: information that needs no parsing (such as the date filed
            from CourtListener), by the name of its column. These values are
            used instead of anything rules find with the same names. Defaults
            to an empty `dict`.
        path: the file the case came from. Defaults to `None`.

    """

    id: str
    source: str
    sections: dict[str, str] = dataclasses.field(default_factory = dict)
    metadata: dict[str, Any] = dataclasses.field(default_factory = dict)
    path: pathlib.Path | None = None


def tidy(data: pd.DataFrame) -> pd.DataFrame:
    """Gives columns of booleans or whole numbers with missing values a type.

    `pandas` stores a column of booleans with missing values (such as
    "published", which is unknown for some cases) as plain objects, and a
    column of whole numbers with missing values (such as "year") as decimals.
    Such columns become the "boolean" and "Int64" types, which allow missing
    values.

    Args:
        data: a table of cases.

    Returns:
        The table, with those columns changed.

    """
    for column in data.columns:
        values = data[column].dropna()
        if len(values) == 0:
            continue
        if data[column].dtype == object and values.map(
            lambda v: isinstance(v, bool)).all():
            data[column] = data[column].astype('boolean')
        elif (
            column in _WHOLE_NUMBERS
            and pd.api.types.is_float_dtype(data[column].dtype)
            and (values == values.round()).all()):
            data[column] = data[column].astype('Int64')
    return data


""" Helpers for Tables of Cases """


def column_as_flags(data: pd.DataFrame, column: str) -> pd.Series:
    """Returns a column of a table of cases as plain booleans.

    Flags combined with `&` and `|` need plain booleans without missing
    values. A missing value (or a missing column) is false. Text (as in a
    table loaded from a CSV file) is true if it is "true", "t", "1", or "yes"
    (in any case).

    Args:
        data: the cases.
        column: name of the column.

    Returns:
        The column as plain booleans, or a column of false values if `data`
            has no such column.

    """
    if column not in data.columns:
        return pd.Series(False, index = data.index)
    values = data[column]
    # pandas reads text as the "str" type, or as `object` when it is mixed
    # with other values.
    if values.dtype == object or pd.api.types.is_string_dtype(values.dtype):
        values = values.map(
            lambda v: str(v).strip().lower() in _TRUE
            if isinstance(v, str) else bool(v) if pd.notna(v) else False)
    return values.astype('boolean').fillna(False).astype(bool)


def flags_as_numbers(column: pd.Series) -> pd.Series:
    """Returns a column of flags as numbers, keeping missing values.

    Args:
        column: flags, which may be missing.

    Returns:
        1.0 for true, 0.0 for false, and NaN for missing values, as plain
            floats (so that means and models can use them).

    """
    return pd.Series(
        column.astype('boolean').astype('Float64').to_numpy(
            dtype = 'float64', na_value = np.nan),
        index = column.index)


def require_columns(
    data: pd.DataFrame,
    columns: Iterable[str],
    name: str,
    *,
    hint: str | None = None) -> None:
    """Raises an error if a table lacks columns.

    Args:
        data: the table.
        columns: names of the columns that are needed.
        name: what needs them (such as "a table of votes" or a technique's
            name), for the message.
        hint: a sentence added to the message, such as how to make the
            columns. Defaults to `None`.

    Raises:
        KeyError: if a column is missing. The message names the missing
            columns and `name`.

    """
    missing = [c for c in columns if c not in data.columns]
    if missing:
        message = f'{name} needs the columns {missing}, which are missing'
        if hint:
            message = f'{message}. {hint}'
        raise KeyError(message)


def select_whole_cases(
    data: pd.DataFrame,
    query: str | None,
    *,
    case_column: str = 'case_id') -> pd.Series:
    """Returns which rows a query selects, keeping each case whole.

    A table with several rows for each case (such as a row for each judge's
    vote) is selected a case at a time, so that a case is never split.

    Args:
        data: the table.
        query: an expression that `pandas.DataFrame.eval` reads (such as
            "year >= 2010 and not dissenting"), or `None`.
        case_column: the column with each row's case. Defaults to "case_id".

    Raises:
        KeyError: if `data` has no `case_column`.
        ValueError: if the query does not say whether each row is selected
            (such as "year + 1", which makes a number for each row).

    Returns:
        Whether each row is selected: every row without a query, and the
            rows of a case only if the query selects every one of them.

    """
    if not query:
        return pd.Series(True, index = data.index)
    require_columns(data, [case_column], 'select_whole_cases')
    message = (
        f'the query {query!r} must say whether each row is selected (true '
        f'or false), as "year >= 2010" does')
    found = data.eval(query)
    if not isinstance(found, pd.Series) or len(found) != len(data):
        raise ValueError(message)
    try:
        selected = column_as_flags(
            pd.DataFrame({'selected': found}, index = data.index),
            'selected')
    except (TypeError, ValueError) as error:
        raise ValueError(message) from error
    whole: pd.Series = selected.groupby(data[case_column]).transform('all')
    return whole


def split_cell(value: Any, separator: str = _SEPARATOR) -> list[Any]:
    """Returns the values in a cell of a table of cases, as a list.

    Rules that find several values (such as "panel_judges" or "agencies")
    join them with "; " so that the table can be saved as a CSV file.

    Args:
        value: a cell: text with `separator` between its values, a list (or
            tuple or array) of values, or a missing value.
        separator: the text between the values. Defaults to "; ".

    Returns:
        The values, with text trimmed of spaces and without blank values. A
            missing value or blank text has none.

    """
    if isinstance(value, list | tuple | np.ndarray):
        return [v for v in value if not isinstance(v, str) or v.strip()]
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return []
    pieces = (p.strip() for p in str(value).split(separator))
    return [p for p in pieces if p]
