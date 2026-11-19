"""Adds the Supreme Court Database's coding to cases of the Supreme Court.

The Supreme Court Database (https://scdb.la.psu.edu) codes every case that
the Supreme Court has decided since its 1946 term: the issue, the direction
of the decision, what the court did with the decision below, which party won,
and how each justice voted, among much else. Its online codebook explains
each variable.

`download` gets the latest release from https://scdb.la.psu.edu/data/ and
keeps it outside of projects (in "scdb" in `courtpy.utilities.data_folder()`).
`cases` returns its table with a row for each case, and `votes` its table
with a row for each justice in each case. Both keep the database's names for
their columns (such as "issueArea" and "decisionDirection"), so the codebook
applies to them as it is.

`merge_scdb` (an `amos.Merger`, which is added to the `amos` library as soon
as courtpy is imported) adds the database's columns to parsed cases of the
Supreme Court, with "scdb_" before their names. A case is matched by the
database's id for it, which CourtListener records ("scdb_id"), or else by
one of its citations:

```python
import courtpy

cases = courtpy.parse("data/court_listener")
dataset = courtpy.code(cases, "merge_scdb", parameters = {
    "merge_scdb": {"columns": "issueArea, decisionDirection, partyWinning"}})
```

`load_scdb` and `download_scdb` (reference loaders, see
`courtpy.loaders.ReferenceLoader`) start a study of the database itself,
such as of how the justices vote ("kind" set to "votes").

Contents:
    DownloadScdb: downloads the Supreme Court Database and loads its cases
        or votes.
    LoadScdb: loads the Supreme Court Database's table of cases or of votes.
    MergeScdb: adds the Supreme Court Database's columns to each case.
    cases: returns the database's table with a row for each case.
    download: downloads the latest release of the database.
    votes: returns the database's table with a row for each justice in each
        case.
    _CITATIONS: the columns of the database with the citations of a case, in
        the order in which they are tried.
    _SEPARATORS: pattern for the text between the citations of a case in a
        table of parsed cases.
    _SYMBOLS: pattern for everything in a citation other than letters and
        digits, which `_cite` removes.

"""

from __future__ import annotations

import dataclasses
import pathlib
import re
from collections.abc import Sequence
from typing import Any

import amos
import numpy as np
import pandas as pd

from ..core import options, utilities
from ..wrangler import loaders

_CITATIONS: tuple[str, ...] = ('usCite', 'sctCite', 'ledCite', 'lexisCite')
_SEPARATORS: re.Pattern[str] = re.compile(r'[;\n]')
_SYMBOLS: re.Pattern[str] = re.compile(r'[^A-Z0-9]')


@dataclasses.dataclass
class MergeScdb(amos.Merger):
    """Adds the Supreme Court Database's columns to each case.

    Each case is matched to the database's row for it: the row with the
    case's id in the database ("scdb_id", which CourtListener records for
    cases of the Supreme Court), or else the row with one of the case's
    citations (such as "347 U.S. 483"). Rather than guess, a case whose
    citations are those of more than one row of the database (as short
    orders on one page of a reporter are) is not matched. A case that is not
    matched, such as a case of another court, gets missing values.

    Like every merger of `amos`, it takes these parameters, never adds,
    removes, or reorders rows, and records how many cases it matched in the
    dataset's history:

    | Parameter | Meaning |
    | --- | --- |
    | `source` | The database's table of cases: the path of its file (looked for in the current folder and then in the clerk's input folder), or a table. Without it, the latest release is used, which is downloaded unless it was before (see `download`). |
    | `columns` | The columns of the database to add, by its names for them (such as "issueArea"). By default, they are all of them. |
    | `prefix` | Text to put before the names of the added columns. It is "scdb_" unless another is set. |
    | `indicator` | The name of a column to make that says whether each case was found in the database. |
    | `on`, `other_on` | The columns of the cases and of the database with the database's id of each case. They are "scdb_id" and "caseId" unless others are set. |
    | `citations` | The column of the cases with their citations. It is "citation" unless another is set. |

    Needs "scdb_id" or "citation" (or the columns named by "on" and
    "citations").

    """

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        source: Any = None,
        columns: Sequence[str] | str | None = None,
        prefix: str | None = 'scdb_',
        **kwargs: Any) -> amos.Dataset:
        """Adds the database's columns for each case of `item`.

        Args:
            item: the dataset of parsed cases.
            source: the database's table of cases, or the path of its file.
                Defaults to `None`, in which case the latest release is
                used, which is downloaded unless it was before.
            columns: the columns of the database to add, as a list or as
                text with commas between their names. Defaults to `None`,
                for all of them.
            prefix: text to put before the names of the added columns.
                Defaults to "scdb_".
            **kwargs: other parameters of the mergers of `amos` (such as
                "indicator"), and those of `match`.

        Raises:
            KeyError: if the cases have neither the column of ids nor the
                column of citations, or one of "columns" is not in the
                database.
            ValueError: if an added column would have the name of a column
                of the cases.

        Returns:
            The dataset, with the new columns.

        """
        if source is None:
            source = download(kinds = 'cases')['cases']
        return super().apply(
            item,
            source = source,
            columns = None if columns is None else utilities.listify(columns),
            prefix = prefix,
            **kwargs)

    def match(
        self,
        data: pd.DataFrame,
        other: pd.DataFrame,
        *,
        on: str = 'scdb_id',
        other_on: str = 'caseId',
        citations: str = 'citation',
        **kwargs: Any) -> Any:
        """Returns the row of the database for each case.

        Args:
            data: the parsed cases.
            other: the database's table of cases.
            on: the column of `data` with the database's id of each case.
                Defaults to "scdb_id".
            other_on: the column of `other` with its id of each case.
                Defaults to "caseId".
            citations: the column of `data` with the citations of each case:
                lists of them, or text with semicolons or line breaks
                between them. Defaults to "citation".
            **kwargs: not used.

        Raises:
            KeyError: if `data` has neither `on` nor `citations`, or `other`
                lacks `other_on`.

        Returns:
            The position of the matching row of `other` for each row of
                `data`, or -1 if there is none.

        """
        if on not in data.columns and citations not in data.columns:
            message = (
                f'{self.name!r} needs the column {on!r} (the Supreme Court '
                f"Database's id of each case, which CourtListener records "
                f'for cases of the Supreme Court) or {citations!r} (the '
                f'citations of each case), and the cases have neither'
            )
            raise KeyError(message)
        if other_on not in other.columns:
            message = f'the columns {[other_on]} are not in the other table'
            raise KeyError(message)
        positions = np.full(len(data), -1, dtype = 'int64')
        if on in data.columns:
            # The first row with an id is used, since the database's other
            # files have a row for each docket or issue of a case.
            ids = other[other_on].astype(str).str.strip()
            first = pd.Series(np.arange(len(other)), index = ids)
            first = first[~first.index.duplicated()]
            wanted = data[on].astype('object').map(
                lambda value: str(value).strip() if pd.notna(value) else '')
            positions = wanted.map(first).fillna(-1).to_numpy(dtype = 'int64')
        if citations in data.columns and (positions < 0).any():
            rows = _cited(other)
            listed = data[citations].tolist()
            for place in np.flatnonzero(positions < 0):
                cell = listed[place]
                if isinstance(cell, str):
                    cell = _SEPARATORS.split(cell)
                elif not isinstance(cell, list | tuple):
                    continue
                found = {
                    rows[cite] for cite in map(_cite, cell) if cite in rows}
                # Citations of more than one case, or of rows that several
                # cases share, do not say which case this is.
                if len(found) == 1 and -1 not in found:
                    positions[place] = found.pop()
        return positions

    def read(self, source: Any, **kwargs: Any) -> pd.DataFrame:
        """Returns the database's table of cases.

        Args:
            source: the path of the database's file (a CSV file, or a zip
                archive of one, as it is downloaded), or a table.
            **kwargs: parameters for loading any other kind of source (see
                `amos.Merger.read`).

        Returns:
            The table.

        """
        if isinstance(source, str | pathlib.Path):
            return cases(utilities.locate(source, self.clerk))
        return super().read(source, **kwargs)


@dataclasses.dataclass
class LoadScdb(loaders.ReferenceLoader):
    """Loads the Supreme Court Database's table of cases or of votes.

    The table starts a study of the database itself, such as of how the
    justices vote ("kind" set to "votes"). Its "source" is the path of one
    of the database's files. Without one, the latest release that was
    downloaded is used, which is downloaded first if there is none (see
    `download`). To add the database's columns to parsed cases, use
    `merge_scdb` instead.

    """

    """ Public Methods """

    def load(
        self,
        source: Any,
        *,
        kind: str = 'cases',
        **kwargs: Any) -> pd.DataFrame:
        """Returns the database's table.

        Args:
            source: the path of the database's file of the kind (a CSV file
                or the zip archive of one), or "current" for the latest
                release that was downloaded.
            kind: "cases" (a row for each case) or "votes" (a row for each
                justice in each case). Defaults to "cases".
            **kwargs: not used.

        Returns:
            The table (see `cases` and `votes`).

        """
        return _read(self._locate(source), _kind(kind))


@dataclasses.dataclass
class DownloadScdb(loaders.ReferenceLoader):
    """Downloads the Supreme Court Database and loads its cases or votes.

    The file is downloaded (see `download`) unless the folder has one
    already, or "refresh" is true, which looks for a newer release. Its
    "source" is the folder to keep the files in, which is "scdb" in
    `courtpy.utilities.data_folder()` unless another is set.

    """

    """ Public Methods """

    def load(
        self,
        source: Any,
        *,
        kind: str = 'cases',
        refresh: bool | str = False,
        session: Any = None,
        **kwargs: Any) -> pd.DataFrame:
        """Downloads the database's file of a kind and returns its table.

        Args:
            source: the folder to keep the files in, or "current" for "scdb"
                in `utilities.data_folder()`.
            kind: "cases" (a row for each case) or "votes" (a row for each
                justice in each case). Defaults to "cases".
            refresh: whether to look for the latest release even if the
                folder has a file of the kind. Defaults to `False`.
            session: an object with a `get` method like a
                `requests.Session`. Defaults to `None`, in which case a
                `requests.Session` is made.
            **kwargs: not used.

        Returns:
            The table (see `cases` and `votes`).

        """
        kind = _kind(kind)
        paths = download(
            self._locate(source),
            kinds = kind,
            overwrite = utilities.to_bool(refresh),
            session = session)
        return _read(paths[kind], kind)


def cases(
    source: pd.DataFrame | pathlib.Path | str | None = None) -> pd.DataFrame:
    """Returns the Supreme Court Database's table with a row for each case.

    Args:
        source: the database's case centered file that is organized by
            citation (a CSV file, or the zip archive of one that
            https://scdb.la.psu.edu/data/ offers), as a path or a table.
            Defaults to `None`, in which case the latest release is used,
            which is downloaded unless it was before (see `download`).

    Returns:
        The table, with the database's names for its columns: "caseId" (such
            as "1946-001"), "usCite", "term", "caseName", "issueArea",
            "decisionDirection", "partyWinning", "majVotes", "minVotes", and
            the rest that its codebook explains.

    """
    return _read(source, 'cases')


def download(
    folder: pathlib.Path | str | None = None,
    *,
    kinds: Sequence[str] | str | None = None,
    overwrite: bool = False,
    session: Any = None) -> dict[str, pathlib.Path]:
    """Downloads the latest release of the Supreme Court Database.

    The files are those of the modern database (the terms since 1946) that
    are organized by citation, as zip archives of CSV files. They need no
    account:

    | Kind | File |
    | --- | --- |
    | `cases` | The case centered data: a row for each case (less than a megabyte). |
    | `votes` | The justice centered data: a row for each justice in each case (about 2 megabytes). |

    A file is saved with the name of its release (such as
    "SCDB_2026_01_caseCentered_Citation.csv.zip"), so the release that a
    study used is in the dataset's history. The database's page lists its
    releases, and the page of the latest one links to its files, so they are
    found by those links.

    Args:
        folder: the folder to save them in. Defaults to `None`, in which case
            "scdb" in `utilities.data_folder()` is used.
        kinds: the files to download: "cases", "votes", or both. Defaults to
            `None`, for both.
        overwrite: whether to look for the latest release even if the folder
            has a file of an earlier one (or of the same one). A new release
            comes out each year. Defaults to `False`.
        session: an object with a `get` method like a `requests.Session`.
            Defaults to `None`, in which case a `requests.Session` is made.

    Raises:
        requests.HTTPError: if a page or a file cannot be downloaded.
        ValueError: if one of `kinds` is not a file that courtpy knows, or
            the database's pages do not link to the files as they did.

    Returns:
        The path of each file, by its kind. If the folder has the files of
            more than one release, they are those of the latest.

    """
    files = options._SCDB_FILES
    wanted = list(files) if kinds is None else utilities.listify(kinds)
    unknown = [kind for kind in wanted if kind not in files]
    if unknown:
        message = f'kinds must be among {list(files)}, not {unknown}'
        raise ValueError(message)
    folder = pathlib.Path(folder).expanduser() if folder else _folder()
    session = utilities.open_session(session)
    release: tuple[str, list[str]] | None = None
    paths = {}
    for kind in wanted:
        saved = sorted(folder.glob(f'*{files[kind]}*')) if not overwrite else []
        if saved:
            paths[kind] = saved[-1]
            continue
        release = release or _release(session)
        name, addresses = release
        path = folder / f'{name}_{files[kind]}.csv.zip'
        # The links to both files have the same words, so the file is
        # checked before it is saved.
        try:
            paths[kind] = amos.loaders.download_file(
                addresses[list(files).index(kind)],
                path,
                refresh = True,
                timeout = options._TIMEOUT,
                session = session,
                required_member = f'*{files[kind]}*')
        except ValueError as error:
            message = (
                f'the file that {options._SCDB_PAGE} links to for the '
                f'{kind} of the Supreme Court Database is not its '
                f'{files[kind]} file: download the file and pass its path '
                f'instead'
            )
            raise ValueError(message) from error
    return paths


def votes(
    source: pd.DataFrame | pathlib.Path | str | None = None) -> pd.DataFrame:
    """Returns the database's table with a row for each justice in each case.

    The table is for studying how the justices vote. The Martin-Quinn score
    of each justice in each term (see `courtpy.politics.justices`) can be
    added to it with the `merge_keys` technique of `amos`, by "term" and
    "justice".

    Args:
        source: the database's justice centered file that is organized by
            citation (a CSV file, or the zip archive of one that
            https://scdb.la.psu.edu/data/ offers), as a path or a table.
            Defaults to `None`, in which case the latest release is used,
            which is downloaded unless it was before (see `download`).

    Returns:
        The table, with the columns of `cases` (repeated for each justice of
            a case) and those of the justice: "justice" and "justiceName"
            (the database's number and name for the justice, such as 117 and
            "ACBarrett"), "vote", "opinion", "direction", "majority",
            "firstAgreement", and "secondAgreement".

    """
    return _read(source, 'votes')


""" Private Functions """


def _cite(citation: Any) -> str:
    """Returns a citation the way that citations are compared.

    Args:
        citation: a citation, such as "347 U.S. 483" or "74 S.Ct. 686".

    Returns:
        The citation in capital letters, without spaces or punctuation (such
            as "347US483"), or an empty `str` if `citation` is not text.

    """
    if not isinstance(citation, str):
        return ''
    return _SYMBOLS.sub('', citation.upper())


def _cited(table: pd.DataFrame) -> dict[str, int]:
    """Returns the row of the database for each citation that one row has.

    Args:
        table: the database's table of cases.

    Returns:
        The position of the row with each citation (as `_cite` writes it) in
            any of the columns of `_CITATIONS`. A citation that more than
            one row has (as short orders on one page of a reporter do) is
            given -1, since it does not say which case is meant.

    """
    rows: dict[str, int] = {}
    for column in _CITATIONS:
        if column not in table.columns:
            continue
        for position, citation in enumerate(table[column].tolist()):
            cite = _cite(citation)
            if cite:
                shared = rows.get(cite, position) != position
                rows[cite] = -1 if shared else position
    return rows


def _kind(kind: Any) -> str:
    """Returns a kind of the database's files, checked.

    Args:
        kind: "cases" or "votes".

    Raises:
        ValueError: if `kind` is not one of the files that courtpy knows.

    Returns:
        `kind` as text.

    """
    text = str(kind).strip()
    if text not in options._SCDB_FILES:
        message = (
            f'kind must be one of {list(options._SCDB_FILES)}, not {kind!r}')
        raise ValueError(message)
    return text


def _folder() -> pathlib.Path:
    """Returns the folder where the database is kept.

    Returns:
        "scdb" in `utilities.data_folder()`. It is not created.

    """
    return utilities.data_folder() / 'scdb'


def _read(
    source: pd.DataFrame | pathlib.Path | str | None,
    kind: str) -> pd.DataFrame:
    """Returns a table from a table or a file, or one of the database's.

    Args:
        source: a table (which is copied), the path of a CSV file (or of a
            zip archive of one), or `None`.
        kind: the file to use if `source` is `None`: "cases" or "votes". It
            is downloaded unless it was before (see `download`).

    Returns:
        The table.

    """
    if isinstance(source, pd.DataFrame):
        return source.copy()
    if source is None:
        source = download(kinds = kind)[kind]
    return utilities.read_csv(source, low_memory = False)


def _release(session: Any) -> tuple[str, list[str]]:
    """Finds the latest release of the database and its files.

    Args:
        session: an object with a `get` method like a `requests.Session`.

    Raises:
        requests.HTTPError: if a page cannot be downloaded.
        ValueError: if the database's page links to no release, or the page
            of the release does not link to a file for each of
            `options._SCDB_FILES`.

    Returns:
        The name of the release (such as "SCDB_2026_01") and the addresses
            of its files that are organized by citation, in the order of the
            page (which is that of `options._SCDB_FILES`).

    """
    pattern = re.compile(options._SCDB_RELEASE)
    # The page lists the latest release first.
    links = amos.loaders.page_links(
        options._SCDB_PAGE, session = session, timeout = options._TIMEOUT)
    for page, _ in links:
        found = pattern.search(page)
        if found is None:
            continue
        addresses = [
            address for address, words in amos.loaders.page_links(
                page, session = session, timeout = options._TIMEOUT)
            if options._SCDB_LINK.lower() in words.lower()]
        if len(addresses) < len(options._SCDB_FILES):
            message = (
                f'{page} does not link to the files of the Supreme Court '
                f'Database as it did: download the files and pass their '
                f'paths instead'
            )
            raise ValueError(message)
        return f'SCDB_{found.group(1)}_{found.group(2)}', addresses
    message = (
        f'no release of the Supreme Court Database was found on '
        f'{options._SCDB_PAGE}: download its files and pass their paths '
        f'instead'
    )
    raise ValueError(message)
