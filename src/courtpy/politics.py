"""Adds the political context of each year to parsed cases.

`build_table` makes a table of years from three
sources:

| Columns | Meaning | Source |
| --- | --- | --- |
| `president_party` | The party of the president: -1 for Democratic and 1 for Republican. | courtpy (see `presidents`). |
| `supreme_court_median`, `supreme_court_min`, `supreme_court_max` | The Martin-Quinn scores of the median justice and of the most liberal and most conservative justices in the term that began in the year. Higher scores are more conservative. | The "justices" file of https://mqscores.wustl.edu/measures.php (see `martin_quinn`). |
| `senate_median`, `house_median` | The median NOMINATE score of the members of each chamber of Congress. Higher scores are more conservative. | The file of members' ideology of https://voteview.com/data (see `nominate`). |

The sources' current files are downloaded by the judicial-common-space
package when they are first needed (see `download`), and kept outside of
projects (in "politics" in `courtpy.utilities.data_folder()`), where it and
fjc-biographies look for them too. The tables are combined by their years
with the `merge_keys` technique of `amos`, which adds the columns of another
table's row that has the same keys.

`add_politics` (an `amos.Merger`, which is added to the `amos` library as
soon as courtpy is imported) is that technique with the year of each case as
its key: it adds the table's columns to each case, with "politics_" before
their names. With no table, it adds only "politics_president_party", which
needs no file. Any table with a "year" column can be used, so other measures
can be added in a spreadsheet:

```python
import courtpy

courtpy.politics.build_table().to_csv("politics.csv", index = False)
dataset = courtpy.code(cases, "add_politics", parameters = {
    "add_politics": {"source": "politics.csv"}})
```

`load_politics` and `download_politics` (reference loaders, see
`courtpy.loaders.ReferenceLoader`) start a study of the years themselves,
with a saved table or one that `build_table` makes.

Contents:
    AddPolitics: adds the columns of a table of years to each case.
    DownloadPolitics: downloads the sources of the political context and
        loads its table.
    LoadPolitics: loads a table of the political context of each year.
    build_table: makes a table of the political context of each year.
    download: downloads the files of Martin-Quinn and NOMINATE scores with
        judicial-common-space.
    justices: returns the Martin-Quinn and Judicial Common Space scores of
        each justice in each term.
    martin_quinn: returns the Martin-Quinn scores of the Supreme Court in
        each year.
    nominate: returns the median NOMINATE scores of the Senate and the House
        in each year.
    presidents: returns the party of the president in each year.
    _CHAMBERS: the columns that `nominate` makes, by the name of each chamber
        of Congress in the file of members.
    _COURT: the columns that `martin_quinn` makes, by the summary of the
        justices' scores that each is.
    _SOURCES: the files that `download` gets, by what judicial-common-space
        calls each.

"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Iterable, Sequence
from typing import Any

import amos
import judicial_common_space
import pandas as pd

from . import jcs, loaders, options, utilities

_CHAMBERS: dict[str, str] = {
    'Senate': 'senate_median', 'House': 'house_median'}
_COURT: dict[str, str] = {
    'median': 'supreme_court_median',
    'min': 'supreme_court_min',
    'max': 'supreme_court_max'}
_SOURCES: dict[str, str] = {'justices': 'martin_quinn', 'congress': 'congress'}


@dataclasses.dataclass
class AddPolitics(amos.mergers.MergeKeys):
    """Adds the columns of a table of years to each case.

    Every column of the table (see `build_table`) is added to the cases, with
    a prefix before its name: each case gets the values of its year. A case
    whose year is missing, or is not in the table, gets missing values.

    It is the `merge_keys` technique of `amos`, with the year as the key. So
    it takes that merger's parameters, never adds, removes, or reorders
    rows, and records how many cases it matched in the dataset's history:

    | Parameter | Meaning |
    | --- | --- |
    | `source` | The table of years: the path of a data file (looked for in the current folder and then in the clerk's input folder), or a table. Without it, the table is the party of the president in each year (see `presidents`). |
    | `on` | The column of the cases to match by. It is "year" unless another is set. |
    | `other_on` | The column of the table to match by, if it has another name there. |
    | `prefix` | Text to put before the names of the table's columns. It is "politics_" unless another is set. |
    | `columns` | The columns of the table to add. By default, they are all of them. |
    | `indicator` | The name of a column to make that says whether each case's year was in the table. |
    | `duplicates` | What to do if the table has more than one row for a year: "error" (the default), "first", or "last". |

    Needs "year" (or the column named by "on").

    """

    def apply(
        self,
        item: amos.Dataset,
        *,
        source: Any = None,
        columns: Sequence[str] | str | None = None,
        prefix: str | None = 'politics_',
        on: Sequence[str] | str = 'year',
        **kwargs: Any) -> amos.Dataset:
        """Adds the political context of each case's year to `item`.

        Args:
            item: the dataset of parsed cases.
            source: a table with a row for each year, or the path of a data
                file of one. Defaults to `None`, in which case it is the
                party of the president in each year (see `presidents`).
            columns: the columns of the table to add, as a list or as text
                with commas between their names. Defaults to `None`, for
                all of them.
            prefix: text to put before the names of the table's columns.
                Defaults to "politics_".
            on: name of the column of the cases by which they are matched to
                the table. Defaults to "year".
            **kwargs: other parameters of the `merge_keys` technique of
                `amos`, such as "other_on", "indicator", and "duplicates".

        Raises:
            KeyError: if the cases or the table lack the column to match by.
            TypeError: if the column is numbers in one and text in the other.
            ValueError: if the table has more than one row for a year (and
                "duplicates" is "error").

        Returns:
            The dataset, with the new columns.

        """
        return super().apply(
            item,
            source = presidents() if source is None else source,
            columns = None if columns is None else utilities.listify(columns),
            prefix = prefix,
            on = on,
            **kwargs)


@dataclasses.dataclass
class LoadPolitics(loaders.ReferenceLoader):
    """Loads a table of the political context of each year.

    The table starts a study of the years themselves. Its "source" is the
    path of a saved table of years (in any format that the clerk knows).
    Without one, the table is made from the sources' current files (see
    `build_table`), which are downloaded first if they are missing, and
    "supreme_court", "congress", "score", and "common_space" are passed to
    `build_table`. To add the table's columns to parsed cases, use
    `add_politics` instead.

    """

    """ Public Methods """

    def load(
        self,
        source: Any,
        *,
        supreme_court: bool | pathlib.Path | str | None = None,
        congress: bool | pathlib.Path | str | None = None,
        score: str = 'nominate_dim1',
        common_space: bool | pathlib.Path | str = False,
        **kwargs: Any) -> Any:
        """Returns the table of years.

        Args:
            source: the path of a saved table of years, or "current" to make
                the table from the sources' current files.
            supreme_court: the file of the justices' Martin-Quinn scores, or
                "false" to leave them out (see `build_table`). Defaults to
                `None`, for the current file.
            congress: the file of the ideology of every member of Congress,
                or "false" to leave it out. Defaults to `None`, for the
                current file.
            score: the column of the file of Congress with the score to use.
                Defaults to "nominate_dim1".
            common_space: the file of Judicial Common Space medians, or
                "true" for the current file. Defaults to `False`, which
                leaves them out.
            **kwargs: parameters for `read`, for a saved table.

        Returns:
            The table, with a "year" column.

        """
        path = self._locate(source)
        if path is not None:
            return self.read(path, **kwargs)
        common = self._choose(common_space)
        return build_table(
            self._choose(supreme_court),
            self._choose(congress),
            score = score,
            common_space = False if common is None else common)


@dataclasses.dataclass
class DownloadPolitics(loaders.ReferenceLoader):
    """Downloads the sources of the political context and loads its table.

    The files of Martin-Quinn and NOMINATE scores (and, with "common_space",
    of Judicial Common Space medians) are downloaded unless they are there
    already, or "refresh" is true (see `download` and
    `courtpy.jcs.download`). Then the table of years is made from them (see
    `build_table`). Its "source" is the data folder whose "politics" (and
    "jcs") folder keeps the files, which is
    `courtpy.utilities.data_folder()` unless another is set.

    """

    """ Public Methods """

    def load(
        self,
        source: Any,
        *,
        supreme_court: bool | str = True,
        congress: bool | str = True,
        score: str = 'nominate_dim1',
        common_space: bool | str = False,
        refresh: bool | str = False,
        session: Any = None,
        **kwargs: Any) -> pd.DataFrame:
        """Downloads the sources' files and returns the table of years.

        Args:
            source: the data folder, or "current" for
                `utilities.data_folder()`.
            supreme_court: whether to download and add the Martin-Quinn
                scores of the Supreme Court. Defaults to `True`.
            congress: whether to download and add the NOMINATE scores of
                Congress. Defaults to `True`.
            score: the column of the file of Congress with the score to use.
                Defaults to "nominate_dim1".
            common_space: whether to download and add the Judicial Common
                Space medians. Defaults to `False`.
            refresh: whether to download the files even if they are there.
                Defaults to `False`.
            session: an object with a `get` method like a
                `requests.Session`. Defaults to `None`, in which case one is
                made.
            **kwargs: not used.

        Returns:
            The table, with a "year" column (see `build_table`).

        """
        folder = self._locate(source)
        overwrite = utilities.to_bool(refresh)
        chosen = {
            'justices': utilities.to_bool(supreme_court),
            'congress': utilities.to_bool(congress)}
        wanted = [kind for kind, use in chosen.items() if use]
        paths: dict[str, Any] = download(
            folder, kinds = wanted, overwrite = overwrite,
            session = session) if wanted else {}
        medians: pathlib.Path | bool = False
        if utilities.to_bool(common_space):
            medians = jcs.download(
                folder, kinds = 'medians', overwrite = overwrite,
                session = session)['medians']
        return build_table(
            paths.get('justices', False),
            paths.get('congress', False),
            score = score,
            common_space = medians)


def build_table(
    supreme_court: pd.DataFrame | pathlib.Path | str | bool | None = None,
    congress: pd.DataFrame | pathlib.Path | str | bool | None = None,
    *,
    score: str = "nominate_dim1",
    common_space: pd.DataFrame | pathlib.Path | str | bool = False) -> (
        pd.DataFrame):
    """Makes a table of the political context of each year.

    Args:
        supreme_court: the file of the justices' Martin-Quinn scores in each
            term (see `martin_quinn`). Defaults to `None`, in which case the
            current file is used, which is downloaded unless it was before
            (see `download`). `False` leaves the court's scores out of the
            table.
        congress: the file of the ideology of every member of Congress (see
            `nominate`). Defaults to `None`, in which case the current file
            is used, which is downloaded unless it was before. `False`
            leaves the scores of Congress out of the table.
        score: the column of `congress` with the score to use. Defaults to
            "nominate_dim1".
        common_space: the file of Judicial Common Space medians (see
            `courtpy.jcs.medians`). Defaults to `False`, which leaves them out
            of the table. `True` uses the current file, which is downloaded
            unless it was before.

    Returns:
        A table with a "year" column and the columns of `presidents`,
            `martin_quinn`, `nominate`, and (with `common_space`)
            `courtpy.jcs.medians`, for every year that any of them has. A
            year that a source lacks has missing values for it.

    """
    tables = [presidents()]
    if supreme_court is not False:
        tables.append(martin_quinn(
            None if supreme_court is True else supreme_court))
    if congress is not False:
        tables.append(nominate(
            None if congress is True else congress, score = score))
    if common_space is not False:
        tables.append(jcs.medians(
            None if common_space is True else common_space))
    years = sorted(set().union(*(table['year'].tolist() for table in tables)))
    context = amos.Dataset(pd.DataFrame({'year': years}))
    merger = amos.mergers.MergeKeys()
    for table in tables:
        merger.apply(context, source = table, on = 'year')
    return context.data


def download(
    folder: pathlib.Path | str | None = None,
    *,
    kinds: Sequence[str] | str | None = None,
    overwrite: bool = False,
    session: Any = None) -> dict[str, pathlib.Path]:
    """Downloads the files of Martin-Quinn and NOMINATE scores.

    | Kind | File | Source |
    | --- | --- | --- |
    | `justices` | "justices.csv": the Martin-Quinn score of each justice in each term. | https://mqscores.wustl.edu/measures.php |
    | `congress` | "HSall_members.csv": the ideology of every member of every Congress (about 6 megabytes). | https://voteview.com/data (its "Member Ideology" data for both chambers and all Congresses) |

    `judicial_common_space.sources.download` downloads them, into the
    "politics" folder of `folder`, where it and fjc-biographies look for the
    files too, so courtpy and those packages share them. The Martin-Quinn
    scores are released each year, in a folder named for the year, so their
    file is found by its link on the page. The page is behind a check for
    automated browsers, which can refuse the download. Then save
    "justices.csv" from the page in a browser and put it in the "politics"
    folder (or pass its path to `justices` and `martin_quinn`).

    Args:
        folder: the data folder, whose "politics" folder they are saved in.
            Defaults to `None`, in which case `utilities.data_folder()` is
            used.
        kinds: the files to download: "justices", "congress", or both.
            Defaults to `None`, for both.
        overwrite: whether to download a file that is already there. The
            scores change as justices and members vote. Defaults to `False`.
        session: an object with a `get` method like a `requests.Session`.
            Defaults to `None`, in which case a `requests.Session` that
            identifies courtpy is made.

    Raises:
        requests.HTTPError: if a page or a file cannot be downloaded.
        ValueError: if one of `kinds` is not a file that courtpy knows, or
            the page of Martin-Quinn scores has no link to its file.

    Returns:
        The path of each file, by its kind.

    """
    wanted = list(_SOURCES) if kinds is None else utilities.listify(kinds)
    unknown = [kind for kind in wanted if kind not in _SOURCES]
    if unknown:
        message = f'kinds must be among {list(_SOURCES)}, not {unknown}'
        raise ValueError(message)
    paths = judicial_common_space.sources.download(
        [_SOURCES[kind] for kind in wanted],
        folder or utilities.data_folder(),
        overwrite = overwrite,
        session = utilities.open_session(session))
    return {kind: paths[_SOURCES[kind]] for kind in wanted}


def justices(
    source: pd.DataFrame | pathlib.Path | str | None = None) -> pd.DataFrame:
    """Returns the Martin-Quinn and Common Space scores of each justice.

    `judicial_common_space.politics.justices` reads the scores and puts each
    Martin-Quinn score on the scale of the Judicial Common Space. The
    justices have the numbers that the Supreme Court Database gives them, so
    the scores can be added to its votes (see `courtpy.scdb.votes`) with the
    `merge_keys` technique of `amos`, by "term" and "justice".

    Args:
        source: the "justices" file of the Martin-Quinn scores (from
            https://mqscores.wustl.edu/measures.php), as a path or a table.
            It has a row for each justice in each term, with the columns
            "term", "justice", "justiceName", and "post_mn". Defaults to
            `None`, in which case the current file is used, which is
            downloaded unless it was before (see `download`).

    Raises:
        KeyError: if `source` lacks a column that is needed.

    Returns:
        A table with "term" (the year in which the term began, in October),
            "justice" and "justiceName" (the Supreme Court Database's number
            and name for the justice, such as 117 and "ACBarrett"),
            "martin_quinn" (the mean of the estimates of the justice's
            score), and "jcs" (the score on the scale of the Judicial Common
            Space).

    """
    scores: pd.DataFrame = judicial_common_space.politics.justices(
        _read(source, 'justices'))
    return scores


def martin_quinn(
    source: pd.DataFrame | pathlib.Path | str | None = None) -> pd.DataFrame:
    """Returns the Martin-Quinn scores of the Supreme Court in each year.

    The scores are summaries of the scores of the justices who served in
    each term (see `justices`): their median and the lowest and highest of
    them. A term in which a justice was replaced (such as 2005, when Samuel
    Alito replaced Sandra Day O'Connor) has the scores of both.

    Args:
        source: the "justices" file of the Martin-Quinn scores (see
            `justices`), as a path or a table. Defaults to `None`, in which
            case the current file is used, which is downloaded unless it was
            before (see `download`).

    Raises:
        KeyError: if `source` lacks a column that is needed.

    Returns:
        A table with "year" (the year in which the term began, in October),
            "supreme_court_median", "supreme_court_min", and
            "supreme_court_max".

    """
    scores = justices(source).dropna(subset = ['term', 'martin_quinn'])
    summaries = scores.groupby('term')['martin_quinn'].agg(list(_COURT))
    table = summaries.rename(columns = _COURT).rename_axis('year')
    return table.reset_index().astype({'year': int})


def nominate(
    source: pd.DataFrame | pathlib.Path | str | None = None,
    *,
    score: str = 'nominate_dim1') -> pd.DataFrame:
    """Returns the median NOMINATE scores of the Senate and House in each year.

    Args:
        source: the file of the ideology of every member of every Congress
            ("HSall_members.csv", which https://voteview.com/data offers as
            its "Member Ideology" data), as a path or a table. It has a row
            for each member of each Congress, with the columns "congress"
            and "chamber" and a column for each score. Defaults to `None`,
            in which case the current file is used, which is downloaded
            unless it was before (see `download`).
        score: the column with the score to use: "nominate_dim1" (the
            default, the first dimension of DW-NOMINATE, on which higher
            scores are more conservative), "nominate_dim2",
            "nokken_poole_dim1", or "nokken_poole_dim2".

    Raises:
        KeyError: if `source` lacks a column that is needed.

    Returns:
        A table with "year", "senate_median", and "house_median". A Congress
            sits for two years (the 97th sat in 1981 and 1982), so both have
            its medians.

    """
    members = _read(source, 'congress')
    _require(
        members, ['congress', 'chamber', score],
        'the file of the ideology of members of Congress')
    members = members[members['chamber'].isin(list(_CHAMBERS))]
    medians = members.assign(
        congress = members['congress'].astype(int),
        score = pd.to_numeric(members[score], errors = 'coerce')).pivot_table(
            index = 'congress', columns = 'chamber', values = 'score',
            aggfunc = 'median')
    medians = medians.reindex(columns = list(_CHAMBERS)).rename(
        columns = _CHAMBERS)
    # The first Congress met in 1789, and each sits for two years.
    first = medians.index.to_numpy() * 2 + 1787
    years = pd.concat([
        medians.assign(year = first), medians.assign(year = first + 1)])
    years = years.sort_values('year').reset_index(drop = True)
    years.columns.name = None
    return years[['year', *_CHAMBERS.values()]]


def presidents(start: int | None = None, end: int | None = None) -> (
        pd.DataFrame):
    """Returns the party of the president in each year.

    The parties are in `options._PRESIDENTS`, by year, where a year can be
    added. A president who takes office in a year (in January) is the
    president of that year.

    Args:
        start: the first year. Defaults to `None`, in which case it is the
            first year that courtpy knows the party of (1933).
        end: the last year. Defaults to `None`, in which case it is the last
            year that courtpy knows the party of, the last of the latest
            president's term.

    Raises:
        ValueError: if `start` or `end` is a year that courtpy does not know
            the party of the president in.

    Returns:
        A table with "year" and "president_party" (-1 for Democratic and 1
            for Republican).

    """
    parties = pd.Series(options._PRESIDENTS, dtype = 'Int64')
    earliest, latest = int(parties.index.min()), int(parties.index.max())
    start = earliest if start is None else start
    end = latest if end is None else end
    if start < earliest or end > latest:
        message = (
            f'courtpy knows the party of the president from {earliest} to '
            f'{latest}, not from {start} to {end}'
        )
        raise ValueError(message)
    years = list(range(start, end + 1))
    return pd.DataFrame({
        'year': years,
        'president_party': parties.reindex(years).array})


""" Private Functions """


def _read(
    source: pd.DataFrame | pathlib.Path | str | None,
    kind: str) -> pd.DataFrame:
    """Returns a table from a table or a CSV file, or one of the sources'.

    Args:
        source: a table (which is copied), the path of a CSV file, or `None`.
        kind: the file to use if `source` is `None`: "justices" or
            "congress". It is downloaded unless it was before (see
            `download`).

    Returns:
        The table.

    """
    if isinstance(source, pd.DataFrame):
        return source.copy()
    if source is None:
        source = download(kinds = kind)[kind]
    return utilities.read_csv(source)


def _require(data: pd.DataFrame, columns: Iterable[str], name: str) -> None:
    """Raises an error if a table lacks columns.

    Args:
        data: the table.
        columns: names of the columns that are needed.
        name: what the table is, for the message.

    Raises:
        KeyError: if a column is missing.

    """
    missing = [c for c in columns if c not in data.columns]
    if missing:
        message = f'{name} needs the columns {missing}, which are missing'
        raise KeyError(message)
