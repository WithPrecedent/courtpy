"""Shared tools.

Contents:
    config_folder: returns the folder for courtpy's settings and secrets.
    data_folder: returns the folder for large downloads, such as bulk data.
    expand_courts: turns court ids and group names into court ids.
    instructions_folder: returns courtpy's "instructions" folder.
    is_none_setting: returns whether a setting names nothing, such as "none"
        or "false".
    listify: returns a setting as a list of names.
    locate: returns a file named in settings, found as a clerk finds files.
    normalize: collapses all whitespace in text into single spaces.
    open_session: returns a session that identifies courtpy to servers.
    parse_date: returns an ISO date (YYYY-MM-DD) from a date in text.
    read_csv: loads a CSV file that is in UTF-8 or Windows-1252.
    to_bool: converts a setting or a CSV cell to a boolean.
    to_date: converts a date setting to YYYY-MM-DD text.
    to_integer: converts a whole-number setting to an `int`.
    _ISO_DATE: pattern for a date written as YYYY-MM-DD, with the year, month,
        and day as its groups.
    _MONTHS: the number of each month, by the first three letters of its name
        in capitals.
    _NONE: text of a setting that turns something off.
    _WRITTEN_DATE: pattern for a date written out, such as "January 5, 2010",
        "Jan. 5, 2010", or "Sept. 5 2010", with the month, day, and year as
        its groups.

"""

from __future__ import annotations

import datetime
import importlib.resources
import os
import pathlib
import re
import sys
from collections.abc import Iterable
from typing import Any

import amos
import pandas as pd
import requests

from . import options

_MONTHS: dict[str, int] = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6, 'JUL': 7,
    'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
# A date such as "January 5, 2010", "Jan. 5, 2010", or "Sept. 5 2010".
_WRITTEN_DATE: re.Pattern[str] = re.compile(
    r'\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.?\s+'
    r'(\d{1,2}),?\s+(\d{4})\b',
    flags = re.IGNORECASE)
_ISO_DATE: re.Pattern[str] = re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b')
# Settings that turn something off.
_NONE: frozenset[str] = frozenset({'', 'none', 'false', 'no', '0'})


def config_folder() -> pathlib.Path:
    """Returns the folder for courtpy's settings and secrets.

    The folder is outside of any project or package, so that a secret (such as
    the CourtListener API key) is never saved in a project's files or shared
    with them. It is the folder named by the `COURTPY_CONFIG_DIR` environment
    variable, if it is set. Otherwise, it is "courtpy" in the user's
    application data folder on Windows ("%APPDATA%"), or in
    "~/.config" (or "$XDG_CONFIG_HOME") on other systems.

    Returns:
        The path of the folder. It is not created.

    """
    named = os.environ.get(options._ENV_CONFIG)
    if named:
        return pathlib.Path(named).expanduser()
    if sys.platform == 'win32':
        base = (
            os.environ.get('APPDATA')
            or pathlib.Path.home() / 'AppData' / 'Roaming')
        return pathlib.Path(base) / 'courtpy'
    base = os.environ.get('XDG_CONFIG_HOME') or pathlib.Path.home() / '.config'
    return pathlib.Path(base) / 'courtpy'


def data_folder() -> pathlib.Path:
    """Returns the folder for large downloads, such as bulk data.

    Bulk data files are very large (the opinions alone are more than 50 GB),
    so they are kept outside of projects, where every project can share
    them. The folder is the one named by the `COURTPY_DATA_DIR` environment
    variable, if it is set. Otherwise, it is `options._DATA_SUBFOLDER`
    ("courts") in the data folder of the `amos` workspace, which is where
    every `amos` project keeps its data (see `amos.clerks.workspace`): with
    projects in "projects/code", it is "projects/data/courts".

    Returns:
        The path of the folder. It is not created.

    """
    named = os.environ.get(options._ENV_DATA)
    if named:
        return pathlib.Path(named).expanduser()
    return (
        amos.clerks.workspace() / amos.options._DATA_FOLDER
        / options._DATA_SUBFOLDER)


def expand_courts(courts: str | Iterable[str] | None) -> list[str]:
    """Turns court ids and names of groups of courts into court ids.

    Args:
        courts: CourtListener court ids (such as "ca1" or "scotus") or names of
            groups in `options._COURT_GROUPS` (such as "federal_appellate"),
            as a list or a comma-separated `str`.

    Raises:
        ValueError: if no courts are named.

    Returns:
        The court ids, in order, without repeats.

    """
    found: list[str] = []
    for name in listify(courts):
        for court in options._COURT_GROUPS.get(name.lower(), (name.lower(),)):
            if court not in found:
                found.append(court)
    if not found:
        message = 'name at least one court (such as "ca1") or group of courts'
        raise ValueError(message)
    return found


def instructions_folder() -> pathlib.Path:
    """Returns courtpy's "instructions" folder.

    The folder has the built-in rulebooks (see `courtpy.rules`).

    Returns:
        The path of the folder, inside the installed package.

    """
    package = pathlib.Path(str(importlib.resources.files('courtpy')))
    return package / 'instructions'


def is_none_setting(value: Any) -> bool:
    """Returns whether a setting names nothing, such as "none" or "false".

    Settings such as "coders = none" turn something off.

    Args:
        value: a setting: `None`, a `bool`, or text.

    Returns:
        Whether `value` is `None`, `False`, or text (in any case, with any
            spaces around it) in `_NONE`.

    """
    if value is None or value is False:
        return True
    return str(value).strip().lower() in _NONE


def listify(item: Any) -> list[str]:
    """Returns a setting as a list of names.

    Args:
        item: `None`, a `str` (which may list names separated by commas), or an
            iterable of names.

    Returns:
        The names, with surrounding spaces removed and blank names dropped.

    """
    if item is None:
        return []
    if isinstance(item, str):
        item = item.split(',')
    elif not isinstance(item, Iterable):
        item = [item]
    return [str(name).strip() for name in item if str(name).strip()]


def locate(path: pathlib.Path | str, clerk: Any = None) -> pathlib.Path:
    """Returns a file named in settings, found as a clerk finds files.

    Args:
        path: a path, which may begin with "~" for the user's home folder.
        clerk: the file manager of a project (a `nagata.FileManager`).
            Defaults to `None`.

    Returns:
        `path` itself if it is absolute, exists in the current folder, or
            there is no `clerk`, and otherwise `path` in the clerk's input
            folder.

    """
    resolved = pathlib.Path(str(path)).expanduser()
    if clerk is None or resolved.is_absolute() or resolved.exists():
        return resolved
    return pathlib.Path(clerk.input_folder) / resolved


def normalize(text: str | None) -> str:
    """Collapses all whitespace in `text` into single spaces.

    Args:
        text: text to normalize. `None` becomes an empty `str`.

    Returns:
        The text on one line, with single spaces between words.

    """
    return ' '.join(text.split()) if text else ''


def open_session(session: Any = None) -> Any:
    """Returns a session that identifies courtpy to servers.

    Args:
        session: an object with a `get` method like a `requests.Session`.
            Defaults to `None`.

    Returns:
        `session`, or a new `requests.Session` with courtpy's user agent if
            it is `None`.

    """
    if session is None:
        session = requests.Session()
        session.headers.update({'User-Agent': options._USER_AGENT})
    return session


def parse_date(text: str | None) -> str | None:
    """Returns the first date in `text` as an ISO date (YYYY-MM-DD).

    Args:
        text: text with a date written out (such as "March 3, 2010" or
            "Mar. 3, 2010") or in ISO format ("2010-03-03").

    Returns:
        The date, or `None` if there is no valid date in `text`.

    """
    if not text:
        return None
    match = _ISO_DATE.search(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
    else:
        match = _WRITTEN_DATE.search(text)
        if match is None:
            return None
        month = _MONTHS[match.group(1).upper()[:3]]
        day, year = int(match.group(2)), int(match.group(3))
    try:
        return datetime.date(year, month, day).isoformat()
    except ValueError:
        return None


def read_csv(path: pathlib.Path | str, **kwargs: Any) -> pd.DataFrame:
    """Loads a CSV file that is in UTF-8 or Windows-1252.

    The files of other researchers' data are not all in UTF-8, and some have
    been in one encoding in one year and another in the next.

    Args:
        path: the path of the file, which may begin with "~" for the user's
            home folder. A zip archive of one CSV file is read as that file.
        **kwargs: arguments for `pandas.read_csv`.

    Returns:
        The table.

    """
    path = pathlib.Path(path).expanduser()
    table: pd.DataFrame
    try:
        table = pd.read_csv(path, encoding = 'utf-8-sig', **kwargs)
    except UnicodeDecodeError:
        table = pd.read_csv(path, encoding = 'cp1252', **kwargs)
    return table


def to_bool(value: Any) -> bool:
    """Converts a setting or a CSV cell to a boolean.

    Args:
        value: a `bool`, a number, or text such as "TRUE", "yes", "1", "t",
            "FALSE", "no", "0", or "f" (in any case). Blank text is `False`.

    Raises:
        ValueError: if `value` is text that is not one of those.

    Returns:
        The boolean value.

    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, int | float):
        return bool(value)
    text = str(value).strip().lower()
    if text in {'true', 't', 'yes', 'y', '1'}:
        return True
    if text in {'false', 'f', 'no', 'n', '0', ''}:
        return False
    message = f'{value!r} is not TRUE or FALSE'
    raise ValueError(message)


def to_date(value: Any) -> str | None:
    """Converts a date setting to YYYY-MM-DD text.

    Args:
        value: the setting: text such as "2019-01-01", or a date or date and
            time (which a settings file may have turned it into).

    Returns:
        The first ten characters of the setting as text (the date), or `None`
            if it is blank.

    """
    if value in (None, ''):
        return None
    return str(value)[:10]


def to_integer(value: Any) -> int | None:
    """Converts a whole-number setting to an `int`.

    Args:
        value: the setting, as a number or as text such as "500".

    Raises:
        ValueError: if the setting is not a whole number.

    Returns:
        The number, or `None` if the setting is blank.

    """
    if value in (None, ''):
        return None
    return int(value)
