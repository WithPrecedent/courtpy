"""Adds Judicial Common Space scores of judges, justices, and courts.

The Judicial Common Space (Epstein, Martin, Segal, and Westerland, "The
Judicial Common Space," 23 J.L. Econ. & Org. 303 (2007)) places judges,
justices of the Supreme Court, members of Congress, and presidents on one
scale of ideology, on which higher scores are more conservative. The
judicial-common-space package
(https://github.com/WithPrecedent/judicial_common_space) computes the scores
and downloads the files that they are computed from and checked against,
which courtpy uses in three ways:

* Each appointment of a judge or justice has a score, which fjc-biographies
  adds to a roster with judicial-common-space
  (`courtpy.judges.Roster.from_fjc(jcs = True)`) as "jcs", an attribute of
  each judge like "party": `code_panels` adds "panel_jcs" (the mean score of
  each case's panel), and `add_biography` adds "judge_jcs". Unlike the
  published scores, which are of the judges of the courts of appeals and the
  justices, the computed scores are of district judges too.
* Each justice has a score in each term, which `courtpy.politics.justices`
  returns with the justice's Martin-Quinn score, so the scores can be added
  to the Supreme Court Database's votes (see `courtpy.scdb.votes`).
* Each year has the scores of the president and of the medians of the House,
  the Senate, the Supreme Court, and each court of appeals, which its authors
  publish at https://epstein.wustl.edu/jcs. `medians` reads them, so they can
  be added to cases by "year" with the `merge_keys` technique of `amos` (or
  be a part of `courtpy.politics.build_table`).

The published files are downloaded by judicial-common-space (see `download`)
into "jcs" in `courtpy.utilities.data_folder()`, where it looks for them too:

| Kind | File | Rows |
| --- | --- | --- |
| `judges` | "judges.csv" | Each judge of a court of appeals, with the judge's name, circuit, and score. |
| `justices` | "justices.csv" | Each justice in each term of the Supreme Court. |
| `medians` | "medians.csv" | Each year, with the scores of the president and of the medians of the House, the Senate, the Supreme Court, and each court of appeals. |

```python
import courtpy

roster = courtpy.judges.Roster.from_fjc(jcs = True)
roster.save()
table = courtpy.politics.build_table(common_space = True)
```

`download_jcs` (a reference loader, see `courtpy.loaders.ReferenceLoader`)
downloads the files and loads one of them, so a study can start from the
scores themselves.

Contents:
    DownloadJcs: downloads the published files of Judicial Common Space
        scores and loads one of them.
    download: downloads the published files of Judicial Common Space scores.
    medians: returns the scores of the president and of the medians of
        Congress and the courts in each year.

"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Sequence
from typing import Any

import judicial_common_space
import pandas as pd

from ..core import cases, utilities
from ..wrangler import loaders

# The published files, by what judicial-common-space calls each.
_KINDS: dict[str, str] = {
    'judges': 'jcs_judges',
    'justices': 'jcs_justices',
    'medians': 'jcs_medians'}
_MEDIANS: dict[str, str] = {
    'president': 'jcs_president',
    'house_median': 'jcs_house_median',
    'senate_median': 'jcs_senate_median',
    'sc_median': 'jcs_supreme_court_median',
    **{f'circuit_median{number}': f'jcs_circuit{number}_median'
       for number in range(1, 14)},
    **{f'circuit_sd{number}': f'jcs_circuit{number}_sd'
       for number in range(1, 14)}}


@dataclasses.dataclass
class DownloadJcs(loaders.ReferenceLoader):
    """Downloads the published files of Judicial Common Space scores.

    The archive of the scores is downloaded unless its files are there
    already, or "refresh" is true (see `download`), and the file named by
    "kind" is loaded: "medians" (the default, a row for each year, as
    `medians` returns it), "judges" (a row for each judge of a court of
    appeals), or "justices" (a row for each justice in each term). Its
    "source" is the data folder whose "jcs" folder keeps the files, which is
    `courtpy.utilities.data_folder()` unless another is set.

    """

    """ Public Methods """

    def load(
        self,
        source: Any,
        *,
        kind: str = 'medians',
        refresh: bool | str = False,
        session: Any = None,
        **kwargs: Any) -> pd.DataFrame:
        """Downloads the files and returns the table of one of them.

        Args:
            source: the data folder, or "current" for
                `utilities.data_folder()`.
            kind: the file to load: "medians", "judges", or "justices".
                Defaults to "medians".
            refresh: whether to download the archive even if the files are
                there. Defaults to `False`.
            session: an object with a `get` method like a
                `requests.Session`. Defaults to `None`, in which case one is
                made.
            **kwargs: not used.

        Raises:
            ValueError: if `kind` is not one of the files.

        Returns:
            The table.

        """
        kind = str(kind).strip()
        path = download(
            self._locate(source), kinds = kind,
            overwrite = utilities.to_bool(refresh), session = session)[kind]
        if kind == 'medians':
            return medians(path)
        return _read(path, kind)


def download(
    folder: pathlib.Path | str | None = None,
    *,
    kinds: Sequence[str] | str | None = None,
    overwrite: bool = False,
    session: Any = None) -> dict[str, pathlib.Path]:
    """Downloads the published files of Judicial Common Space scores.

    The scores are posted as one archive (about 100 kilobytes), which
    `judicial_common_space.sources.download` finds by its link on
    https://epstein.wustl.edu/jcs and unpacks. Its CSV files are saved as
    "judges.csv", "justices.csv", and "medians.csv" (see the module's
    documentation), and the archive is kept beside them.

    Args:
        folder: the data folder, whose "jcs" folder they are saved in.
            Defaults to `None`, in which case `utilities.data_folder()` is
            used.
        kinds: the files to return: any of "judges", "justices", and
            "medians". Defaults to `None`, for all of them. The archive is
            downloaded if any of them is missing.
        overwrite: whether to download the archive even if the files are
            there. The scores are updated every few years. Defaults to
            `False`.
        session: an object with a `get` method like a `requests.Session`.
            Defaults to `None`, in which case a `requests.Session` that
            identifies courtpy is made.

    Raises:
        requests.HTTPError: if the page or the archive cannot be downloaded.
        ValueError: if one of `kinds` is not a file that courtpy knows, the
            page has no link to an archive, or the archive lacks a file.

    Returns:
        The path of each file, by its kind.

    """
    wanted = list(_KINDS) if kinds is None else utilities.listify(kinds)
    unknown = [kind for kind in wanted if kind not in _KINDS]
    if unknown:
        message = f'kinds must be among {list(_KINDS)}, not {unknown}'
        raise ValueError(message)
    paths = judicial_common_space.sources.download(
        [_KINDS[kind] for kind in wanted],
        folder or utilities.data_folder(),
        overwrite = overwrite,
        session = utilities.open_session(session))
    return {kind: paths[_KINDS[kind]] for kind in wanted}


def medians(
    source: pd.DataFrame | pathlib.Path | str | None = None) -> pd.DataFrame:
    """Returns the scores of the president and of medians in each year.

    Args:
        source: the file of medians (see `download`), as a path or a table,
            with a "year" column and columns of scores. Defaults to `None`,
            in which case the current file is used, which is downloaded
            unless it was before.

    Raises:
        KeyError: if `source` lacks a "year" column.

    Returns:
        A table with "year" and, for each of these that the file has,
            "jcs_president" (the president's score),
            "jcs_house_median", "jcs_senate_median",
            "jcs_supreme_court_median", and "jcs_circuit{n}_median" and
            "jcs_circuit{n}_sd" (the median and standard deviation of the
            scores of each court of appeals, numbered as the federal rules
            number them, with 12 for the District of Columbia and 13 for the
            Federal Circuit). A year with more than one row in the file (as
            when a new president or Congress took office) has their means.

    """
    scores = _read(source, 'medians')
    cases.require_columns(
        scores, ['year'], 'the file of Judicial Common Space medians')
    columns = [column for column in _MEDIANS if column in scores.columns]
    numbers = scores[columns].apply(pd.to_numeric, errors = 'coerce')
    numbers['year'] = pd.to_numeric(scores['year'], errors = 'coerce')
    numbers = numbers.dropna(subset = ['year']).astype({'year': int})
    means = numbers.groupby('year')[columns].mean().reset_index()
    renamed: pd.DataFrame = means.rename(columns = _MEDIANS)
    return renamed


""" Private Functions """


def _read(
    source: pd.DataFrame | pathlib.Path | str | None,
    kind: str) -> pd.DataFrame:
    """Returns a table from a table or a CSV file, or one of the files.

    Args:
        source: a table (which is copied), the path of a CSV file, or `None`.
        kind: the file to use if `source` is `None`: "judges", "justices", or
            "medians". It is downloaded unless it was before (see
            `download`).

    Returns:
        The table, without the column of row numbers that the files have.

    """
    if isinstance(source, pd.DataFrame):
        table = source.copy()
    else:
        if source is None:
            source = download(kinds = kind)[kind]
        table = utilities.read_csv(source)
    numbered = [
        column for column in table.columns
        if str(column) == '' or str(column).startswith('Unnamed:')]
    return table.drop(columns = numbered)
