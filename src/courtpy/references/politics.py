"""Adds the political context of each case: who held power when it was decided.

Three mergers (`amos.Merger` techniques, which are added to the `amos`
library as soon as courtpy is imported) add the ideology of the other
branches and of the Supreme Court on the day each case was decided. Each
matches the case's date to a table of date ranges with the `merge_ranges`
technique of `amos`, so another table with the same columns (such as the
governors of a state) can be its "source":

| Technique | Adds | Table |
| --- | --- | --- |
| `add_executive` | `executive_name` and `executive_ideology` (the president's party: -1 for Democratic and 1 for Republican). | `executives`: each president's term, from "instructions/federal/presidents.csv". |
| `add_legislature` | `senate_ideology` and `house_ideology`: the median DW-NOMINATE score of the members of each chamber of the Congress then sitting. Higher scores are more conservative. | `legislatures`: each Congress, from the file of members' ideology of https://voteview.com/data. |
| `add_high_court` | `high_court_ideology`: the Martin-Quinn score of the median justice in the term of the Supreme Court then sitting (from October to September). Higher scores are more conservative. | `high_courts`: each term, from the "justices" file of https://mqscores.wustl.edu/measures.php. |

Each takes "date" (the column with the date each case was decided, which is
"date_filed" unless another is set) and the parameters of every merger of
`amos` ("source", "columns", "prefix", and "indicator").

The sources' current files are downloaded by the judicial-common-space
package when they are first needed (see `download`), and kept outside of
projects (in "politics" in `courtpy.utilities.data_folder()`), where it and
fjc-biographies look for them too.

`build_table` makes a table of the political context of each year, with
the columns of `presidents` ("president_party"), `martin_quinn`
("supreme_court_median", ...), and `nominate` ("senate_median" and
"house_median"). `load_politics` and `download_politics` (reference loaders,
see `courtpy.loaders.ReferenceLoader`) start a study of the years
themselves with a saved table or one that `build_table` makes.

Contents:
    AddExecutive: adds the executive in power when each case was decided.
    AddHighCourt: adds the ideology of the Supreme Court when each case was
        decided.
    AddLegislature: adds the ideology of Congress when each case was
        decided.
    ByDate: makes a merger add the row of a table of date ranges that has
        each case's date.
    DownloadPolitics: downloads the sources of the political context and
        loads its table.
    LoadPolitics: loads a table of the political context of each year.
    build_table: makes a table of the political context of each year.
    download: downloads the files of Martin-Quinn and NOMINATE scores with
        judicial-common-space.
    executives: returns the term of each president.
    high_courts: returns the Martin-Quinn score of the median justice in
        each term of the Supreme Court.
    justices: returns the Martin-Quinn and Judicial Common Space scores of
        each justice in each term.
    legislatures: returns the median NOMINATE scores of each chamber in each
        Congress.
    martin_quinn: returns the Martin-Quinn scores of the Supreme Court in
        each year.
    nominate: returns the median NOMINATE scores of the Senate and the House
        in each year.
    presidents: returns the party of the president in each year.
    _CHAMBERS: the columns that `nominate` makes, by the name of each chamber
        of Congress in the file of members.
    _COURT: the columns that `martin_quinn` makes, by the summary of the
        justices' scores that each is.
    _FIRST_JANUARY_CONGRESS: the first Congress that met in January (under
        the Twentieth Amendment).
    _PRESIDENTS_FILE: the file of the presidents' terms.
    _SOURCES: the files that `download` gets, by what judicial-common-space
        calls each.

"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Sequence
from typing import Any, ClassVar

import amos
import judicial_common_space
import pandas as pd

from ..core import cases, utilities
from ..wrangler import loaders
from . import jcs

_CHAMBERS: dict[str, str] = {
    'Senate': 'senate_median', 'House': 'house_median'}
_COURT: dict[str, str] = {
    'median': 'supreme_court_median',
    'min': 'supreme_court_min',
    'max': 'supreme_court_max'}
_FIRST_JANUARY_CONGRESS: int = 74
_PRESIDENTS_FILE: pathlib.Path = (
    utilities.instructions_folder() / 'federal' / 'presidents.csv')
_SOURCES: dict[str, str] = {'justices': 'martin_quinn', 'congress': 'congress'}


class ByDate:
    """Makes a merger add the row of a table of date ranges with each date.

    A merger of courtpy subclasses it before `amos.Merger` (as in
    `class AddExecutive(ByDate, amos.Merger)`). Each row of its table is a
    range of dates ("start_date" and "end_date"), and each case gets the
    columns of the row whose range has the case's date, as the
    `merge_ranges` technique of `amos` finds it. A date on which one range
    ends and the next begins (such as the day of an inauguration) gets the
    later row. It is a mixin rather than a base class so that the merger
    stays a merger in the `amos` library.

    Attributes:
        added: the columns of the table that are added unless "columns" names
            others.

    """

    added: ClassVar[tuple[str, ...]]

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        source: Any = None,
        columns: Sequence[str] | str | None = None,
        date: str = 'date_filed',
        **kwargs: Any) -> amos.Dataset:
        """Adds the columns of the row of the table that has each case's date.

        Args:
            item: the dataset of cases (or of votes).
            source: the table of date ranges: a table, or the path of a data
                file of one, with "start_date" and "end_date". Defaults to
                `None`, in which case it is `default_table`.
            columns: the columns of the table to add. Defaults to `None`, for
                `added`.
            date: the column of `item` with the date each case was decided.
                Defaults to "date_filed".
            **kwargs: other parameters of the merger, such as "prefix" and
                "indicator".

        Raises:
            KeyError: if `item` lacks `date`, or the table lacks a column.

        Returns:
            The dataset, with the new columns.

        """
        return super().apply(  # type: ignore[misc, no-any-return]
            item,
            source = self.default_table() if source is None else source,
            columns = (
                list(self.added) if columns is None
                else utilities.listify(columns)),
            date = date,
            **kwargs)

    def default_table(self) -> pd.DataFrame:
        """Returns the table of date ranges that is used without a "source".

        Returns:
            The table, with "start_date", "end_date", and the columns of
                `added`.

        Raises:
            NotImplementedError: unless a subclass writes it.

        """
        raise NotImplementedError

    def match(
        self,
        data: pd.DataFrame,
        other: pd.DataFrame,
        *,
        date: str = 'date_filed',
        **kwargs: Any) -> Any:
        """Returns the row of the table whose range has each case's date.

        Args:
            data: the cases.
            other: the table of date ranges.
            date: the column of `data` with the date each case was decided.
                Defaults to "date_filed".
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks `date` or `other` lacks "start_date"
                or "end_date".

        Returns:
            The position of the matching row of `other` for each case, or -1
                if its date is missing or in no range.

        """
        name = repr(getattr(self, 'name', type(self).__name__))
        cases.require_columns(data, [date], name)
        cases.require_columns(
            other, ['start_date', 'end_date'], f'the table of {name}')
        dates = pd.DataFrame({
            'date': pd.to_datetime(data[date], errors = 'coerce')})
        ranges = pd.DataFrame({
            'start_date': pd.to_datetime(other['start_date']),
            'end_date': pd.to_datetime(other['end_date'])})
        return amos.mergers.MergeRanges().match(
            dates, ranges, column = 'date', start = 'start_date',
            end = 'end_date', duplicates = 'last')


@dataclasses.dataclass
class AddExecutive(ByDate, amos.Merger):
    """Adds the executive in power when each case was decided.

    Each case gets "executive_name" (the president, such as "Barack Obama")
    and "executive_ideology" (the president's party: -1 for Democratic and 1
    for Republican), from the term of the president on the case's date (see
    `executives`). A case decided on the day of an inauguration gets the new
    president. Another table of executives (such as a state's governors)
    with the same columns can be its "source". See `ByDate` for its
    parameters.

    """

    added: ClassVar[tuple[str, ...]] = (
        'executive_name', 'executive_ideology')

    def default_table(self) -> pd.DataFrame:
        """Returns the term of each president.

        Returns:
            The table of `executives`.

        """
        return executives()


@dataclasses.dataclass
class AddLegislature(ByDate, amos.Merger):
    """Adds the ideology of Congress when each case was decided.

    Each case gets "senate_ideology" and "house_ideology": the median
    DW-NOMINATE score (the first dimension, on which higher scores are more
    conservative) of the members of each chamber of the Congress that was
    sitting on the case's date (see `legislatures`). The file of members'
    ideology is downloaded the first time it is needed. Another table of
    legislatures (such as a state's) with the same columns can be its
    "source". See `ByDate` for its parameters.

    """

    added: ClassVar[tuple[str, ...]] = ('senate_ideology', 'house_ideology')

    def default_table(self) -> pd.DataFrame:
        """Returns the median scores of each chamber in each Congress.

        Returns:
            The table of `legislatures`.

        """
        return legislatures()


@dataclasses.dataclass
class AddHighCourt(ByDate, amos.Merger):
    """Adds the ideology of the Supreme Court when each case was decided.

    Each case gets "high_court_ideology": the Martin-Quinn score of the
    median justice (higher is more conservative) in the term of the Supreme
    Court that was sitting on the case's date, from October 1 to September
    30 (see `high_courts`). The file of Martin-Quinn scores is downloaded the
    first time it is needed. Another table of high courts (such as a state's
    supreme court) with the same columns can be its "source". See `ByDate`
    for its parameters.

    """

    added: ClassVar[tuple[str, ...]] = ('high_court_ideology',)

    def default_table(self) -> pd.DataFrame:
        """Returns the Martin-Quinn score of the median justice in each term.

        Returns:
            The table of `high_courts`.

        """
        return high_courts()


@dataclasses.dataclass
class LoadPolitics(loaders.ReferenceLoader):
    """Loads a table of the political context of each year.

    The table starts a study of the years themselves. Its "source" is the
    path of a saved table of years (in any format that the clerk knows).
    Without one, the table is made from the sources' current files (see
    `build_table`), which are downloaded first if they are missing, and
    "supreme_court", "congress", "score", and "common_space" are passed to
    `build_table`. To add the political context to parsed cases, use
    `add_executive`, `add_legislature`, and `add_high_court` instead.

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
    score: str = 'nominate_dim1',
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
    medians = _chamber_medians(source, score)
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

    The president of a year is the one in office at its end, so a president
    who takes office in a year (in January) is the president of that year.
    The terms are in "instructions/federal/presidents.csv" (see
    `executives`), where a president can be added.

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
    terms = executives()
    starts = pd.to_datetime(terms['start_date'])
    ends = pd.to_datetime(terms['end_date'])
    earliest = int(starts.min().year)
    # The last term ends during its last year, so the year before is the
    # last that a president is in office at the end of.
    latest = int(ends.max().year) - 1
    start = earliest if start is None else start
    end = latest if end is None else end
    if start < earliest or end > latest:
        message = (
            f'courtpy knows the party of the president from {earliest} to '
            f'{latest}, not from {start} to {end}'
        )
        raise ValueError(message)
    years = list(range(start, end + 1))
    last_day = pd.to_datetime([f'{year}-12-31' for year in years])
    chosen = starts.searchsorted(last_day, side = 'right') - 1
    parties = terms['executive_ideology'].astype('Int64').to_numpy()[chosen]
    return pd.DataFrame({
        'year': years,
        'president_party': pd.array(parties, dtype = 'Int64')})


def executives(source: pathlib.Path | str | None = None) -> pd.DataFrame:
    """Returns the term of each president.

    Args:
        source: a CSV file of terms, with "president", "party", "start_date",
            and "end_date". Defaults to `None`, for
            "instructions/federal/presidents.csv".

    Raises:
        KeyError: if `source` lacks a column that is needed.

    Returns:
        A table with "executive_name" (the president), "executive_ideology"
            (the president's party: -1 for Democratic and 1 for Republican),
            "start_date", and "end_date" (the days the term began and ended,
            as dates), sorted by the start of the terms.

    """
    terms = utilities.read_csv(source or _PRESIDENTS_FILE)
    cases.require_columns(
        terms, ['president', 'party', 'start_date', 'end_date'],
        'the table of presidents')
    table = pd.DataFrame({
        'executive_name': terms['president'].astype(str),
        'executive_ideology': pd.to_numeric(
            terms['party'], errors = 'coerce').astype('Int64'),
        'start_date': pd.to_datetime(terms['start_date']),
        'end_date': pd.to_datetime(terms['end_date'])})
    return table.sort_values('start_date').reset_index(drop = True)


def high_courts(
    source: pd.DataFrame | pathlib.Path | str | None = None) -> pd.DataFrame:
    """Returns the Martin-Quinn score of the median justice in each term.

    Args:
        source: the "justices" file of the Martin-Quinn scores (see
            `justices`), as a path or a table. Defaults to `None`, in which
            case the current file is used, which is downloaded unless it was
            before (see `download`).

    Raises:
        KeyError: if `source` lacks a column that is needed.

    Returns:
        A table with "term" (the year in which the term began),
            "start_date" (October 1 of that year), "end_date" (September 30
            of the next), and "high_court_ideology" (the score of the median
            justice; see `martin_quinn`).

    """
    terms = martin_quinn(source)
    years = terms['year'].astype(int)
    return pd.DataFrame({
        'term': years,
        'start_date': pd.to_datetime(years.astype(str) + '-10-01'),
        'end_date': pd.to_datetime((years + 1).astype(str) + '-09-30'),
        'high_court_ideology': terms['supreme_court_median'].to_numpy()})


def legislatures(
    source: pd.DataFrame | pathlib.Path | str | None = None,
    *,
    score: str = 'nominate_dim1') -> pd.DataFrame:
    """Returns the median NOMINATE scores of each chamber in each Congress.

    Args:
        source: the file of the ideology of every member of every Congress
            (see `nominate`), as a path or a table. Defaults to `None`, in
            which case the current file is used, which is downloaded unless
            it was before (see `download`).
        score: the column with the score to use. Defaults to "nominate_dim1"
            (see `nominate`).

    Raises:
        KeyError: if `source` lacks a column that is needed.

    Returns:
        A table with "congress" (its number), "start_date" and "end_date"
            (the day it first met and the day the next one did: January 3
            since the 74th, in 1935, and March 4 before), and
            "senate_ideology" and "house_ideology" (the median score of the
            members of each chamber).

    """
    medians = _chamber_medians(source, score)
    numbers = medians.index.to_numpy()
    starts = pd.to_datetime([_first_day(number) for number in numbers])
    ends = pd.to_datetime([_first_day(number + 1) for number in numbers])
    return pd.DataFrame({
        'congress': numbers,
        'start_date': starts,
        'end_date': ends,
        'senate_ideology': medians['senate_median'].to_numpy(),
        'house_ideology': medians['house_median'].to_numpy()})


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


def _chamber_medians(
    source: pd.DataFrame | pathlib.Path | str | None,
    score: str) -> pd.DataFrame:
    """Returns the median score of each chamber of each Congress.

    Args:
        source: the file of the ideology of every member of every Congress,
            as a path or a table, or `None` for the current file.
        score: the column with the score to use.

    Raises:
        KeyError: if `source` lacks a column that is needed.

    Returns:
        A table labeled by the number of each Congress, with
            "senate_median" and "house_median".

    """
    members = _read(source, 'congress')
    cases.require_columns(
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
    medians.columns.name = None
    return medians


def _first_day(congress: int) -> str:
    """Returns the day a Congress first met, as the Constitution set it.

    Args:
        congress: the number of the Congress.

    Returns:
        The date, as "YYYY-MM-DD": January 3 of its first year since the
            74th Congress (under the Twentieth Amendment), and March 4
            before.

    """
    year = congress * 2 + 1787
    day = '01-03' if congress >= _FIRST_JANUARY_CONGRESS else '03-04'
    return f'{year}-{day}'
