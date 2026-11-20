"""Adds the Federal Judicial Center's Integrated Database to cases.

The Federal Judicial Center's Integrated Database (IDB) has a record of each
appeal that the federal courts of appeals have docketed, terminated, or had
pending since the 2008 fiscal year, taken from the courts' own dockets: the
type of appeal, the parties, the court and judge appealed from, the dates of
each step, the judges of the panel and the opinions each wrote, how the
appeal ended, and whether the decision was published, among much else. It
covers the twelve regional circuits (not the Federal Circuit). Its codebooks
(https://www.fjc.gov/research/idb) explain each variable.

courtpy uses the fjc-idb package (https://github.com/WithPrecedent/fjc_idb)
to download, read, and decode the database's files. `download` gets the
yearly files that are missing and keeps them outside of projects (in
"fjc_idb" in `courtpy.utilities.data_folder()`, in the layout that fjc-idb
uses). `appeals` returns the database's table of appeals for a range of
years, with fjc-idb's descriptive names for its columns (such as
"appeal_type", "docket_date", and "judgment_date") and labels in place of
many of its codes. With `district = True`, each appeal from a district court
also has the district court's record of the case that was appealed (in
columns that begin with "district_"), which fjc-idb's `merge_district`
finds.

`add_idb` (an `amos.Merger`, which is added to the `amos` library as soon
as courtpy is imported) adds the database's columns, with "idb_" before
their names, by circuit and docket number. The database has a record for
each docket, so it is best added to `Dockets` (which `cases_to_dockets`
makes), each of whose rows has one docket number ("docket"). A case that
consolidated several appeals then has each appeal's record on its own row:

```python
import courtpy

cases = courtpy.parse("data/courtlistener")
dockets = courtpy.code(cases, ["cases_to_dockets", "add_idb"], parameters = {
    "add_idb": {"columns": "appeal_type, judgment_date, published"}})
```

Added to `Cases`, a case with several docket numbers gets the record of the
first of them that the database has.

`load_idb` and `download_idb` (reference loaders, see
`courtpy.loaders.ReferenceLoader`) start a study of the appeals themselves,
whether or not they have opinions.

Contents:
    AddIdb: adds the Integrated Database's record of each appeal to its
        case.
    DownloadIdb: downloads the Integrated Database's files and loads its
        appeals.
    CompareWithIdb: compares a dataset with the Integrated Database's
        records of appeals, and its appeals that the dataset lacks.
    LoadIdb: loads the Integrated Database's table of appeals for a range of
        years.
    appeals: returns the database's table of appeals for a range of years.
    download: downloads the database's yearly files that are missing.
    logger: the module's logger, which reports the files that are
        downloaded.
    _BY: the columns of the database that the groups of `compare_with_idb`
        name.
    _DOCKET_COLUMN: the column of `Dockets` with each row's one docket
        number.
    _FALSE_TEXT: text that is false in a column of flags.
    _TRUE_TEXT: text that is true in a column of flags.
    _VARIABLES: the variables that `compare_with_idb` compares, by name.

"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import math
import pathlib
import re
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from typing import Any, ClassVar

import amos
import chrisjen
import fjc_idb
import fjc_idb.main
import fjc_idb.options
import fjc_idb.rules
import numpy as np
import pandas as pd

from ..core import cases, options, utilities
from ..wrangler import loaders, shapers

logger = logging.getLogger(__name__)
_COURTS: tuple[str, ...] = ('court_num', 'court')
# The federal rules number the D.C. Circuit 12 (and the Federal Circuit 13,
# which the database does not cover).
_COURT_NUMBERS: dict[int, str] = {
    **{number: str(number) for number in range(1, 12)}, 12: '0'}
_DATES: tuple[str, ...] = ('date_filed', 'year')
_DOCKET: re.Pattern[str] = re.compile(r'(?<!\d)(\d{2})-(\d{1,6})(?!\d)')
_DOCKET_COLUMN: str = 'docket'
_DOCKETS: tuple[str, ...] = ('docket_numbers', 'docket_number')
_KINDS: tuple[str, ...] = ('appellate', 'civil', 'criminal')
_TEXT_COLUMNS: tuple[str, ...] = (
    'circuit', 'docket_num_idb', 'docket_number', 'district_of_origin',
    'district_courthouse', 'district_docket', 'criminal_defendant_number',
    'joined_docket')


@dataclasses.dataclass
class AddIdb(amos.Merger):
    """Adds the Integrated Database's record of each appeal by its docket.

    Each row of `Dockets` (see `cases_to_dockets`) is matched to the
    database's record of the appeal with the same circuit and docket number
    ("docket"), so each docket of a case that consolidated several appeals
    gets its own record. Each row of `Cases` is matched by the first of its
    docket numbers that the database has. An appeal that was reopened or remanded has
    a record for each time it ended, under the same docket number, so the
    record whose judgment is nearest the date of the decision is used (or
    the latest one, if there are no dates), and never a record of an appeal
    docketed after the decision. A case that is not matched, such as a case
    of another court or of a year that the database does not cover, gets
    missing values.

    The database's records come from fjc-idb (see `appeals`). By default,
    they are those of the years of the cases (from the year of the earliest
    decision to the year after the latest, since the database's years end on
    September 30), and the yearly files that are missing are downloaded.

    Like every merger of `amos`, it takes these parameters, never adds,
    removes, or reorders rows, and records how many cases it matched in the
    dataset's history:

    | Parameter | Meaning |
    | --- | --- |
    | `source` | The database's table of appeals: a table, or the path of a file (looked for in the current folder and then in the clerk's input folder), such as the CSV file that the `fjc-idb` command makes. Without it, the table is made from the database's yearly files (see `appeals`). |
    | `columns` | The columns of the database to add, by fjc-idb's names for them (such as "appeal_type"). By default, they are all of them. |
    | `prefix` | Text to put before the names of the added columns. It is "idb_" unless another is set. |
    | `indicator` | The name of a column to make that says whether each case was found in the database. |
    | `start_year`, `stop_year` | The first and last years of the database to use, without a `source`. They cover the cases unless they are set. |
    | `district` | Whether to add the district court's record of the case that was appealed, without a `source` (in columns that begin with "idb_district_"). It is false unless set, since the district courts' files are large. |
    | `folder` | The folder of the database's yearly files, without a `source` (looked for in the current folder and then in the clerk's input folder). It is "fjc_idb" in courtpy's data folder unless another is set. |
    | `download` | Whether to download the yearly files that are missing, without a `source`. It is true unless set. |
    | `courts`, `dockets`, `dates` | The columns of the cases with their courts, docket numbers, and dates of decision. They are "court_num" (or else "court"), "docket" (in `Dockets`, and otherwise "docket_numbers" or else "docket_number"), and "date_filed" (or else "year") unless others are set. |

    Needs a court (a CourtListener court id, such as "ca1", or the number
    that the federal rules give a court of appeals) and docket numbers (such
    as "17-1234").

    """

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        source: Any = None,
        columns: Sequence[str] | str | None = None,
        prefix: str | None = 'idb_',
        start_year: int | None = None,
        stop_year: int | None = None,
        district: bool = False,
        folder: pathlib.Path | str | None = None,
        download: bool = True,
        **kwargs: Any) -> amos.Dataset:
        """Adds the database's record of the appeal of each case of `item`.

        Args:
            item: the dataset of parsed cases.
            source: the database's table of appeals, or the path of a file of
                it. Defaults to `None`, in which case it is made from the
                database's yearly files (see `appeals`).
            columns: the columns of the database to add, as a list or as
                text with commas between their names. Defaults to `None`,
                for all of them.
            prefix: text to put before the names of the added columns.
                Defaults to "idb_".
            start_year: the first year of the database to use, without a
                `source`. Defaults to `None`, in which case it is the year of
                the earliest decision in `item`.
            stop_year: the last year of the database to use, without a
                `source`. Defaults to `None`, in which case it is the year
                after the latest decision in `item` (but not after this
                year).
            district: whether to add the district court's record of the case
                that was appealed, without a `source`. Defaults to `False`.
            folder: the folder of the database's yearly files, without a
                `source`, which is found as the clerk finds files (see
                `utilities.locate`). Defaults to `None`, in which case
                "fjc_idb" in `utilities.data_folder()` is used.
            download: whether to download the yearly files that are missing,
                without a `source`. Defaults to `True`.
            **kwargs: other parameters of the mergers of `amos` (such as
                "indicator" and "reader"), and those of `match`.

        Raises:
            KeyError: if the cases lack a court or docket numbers, or one of
                "columns" is not in the database.
            ValueError: if the years of the cases are all before the
                database's first year, or an added column would have the
                name of a column of the cases.

        Returns:
            The dataset, with the new columns.

        """
        table, described = _load_appeals(
            self,
            item.data,
            source,
            start_year = start_year,
            stop_year = stop_year,
            district = district,
            folder = folder,
            download = download,
            dates = kwargs.get('dates', _DATES),
            reader = kwargs.pop('reader', None))
        # A merger leaves out the columns whose names the cases have, but
        # the prefix keeps the database's columns apart from the cases'.
        chosen = (
            list(table.columns) if columns is None
            else utilities.listify(columns))
        dataset = super().apply(
            item, source = table, columns = chosen, prefix = prefix, **kwargs)
        dataset.history[-1]['source'] = described
        return dataset

    def match(
        self,
        data: pd.DataFrame,
        other: pd.DataFrame,
        *,
        courts: Sequence[str] | str = _COURTS,
        dockets: Sequence[str] | str | None = None,
        dates: Sequence[str] | str = _DATES,
        **kwargs: Any) -> Any:
        """Returns the database's record of the appeal of each case.

        Args:
            data: the parsed cases.
            other: the database's table of appeals.
            courts: the columns of `data` with the court of each case, tried
                in order: CourtListener court ids or the numbers that the
                federal rules give the courts of appeals. Defaults to
                `_COURTS`.
            dockets: the columns of `data` with the docket numbers of each
                case, as lists or as text, tried in order. Defaults to
                `None`, in which case it is "docket" (the one docket number
                of each row of `Dockets`) if `data` has it, so that a row is
                matched only by its own docket, and otherwise `_DOCKETS`.
            dates: the columns of `data` with the date (or year) of each
                decision, tried in order. Defaults to `_DATES`.
            **kwargs: not used.

        Raises:
            KeyError: if `data` has none of `courts` or `dockets`.

        Returns:
            The position of the matching row of `other` for each row of
                `data`, or -1 if there is none.

        """
        courts = utilities.listify(courts)
        if dockets is None:
            dockets = [_DOCKET_COLUMN] if _DOCKET_COLUMN in data.columns else (
                list(_DOCKETS))
        dockets = utilities.listify(dockets)
        for wanted, kind in ((courts, 'courts'), (dockets, 'docket numbers')):
            if not any(column in data.columns for column in wanted):
                message = (
                    f'{self.name!r} needs the {kind} of the cases (one of '
                    f'the columns {wanted}), and the cases have none'
                )
                raise KeyError(message)
        records, docketed, judged = _records(other)
        circuits = _circuits(data, courts)
        decided = _decided(data, utilities.listify(dates))
        cells = [data[c].tolist() for c in dockets if c in data.columns]
        positions = np.full(len(data), -1, dtype = 'int64')
        for place, circuit in enumerate(circuits):
            if circuit is None:
                continue
            when = decided[place]
            numbers = [column[place] for column in cells]
            for key in _keys(circuit, numbers):
                # An appeal docketed after the decision is not its appeal.
                found = [
                    row for row in records.get(key, [])
                    if pd.isna(when) or pd.isna(docketed[row])
                    or docketed[row] <= when]
                if found:
                    positions[place] = min(found, key = lambda row: (
                        np.inf if pd.isna(when) or pd.isna(judged[row])
                        else abs((judged[row] - when).days), -row))
                    break
        return positions

    def read(self, source: Any, **kwargs: Any) -> pd.DataFrame:
        """Returns the database's table of appeals.

        A CSV file (such as the one that the `fjc-idb` command makes) keeps
        its codes and docket numbers as text, and its dates are read as
        dates.

        Args:
            source: the path of a file of the table, or a table.
            **kwargs: parameters for loading the file (see
                `amos.Merger.read`, or `pandas.read_csv` for a CSV file).

        Returns:
            The table.

        """
        if isinstance(source, str | pathlib.Path) and (
                '.csv' in pathlib.Path(str(source)).suffixes):
            path = utilities.locate(source, self.clerk)
            header = utilities.read_csv(path, nrows = 0).columns
            table = utilities.read_csv(
                path,
                dtype = {c: 'string' for c in _TEXT_COLUMNS if c in header},
                low_memory = False,
                **kwargs)
            for column in table.columns:
                if column.endswith('_date'):
                    table[column] = pd.to_datetime(
                        table[column], errors = 'coerce', format = 'ISO8601')
            return table
        return super().read(source, **kwargs)


@dataclasses.dataclass
class LoadIdb(loaders.ReferenceLoader):
    """Loads the Integrated Database's table of appeals for a range of years.

    The table starts a study of the appeals themselves, which need not have
    opinions. Its "source" is the folder of the database's yearly files, in
    fjc-idb's layout, which is "fjc_idb" in
    `courtpy.utilities.data_folder()` unless another is set. The files that
    are missing are downloaded first unless "download" is false (see
    `appeals`). To add the database's records to parsed cases, use
    `add_idb` instead.

    """

    """ Public Methods """

    def load(
        self,
        source: Any,
        *,
        start_year: int | str | None = None,
        stop_year: int | str | None = None,
        district: bool | str = False,
        download: bool | str = True,
        fix_city_spellings: bool | str = True,
        **kwargs: Any) -> pd.DataFrame:
        """Returns the database's table of appeals.

        Args:
            source: the folder of the yearly files, or "current" for
                "fjc_idb" in `utilities.data_folder()`.
            start_year: the first fiscal year to include. Defaults to `None`,
                in which case it is the database's first year.
            stop_year: the last fiscal year to include. Defaults to `None`,
                in which case it is this year.
            district: whether to add the district court's record of the case
                that each appeal is from. Defaults to `False`.
            download: whether to download the yearly files that are missing.
                Defaults to `True`.
            fix_city_spellings: whether to correct the names of cities that
                the database's codebook misspells. Defaults to `True`.
            **kwargs: not used.

        Returns:
            The table (see `appeals`).

        """
        return appeals(
            _year(start_year),
            _year(stop_year),
            self._locate(source),
            district = utilities.to_bool(district),
            download = utilities.to_bool(download),
            fix_city_spellings = utilities.to_bool(fix_city_spellings))


@dataclasses.dataclass
class DownloadIdb(loaders.ReferenceLoader):
    """Downloads the Integrated Database's files and loads its appeals.

    The yearly files that are missing are downloaded (see `download`), and
    every file of the years is downloaded again if "refresh" is true, which
    gets the latest records of the current year. Its "source" is the folder
    to keep the files in, which is "fjc_idb" in
    `courtpy.utilities.data_folder()` unless another is set.

    """

    """ Public Methods """

    def load(
        self,
        source: Any,
        *,
        start_year: int | str | None = None,
        stop_year: int | str | None = None,
        district: bool | str = False,
        refresh: bool | str = False,
        fix_city_spellings: bool | str = True,
        **kwargs: Any) -> pd.DataFrame:
        """Downloads the database's yearly files and returns its appeals.

        Args:
            source: the folder to keep the yearly files in, or "current" for
                "fjc_idb" in `utilities.data_folder()`.
            start_year: the first fiscal year to download and include.
                Defaults to `None`, in which case it is the database's first
                year.
            stop_year: the last fiscal year to download and include. Defaults
                to `None`, in which case it is this year.
            district: whether to also download the district courts' files and
                add the district court's record of the case that each appeal
                is from. Defaults to `False`.
            refresh: whether to download the files of years that are in the
                folder again. Defaults to `False`.
            fix_city_spellings: whether to correct the names of cities that
                the database's codebook misspells. Defaults to `True`.
            **kwargs: not used.

        Returns:
            The table (see `appeals`).

        """
        folder = self._locate(source)
        start, stop = _year(start_year), _year(stop_year)
        with_district = utilities.to_bool(district)
        download(
            start, stop, folder, district = with_district,
            overwrite = utilities.to_bool(refresh))
        return appeals(
            start, stop, folder, district = with_district, download = False,
            fix_city_spellings = utilities.to_bool(fix_city_spellings))


@dataclasses.dataclass
class CompareWithIdb(amos.describers.Describer):
    """Compares a dataset with the Integrated Database's records of appeals.

    The cases are made `Dockets` first (see `cases_to_dockets`), unless they
    are already, since the database has a record for each docket rather than
    for each decision. Each docket is matched to its record as `add_idb`
    matches it, and two tables are made.

    The first, stored under the technique's name, says how well the
    variables that both have agree, one row for each variable, for the
    dockets that were matched: how many dockets have both values ("compared"),
    how many of those agree ("matches", "match_share", and Cohen's "kappa"),
    and the disagreements in each direction ("data_only" is true in the data
    and false in the database, and "idb_only" the reverse). The variables
    are true-or-false. By default, they are each of these whose column the
    data has:

    | Variable | The data's column | The database's column |
    | --- | --- | --- |
    | criminal | "type_criminal" | "appeal_type" is a criminal appeal |
    | civil | "type_civil" | "appeal_type" is not a criminal appeal |
    | reversal | "outcome_reversal" | "disposition" is reversed (in whole or part) or remanded |
    | published | "published" | "published" |
    | dissent | "dissents" (more than 0) | "dissents" (more than 0) |
    | us_appellant | the United States is a party ("party1_united_states") and the appellant ("party1_appellant"), for either party | "us_appellant" |
    | pro_se_appellant | "pro_se_appellant" | "pro_se_appellant" |
    | prisoner_appeal | "prisoner_appeal" | "prisoner_appeal" |

    The second, stored under the technique's name and "_missing", compares
    the appeals in the database that the data has with those that it lacks,
    in each circuit (or district, or any column of the database) and in all
    of them ("All"). The database has every appeal, so the data always lacks
    some. What matters is whether the appeals it lacks differ from those it
    has, such as whether reversals are more common among them. The appeals
    are those of the data's circuits whose judgments are between the data's
    first and last decisions and, unless "merits_only" is false, that were
    decided on the merits (those with a "disposition"), since the others
    rarely have opinions. Each row is one variable in one group: how many
    appeals there are ("appeals"), how many the data has ("in_data") and
    their share ("coverage"), the share of the appeals with a known value
    that are true among those the data has ("share_in_data") and those it
    lacks ("share_missing"), their "difference", and the p value of a
    two-proportion z test of it ("p_value"). Its variables are the
    database's side of the variables above, by default.

    With "visualize", `idb_confusion_matrices` draws the first table and
    `idb_missing_differences` the second (stored in `figures` under the
    tables' names).

    | Parameter | Meaning |
    | --- | --- |
    | `variables` | The variables to compare: names of those above, or a mapping of new names to a column of the data and a column of the database (as a list or as text with a comma between them). By default, each of those above whose column the data has. |
    | `report` | The variables of the second table: names of those above, or columns of the database. By default, all of those above. |
    | `by` | "circuit", "district" (the district court appealed from), or another column of the database, for the groups of the second table. It is "circuit" unless set. |
    | `merits_only` | Whether the second table counts only the appeals decided on the merits. It is true unless set. |
    | `alpha` | Not used by the tables; `idb_missing_differences` stars differences whose p value is below it. |
    | `source`, `start_year`, `stop_year`, `district`, `folder`, `download`, `reader`, `courts`, `dockets`, `dates` | As for `add_idb`. |

    """

    visual: ClassVar[str] = 'idb_confusion_matrices'
    clerk: Any = dataclasses.field(default = None, repr = False)

    """ Class Methods """

    @classmethod
    def build(
        cls,
        name: str,
        project: Any,
        parameters: MutableMapping[str, Any] | None = None,
        **kwargs: Any) -> CompareWithIdb:
        """Builds the technique with the clerk of `project`.

        Args:
            name: name of the technique.
            project: the project the technique belongs to.
            parameters: more parameters, which take precedence over those in
                the settings. Defaults to `None`.
            **kwargs: other arguments for the constructor.

        Returns:
            The built technique.

        """
        kwargs.setdefault('clerk', project.clerk)
        return super().build(name, project, parameters, **kwargs)

    """ Required Methods """

    def describe(self, item: amos.Dataset, **kwargs: Any) -> pd.DataFrame:
        """Returns the table of how well the variables agree.

        Args:
            item: the dataset of cases or dockets.
            **kwargs: the parameters of `compare`.

        Returns:
            The first table of `compare`.

        """
        return self.compare(item, **kwargs)[0]

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        visualize: bool = False,
        **kwargs: Any) -> amos.Dataset:
        """Adds both tables of `compare` to the tables of `item`.

        Args:
            item: the dataset of cases or dockets. It is not changed, and
                stays cases if it is cases.
            visualize: whether to draw both tables as figures. The dataset's
                `visualize_explorers` replaces it, if it is set. Defaults to
                `False`.
            **kwargs: the parameters of `compare`.

        Returns:
            The dataset, with the new tables (and figures).

        """
        alpha = kwargs.pop('alpha', None)
        agreement, missing, details = self.compare(item, **kwargs)
        item.tables[self.name] = agreement
        item.tables[self.missing_name] = missing
        item.record(
            self.name, table = self.name, missing_table = self.missing_name,
            **details)
        if alpha is not None:
            kwargs['alpha'] = alpha
        self._visualize(item, visualize, kwargs)
        return item

    def compare(
        self,
        item: amos.Dataset,
        *,
        variables: Mapping[str, Any] | Sequence[str] | str | None = None,
        report: Sequence[str] | str | None = None,
        by: str = 'circuit',
        merits_only: bool | str = True,
        source: Any = None,
        start_year: int | None = None,
        stop_year: int | None = None,
        district: bool = False,
        folder: pathlib.Path | str | None = None,
        download: bool = True,
        reader: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        """Returns how the dataset agrees with the database, and what it lacks.

        Args:
            item: the dataset of cases or dockets.
            variables: the variables to compare: names of `_VARIABLES`, or a
                mapping of new names to a column of the data and a column of
                the database. Defaults to `None`, for each of `_VARIABLES`
                whose column the data has.
            report: the variables of the second table: names of
                `_VARIABLES` or columns of the database. Defaults to `None`,
                for all of `_VARIABLES`.
            by: "circuit", "district", or a column of the database, for the
                groups of the second table. Defaults to "circuit".
            merits_only: whether the second table counts only the appeals
                decided on the merits. Defaults to `True`.
            source: the database's table of appeals, or the path of a file of
                it (see `AddIdb.apply`). Defaults to `None`.
            start_year: the first year of the database to use, without a
                `source`. Defaults to `None`.
            stop_year: the last year of the database to use, without a
                `source`. Defaults to `None`.
            district: whether to read the district court's records too,
                without a `source` (needed for district columns other than
                "district_of_origin"). Defaults to `False`.
            folder: the folder of the database's yearly files, without a
                `source`. Defaults to `None`.
            download: whether to download the yearly files that are missing,
                without a `source`. Defaults to `True`.
            reader: parameters for reading `source`. Defaults to `None`.
            **kwargs: "courts", "dockets", and "dates" (see `AddIdb.match`).

        Raises:
            KeyError: if a variable or a column is unknown, or the database
                lacks "disposition" and `merits_only` is true.

        Returns:
            The table of agreement, the table of what the data lacks, and
                details for the dataset's history.

        """
        data = _as_dockets(item.data)
        merger = AddIdb(clerk = self.clerk)
        table, described = _load_appeals(
            merger, data, source, start_year = start_year,
            stop_year = stop_year, district = district, folder = folder,
            download = download, dates = kwargs.get('dates', _DATES),
            reader = reader)
        found = np.asarray(merger.match(data, table, **kwargs), dtype = 'int64')
        matched = found >= 0
        agreement = _agreement(
            data[matched], table.iloc[found[matched]], variables)
        universe = _universe(
            data, table, utilities.to_bool(merits_only),
            utilities.listify(kwargs.get('courts', _COURTS)),
            utilities.listify(kwargs.get('dates', _DATES)))
        in_data = np.isin(np.flatnonzero(universe), found[matched])
        missing = _missing(
            table[universe].assign(_in_data = in_data), report, by)
        details = {
            'source': described,
            'dockets': len(data),
            'matched': int(matched.sum()),
            'idb_appeals': int(universe.sum()),
            'in_data': int(in_data.sum()),
            'by': by}
        return agreement, missing, details

    """ Properties """

    @property
    def missing_name(self) -> str:
        """Returns the name of the table (and figure) of what the data lacks.

        Returns:
            The technique's name with "_missing" after it.

        """
        return f'{self.name}_missing'

    """ Private Methods """

    def _visualize(
        self,
        item: amos.Dataset,
        visualize: Any,
        parameters: Mapping[str, Any] | None = None) -> None:
        """Draws both tables, if it is asked for.

        Args:
            item: the dataset, with both tables.
            visualize: the technique's `visualize` argument.
            parameters: the parameters that the technique was applied with.
                Defaults to `None`.

        """
        super()._visualize(item, visualize, parameters)
        entry = next(
            e for e in reversed(item.history)
            if e.get('technique') == self.name)
        if entry.get('figure') != self.name:
            return
        settings = {'source': self.missing_name}
        if parameters and 'alpha' in parameters:
            settings['alpha'] = parameters['alpha']
        try:
            plot: Any = chrisjen.library.borrow('idb_missing_differences')()
            figure = plot.make_figure(item, **settings)
        except Exception as error:  # noqa: BLE001
            logger.warning(
                f'the figure of {self.missing_name!r} was not drawn: {error}')
            entry['figure_error'] = str(error)
            return
        item.figures[self.missing_name] = figure
        entry['missing_figure'] = self.missing_name

    def _visual_parameters(
        self,
        item: amos.Dataset,  # noqa: ARG002
        parameters: Mapping[str, Any]) -> dict[str, Any]:  # noqa: ARG002
        """Returns the parameters of `idb_confusion_matrices`.

        Args:
            item: the dataset, with the technique's table.
            parameters: the parameters that the technique was applied with.

        Returns:
            The name of the table of agreement as "source".

        """
        return {'source': self.name}


def appeals(
    start_year: int | None = None,
    stop_year: int | None = None,
    folder: pathlib.Path | str | None = None,
    *,
    district: bool = False,
    download: bool = True,
    fix_city_spellings: bool = True) -> pd.DataFrame:
    """Returns the Integrated Database's table of appeals for a range of years.

    fjc-idb reads the yearly files, keeps the records of appeals that were
    still pending only from the latest year (since each year's file repeats
    them), decodes the database's codes, and gives the columns descriptive
    names. Its codebooks of the columns are in its documentation
    (https://WithPrecedent.github.io/fjc_idb).

    Args:
        start_year: the first year to include. The database's years are the
            federal government's fiscal years, which end on September 30.
            Defaults to `None`, in which case it is the database's first year
            (`options._IDB_FIRST_YEAR`).
        stop_year: the last year to include. Defaults to `None`, in which
            case it is this year.
        folder: the folder of the database's yearly files, in fjc-idb's
            layout. Defaults to `None`, in which case "fjc_idb" in
            `utilities.data_folder()` is used.
        district: whether to add the district court's record of the case
            that each appeal is from (see `fjc_idb.merge_district`), from the
            district courts' files of the same years. Defaults to `False`.
        download: whether to download the yearly files that are missing (see
            `download`). Defaults to `True`.
        fix_city_spellings: whether to correct the names of cities that the
            database's codebook misspells. Defaults to `True`.

    Raises:
        FileNotFoundError: if the folder has no yearly files of appeals for
            the years.
        ValueError: if `start_year` is after `stop_year`.

    Returns:
        The table, with a row for each appeal (or each time an appeal ended,
            if it was reopened or remanded) and columns such as "circuit",
            "docket_number" (such as "No. 17-1234"), "appeal_type",
            "docket_date", "judgment_date", "disposition", "published", and
            "judge_1" (and, with `district`, "district_match" and the
            district court's columns).

    """
    start, stop = _span(start_year, stop_year)
    root = _folder(folder)
    if download:
        _download(start, stop, root, district = district)
    if district:
        return fjc_idb.merge_district(
            start, stop, root, fix_city_spellings = fix_city_spellings,
            export = False)
    data = fjc_idb.main.import_data(
        'appellate', start, stop,
        fjc_idb.main._get_data_path('appellate', root))
    return fjc_idb.main.parse_data(
        data, 'appellate', fix_city_spellings = fix_city_spellings)


def download(
    start_year: int | None = None,
    stop_year: int | None = None,
    folder: pathlib.Path | str | None = None,
    *,
    district: bool = False,
    overwrite: bool = False) -> list[pathlib.Path]:
    """Downloads the Integrated Database's yearly files that are missing.

    fjc-idb downloads each year's file from the Federal Judicial Center's
    website, with the codebook, and needs no account. A year whose file is
    in the folder is skipped unless `overwrite` is true. The Federal
    Judicial Center updates the file of the current year during the year, so
    overwrite it to get the latest records. Years that it has not published
    are skipped (fjc-idb logs a warning).

    Args:
        start_year: the first year to download. Defaults to `None`, in which
            case it is the database's first year (`options._IDB_FIRST_YEAR`).
        stop_year: the last year to download. Defaults to `None`, in which
            case it is this year.
        folder: the folder to keep the files in, in fjc-idb's layout
            ("appellate", "district/civil", "district/criminal", and "docs").
            Defaults to `None`, in which case "fjc_idb" in
            `utilities.data_folder()` is used.
        district: whether to also download the district courts' files of
            civil cases and criminal defendants, which `appeals` uses with
            `district = True`. They are much larger than the files of
            appeals. Defaults to `False`.
        overwrite: whether to download the files of years that are in the
            folder again. Defaults to `False`.

    Raises:
        ValueError: if `start_year` is after `stop_year`.

    Returns:
        The paths of the files that were downloaded.

    """
    start, stop = _span(start_year, stop_year)
    return _download(
        start, stop, _folder(folder), district = district,
        overwrite = overwrite)


""" Private Functions """


def _circuit(court: Any) -> str | None:
    """Returns the database's code for the circuit of a court.

    Args:
        court: a CourtListener court id (such as "ca1" or "cadc") or the
            number that the federal rules give a court of appeals (such as 1,
            or 12 for the D.C. Circuit).

    Returns:
        The database's code for the court's circuit (such as "1", or "0" for
            the D.C. Circuit), or `None` if `court` is not one of the
            database's courts.

    """
    if court is None or (not isinstance(court, str) and pd.isna(court)):
        return None
    if isinstance(court, str):
        text = court.strip().lower()
        if text in options._IDB_CIRCUITS:
            return options._IDB_CIRCUITS[text]
        if not text.isdigit():
            return None
        court = int(text)
    try:
        return _COURT_NUMBERS.get(int(court))
    except (TypeError, ValueError):
        return None


def _circuits(data: pd.DataFrame, courts: Sequence[str]) -> list[str | None]:
    """Returns the database's code for the circuit of each case.

    Args:
        data: the parsed cases.
        courts: the columns of `data` with the court of each case, tried in
            order.

    Returns:
        The code of each row of `data` (see `_circuit`), or `None` for a row
            whose court is not one of the database's.

    """
    found: list[str | None] = [None] * len(data)
    for column in courts:
        if column not in data.columns:
            continue
        for place, court in enumerate(data[column].tolist()):
            if found[place] is None:
                found[place] = _circuit(court)
    return found


def _decided(data: pd.DataFrame, dates: Sequence[str]) -> list[Any]:
    """Returns the date of each decision.

    Args:
        data: the parsed cases.
        dates: the columns of `data` with the date of each decision, or its
            year, tried in order. A year is taken to be its last day.

    Returns:
        The date of each row of `data` as a `pandas.Timestamp`, or `pd.NaT`
            if no column has it.

    """
    decided = pd.Series(pd.NaT, index = data.index, dtype = 'datetime64[ns]')
    for column in dates:
        if column not in data.columns:
            continue
        values = data[column]
        if pd.api.types.is_numeric_dtype(values.dtype):
            years = pd.to_numeric(values, errors = 'coerce')
            known = years.between(1, 9999)
            when = pd.to_datetime(
                years[known].astype('int64').astype(str) + '-12-31',
                errors = 'coerce')
            when = when.reindex(data.index)
        else:
            when = pd.to_datetime(
                values, errors = 'coerce', format = 'ISO8601')
        decided = decided.fillna(when.astype('datetime64[ns]'))
    return decided.tolist()


def _download(
    start: int,
    stop: int,
    root: pathlib.Path,
    *,
    district: bool = False,
    overwrite: bool = False) -> list[pathlib.Path]:
    """Downloads the database's yearly files that are missing.

    fjc-idb is only asked for the files of a kind if some year of that kind
    is missing (or `overwrite` is true), since it reads the Federal Judicial
    Center's page of the files each time it is asked.

    Args:
        start: the first year to download.
        stop: the last year to download.
        root: the folder to keep the files in, in fjc-idb's layout.
        district: whether to also download the district courts' files of
            civil cases and criminal defendants. Defaults to `False`.
        overwrite: whether to download the files of years that are in the
            folder again. Defaults to `False`.

    Returns:
        The paths of the files that were downloaded.

    """
    saved: list[pathlib.Path] = []
    for kind in _KINDS if district else _KINDS[:1]:
        folder = fjc_idb.main._get_data_path(kind, root)
        prefix = fjc_idb.options._SOURCE_PREFIXES[kind]
        missing = [
            year for year in range(start, stop + 1)
            if overwrite or not any(
                folder.glob(f'{prefix}{year % 100:02d}*.sas7bdat'))]
        if missing:
            logger.info(
                'downloading the FJC IDB %s files of %s-%s to %s',
                kind, min(missing), max(missing), root)
            saved.extend(fjc_idb.download(
                kind, min(missing), max(missing), root,
                overwrite = overwrite))
    return saved


def _year(value: int | str | None) -> int | None:
    """Returns a year from a setting.

    Args:
        value: a year, as a number or as text, or `None`.

    Raises:
        ValueError: if `value` is text that is not a whole number.

    Returns:
        The year, or `None` if `value` is `None` or blank.

    """
    if value is None or str(value).strip() == '':
        return None
    return int(value)


def _folder(folder: pathlib.Path | str | None = None) -> pathlib.Path:
    """Returns the folder where the database's files are kept.

    Args:
        folder: the folder. Defaults to `None`.

    Returns:
        `folder` (with "~" expanded), or "fjc_idb" in
            `utilities.data_folder()` if it is `None`. It is not created.

    """
    if folder:
        return pathlib.Path(folder).expanduser()
    return utilities.data_folder() / 'fjc_idb'


def _keys(circuit: str, cells: Sequence[Any]) -> list[tuple[str, str, int]]:
    """Returns the circuit, year, and number of each docket number of a case.

    Args:
        circuit: the database's code for the case's circuit.
        cells: the case's cells of the columns with its docket numbers, in
            the order in which they are tried: lists of docket numbers, text
            with one or more of them, or missing values.

    Returns:
        A key for each docket number, in order and without repeats: the
            circuit, the last two digits of the year the appeal was
            docketed, and its number that year (so that "17-01234" and
            "17-1234" are the same).

    """
    keys: list[tuple[str, str, int]] = []
    for cell in cells:
        if isinstance(cell, str):
            texts = [cell]
        elif isinstance(cell, list | tuple | np.ndarray):
            texts = [str(text) for text in cell]
        else:
            continue
        for text in texts:
            for year, number in _DOCKET.findall(text):
                key = (circuit, year, int(number))
                if key not in keys:
                    keys.append(key)
    return keys


def _records(
    table: pd.DataFrame,
) -> tuple[dict[tuple[str, str, int], list[int]], list[Any], list[Any]]:
    """Returns the database's records of each docket.

    Args:
        table: the database's table of appeals. It needs "circuit" (fjc-idb's
            label or the database's code) and "docket_number" (such as "No.
            17-1234") or "docket_num_idb" (the database's form, such as
            "1701234"). "docket_date" and "judgment_date" are used if they are
            there.

    Raises:
        KeyError: if `table` lacks "circuit" or both columns of docket
            numbers.

    Returns:
        The positions of the rows of `table` for each key (as `_keys` makes
            them), and the date that each row's appeal was docketed and its
            date of judgment (`pd.NaT` if it is unknown).

    """
    if 'circuit' not in table.columns or not (
            {'docket_number', 'docket_num_idb'} & set(table.columns)):
        message = (
            'the table of appeals needs the columns "circuit" and '
            '"docket_number" (or "docket_num_idb"), as fjc-idb names them'
        )
        raise KeyError(message)
    # fjc-idb's labels (such as "First Circuit") become the database's codes,
    # and codes stay as they are.
    circuits = _circuit_codes(table)
    if 'docket_number' in table.columns:
        parts = table['docket_number'].astype('string').str.extract(
            r'(\d{2})-(\d+)')
    else:
        idb = table['docket_num_idb'].astype('string').str.strip().str.zfill(7)
        parts = pd.DataFrame({0: idb.str[:2], 1: idb.str[2:]})
    numbers = pd.to_numeric(parts[1], errors = 'coerce')
    records: dict[tuple[str, str, int], list[int]] = {}
    for row, (circuit, year, number) in enumerate(zip(
            circuits.tolist(), parts[0].tolist(), numbers.tolist(),
            strict = True)):
        if pd.isna(circuit) or pd.isna(year) or pd.isna(number):
            continue
        records.setdefault((circuit, year, int(number)), []).append(row)

    def dates(column: str) -> list[Any]:
        """Returns a column of dates of `table`.

        Args:
            column: name of the column.

        Returns:
            Its dates, or `pd.NaT` for each row if `table` lacks it.

        """
        if column not in table.columns:
            return [pd.NaT] * len(table)
        return pd.to_datetime(
            table[column], errors = 'coerce', format = 'ISO8601').tolist()

    return records, dates('docket_date'), dates('judgment_date')


def _span(start_year: int | None, stop_year: int | None) -> tuple[int, int]:
    """Returns the first and last years of the database to use.

    Args:
        start_year: the first year, or `None` for the database's first year.
            A year before the database's first is taken to be its first.
        stop_year: the last year, or `None` for this year.

    Raises:
        ValueError: if the first year is after the last.

    Returns:
        The first and last years.

    """
    start = max(
        int(start_year or options._IDB_FIRST_YEAR), options._IDB_FIRST_YEAR)
    stop = int(stop_year or dt.datetime.now(tz = dt.UTC).year)
    if start > stop:
        message = (
            f"the Integrated Database's records of appeals begin in "
            f"{options._IDB_FIRST_YEAR}, so there are none for the years "
            f"{start_year}-{stop_year}"
        )
        raise ValueError(message)
    return start, stop


def _years(
    data: pd.DataFrame,
    start_year: int | None,
    stop_year: int | None,
    dates: Sequence[str] | str) -> tuple[int, int]:
    """Returns the years of the database that cover a table of cases.

    Args:
        data: the parsed cases.
        start_year: the first year, or `None` for the year of the earliest
            decision.
        stop_year: the last year, or `None` for the year after the latest
            decision (since the database's years end on September 30), but
            not after this year.
        dates: the columns of `data` with the date (or year) of each
            decision, tried in order.

    Raises:
        ValueError: if the first year is after the last (as it is if every
            decision was before the database's first year).

    Returns:
        The first and last years (see `_span`).

    """
    years = pd.Series(
        [when.year for when in _decided(data, utilities.listify(dates))
         if not pd.isna(when)],
        dtype = 'int64')
    this_year = dt.datetime.now(tz = dt.UTC).year
    if start_year is None and not years.empty:
        start_year = max(int(years.min()), options._IDB_FIRST_YEAR)
    if stop_year is None and not years.empty:
        stop_year = min(int(years.max()) + 1, this_year)
    return _span(start_year, stop_year)


def _agreement(
    data: pd.DataFrame,
    records: pd.DataFrame,
    variables: Mapping[str, Any] | Sequence[str] | str | None) -> pd.DataFrame:
    """Returns how well the variables of the data and the database agree.

    Args:
        data: the dockets that were matched.
        records: the database's record of each of `data`, in the same order.
        variables: the variables to compare (see `CompareWithIdb.compare`).

    Raises:
        KeyError: if a variable that was named is unknown, or a column of it
            is missing.

    Returns:
        One row for each variable (see `CompareWithIdb`).

    """
    chosen, named = _chosen_variables(variables)
    rows = []
    for name, variable in chosen.items():
        mine = _values(data, variable.data)
        theirs = _values(records, variable.idb)
        if mine is None or theirs is None:
            if named:
                side = 'data' if mine is None else 'database'
                needed = (
                    variable.data_text if mine is None else variable.idb_text)
                message = (
                    f'the {side} lacks the column of the variable {name!r} '
                    f'({needed})'
                )
                raise KeyError(message)
            continue
        ours = mine.to_numpy(dtype = 'float64')
        idb = theirs.to_numpy(dtype = 'float64')
        known = ~np.isnan(ours) & ~np.isnan(idb)
        counts = {
            (a, b): int(((ours == a) & (idb == b) & known).sum())
            for a in (0, 1) for b in (0, 1)}
        compared = int(known.sum())
        matches = counts[1, 1] + counts[0, 0]
        rows.append({
            'variable': name,
            'data_column': variable.data_text,
            'idb_column': variable.idb_text,
            'dockets': len(ours),
            'compared': compared,
            'matches': matches,
            'match_share': matches / compared if compared else np.nan,
            'both_true': counts[1, 1],
            'both_false': counts[0, 0],
            'data_only': counts[1, 0],
            'idb_only': counts[0, 1],
            'data_missing': int(np.isnan(ours).sum()),
            'idb_missing': int(np.isnan(idb).sum()),
            'kappa': _kappa(counts, compared)})
    columns = [
        'variable', 'data_column', 'idb_column', 'dockets', 'compared',
        'matches', 'match_share', 'both_true', 'both_false', 'data_only',
        'idb_only', 'data_missing', 'idb_missing', 'kappa']
    return pd.DataFrame(rows, columns = columns).set_index('variable')


def _as_dockets(data: pd.DataFrame) -> pd.DataFrame:
    """Returns a table of cases as a table of dockets.

    Args:
        data: cases (labeled by "case_id", or by their positions) or dockets
            (which have "docket").

    Raises:
        KeyError: if `data` has no docket numbers.

    Returns:
        `data` itself if it has "docket", and otherwise a row for each
            docket number of each case (see `cases_to_dockets`).

    """
    if _DOCKET_COLUMN in data.columns:
        return data
    if 'case_id' in data.columns:
        data = data.set_index('case_id')
    elif data.index.name != 'case_id':
        data = data.rename_axis('case_id')
    return shapers.CasesToDockets().shape(data)


def _chosen_variables(
    variables: Mapping[str, Any] | Sequence[str] | str | None,
) -> tuple[dict[str, _Variable], bool]:
    """Returns the variables to compare.

    Args:
        variables: names of `_VARIABLES`, a mapping of new names to a column
            of the data and a column of the database, or `None`.

    Raises:
        KeyError: if a name is not one of `_VARIABLES`.
        ValueError: if a new variable does not have two columns.

    Returns:
        The variables by name, and whether they were named (so that a
            missing column is an error, rather than a reason to leave the
            variable out).

    """
    if variables is None:
        return dict(_VARIABLES), False
    if isinstance(variables, Mapping):
        chosen = {}
        for name, columns in variables.items():
            pair = utilities.listify(columns)
            if len(pair) != 2:
                message = (
                    f'the variable {name!r} needs a column of the data and a '
                    f'column of the database, not {columns!r}'
                )
                raise ValueError(message)
            chosen[str(name)] = _Variable(*pair, *pair)
        return chosen, True
    names = utilities.listify(variables)
    unknown = [name for name in names if name not in _VARIABLES]
    if unknown:
        message = (
            f'the variables {unknown} are unknown (the known ones are '
            f'{list(_VARIABLES)})'
        )
        raise KeyError(message)
    return {name: _VARIABLES[name] for name in names}, True


def _circuit_codes(table: pd.DataFrame) -> pd.Series:
    """Returns the database's code for the circuit of each appeal.

    Args:
        table: the database's table of appeals, with "circuit" (fjc-idb's
            label, such as "First Circuit", or the database's code).

    Returns:
        The code of each appeal (such as "1", or "0" for the D.C. Circuit).

    """
    codes = {label: code for code, label in fjc_idb.rules.circuits.items()}
    circuits = table['circuit'].astype('string').str.strip()
    return circuits.map(codes).fillna(circuits)


def _codes(values: pd.Series) -> pd.Series:
    """Returns a column of the database's codes as text.

    Args:
        values: codes, as numbers or text.

    Returns:
        The codes as text without spaces (and without ".0" after whole
            numbers), with missing values (and the database's "-8", for
            missing) kept missing.

    """
    texts = values.astype('string').str.strip().str.replace(
        r'\.0$', '', regex = True)
    return texts.mask(texts == '-8')


def _data_us_appellant(data: pd.DataFrame) -> pd.Series | None:
    """Returns whether the United States brought each appeal of the data.

    Args:
        data: the dockets.

    Returns:
        1 if a party is the United States and the appellant, and otherwise
            0, or `None` if `data` lacks the columns of the parties.

    """
    sides = ('party1', 'party2')
    needed = [
        f'{side}_{role}' for side in sides
        for role in ('united_states', 'appellant')]
    if any(column not in data.columns for column in needed):
        return None
    brought = pd.Series(False, index = data.index)
    for side in sides:
        brought |= (
            cases.column_as_flags(data, f'{side}_united_states')
            & cases.column_as_flags(data, f'{side}_appellant'))
    return brought.astype('float64')


def _flags(values: pd.Series) -> pd.Series:
    """Returns a column as 1s and 0s, with missing values kept missing.

    Args:
        values: true-or-false values, counts (which are true if more than 0),
            or text such as "true", "false", "1", or "0".

    Returns:
        The values as decimals: 1.0, 0.0, or NaN.

    """
    def flag(value: Any) -> float:
        """Returns one value as 1.0, 0.0, or NaN.

        Args:
            value: the value.

        Returns:
            1.0 if it is true (or more than 0), 0.0 if it is false (or 0),
                and NaN if it is missing or neither.

        """
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            return np.nan
        if isinstance(value, str):
            text = value.strip().lower()
            if text in _TRUE_TEXT:
                return 1.0
            if text in _FALSE_TEXT:
                return 0.0
            try:
                return float(float(text) > 0)
            except ValueError:
                return np.nan
        try:
            return float(float(value) > 0)
        except (TypeError, ValueError):
            return np.nan

    return pd.Series(
        [flag(value) for value in values.tolist()], index = values.index,
        dtype = 'float64')


def _idb_criminal(table: pd.DataFrame) -> pd.Series | None:
    """Returns whether each appeal of the database is a criminal appeal.

    Args:
        table: the database's table of appeals.

    Returns:
        1 if its "appeal_type" is one of fjc-idb's criminal appeal types, 0
            if it is another type, and missing if it is unknown, or `None`
            if `table` lacks "appeal_type".

    """
    if 'appeal_type' not in table.columns:
        return None
    codes = _codes(table['appeal_type'])
    criminal = codes.isin(fjc_idb.rules.criminal_apptypes).astype('float64')
    return criminal.mask(codes.isna())


def _idb_civil(table: pd.DataFrame) -> pd.Series | None:
    """Returns whether each appeal of the database is not a criminal appeal.

    Args:
        table: the database's table of appeals.

    Returns:
        The reverse of `_idb_criminal`, or `None` if `table` lacks
            "appeal_type".

    """
    criminal = _idb_criminal(table)
    return None if criminal is None else 1 - criminal


def _idb_reversal(table: pd.DataFrame) -> pd.Series | None:
    """Returns whether each appeal of the database was reversed or remanded.

    It is what courtpy's "outcome_reversal" means: the court of appeals
    reversed, vacated, or remanded (in whole or in part).

    Args:
        table: the database's table of appeals.

    Returns:
        1 if its "disposition" is reversed, affirmed and reversed in part, or
            remanded, 0 if it is another disposition on the merits, and
            missing if it was not decided on the merits, or `None` if
            `table` lacks "disposition".

    """
    if 'disposition' not in table.columns:
        return None
    codes = _codes(table['disposition'])
    rules = fjc_idb.rules.disposition_columns
    reversed_codes = [
        *rules['reversed_in_whole_or_part'], *rules['remanded_only']]
    reversal = codes.isin(reversed_codes).astype('float64')
    return reversal.mask(codes.isna())


def _kappa(counts: Mapping[tuple[int, int], int], compared: int) -> float:
    """Returns Cohen's kappa for two true-or-false columns.

    Args:
        counts: the number of rows with each pair of values (the data's and
            the database's).
        compared: the number of rows with both values.

    Returns:
        The agreement beyond what chance would give, from -1 to 1, or NaN if
            there are no rows or both columns have one value throughout.

    """
    if not compared:
        return np.nan
    observed = (counts[1, 1] + counts[0, 0]) / compared
    ours = (counts[1, 1] + counts[1, 0]) / compared
    theirs = (counts[1, 1] + counts[0, 1]) / compared
    expected = ours * theirs + (1 - ours) * (1 - theirs)
    if expected >= 1:
        return np.nan
    return (observed - expected) / (1 - expected)


def _load_appeals(
    merger: AddIdb,
    data: pd.DataFrame,
    source: Any,
    *,
    start_year: int | None,
    stop_year: int | None,
    district: bool | str,
    folder: pathlib.Path | str | None,
    download: bool | str,
    dates: Sequence[str] | str,
    reader: Mapping[str, Any] | None) -> tuple[pd.DataFrame, str]:
    """Returns the database's table of appeals for a table of cases.

    Args:
        merger: the merger whose clerk finds files and that reads `source`.
        data: the cases, whose dates set the years without a `source`.
        source: the database's table of appeals, the path of a file of it,
            or `None` to make it from the yearly files (see `appeals`).
        start_year: the first year to use, without a `source`, or `None` for
            the year of the earliest decision.
        stop_year: the last year to use, without a `source`, or `None` for
            the year after the latest decision.
        district: whether to add the district courts' records, without a
            `source`.
        folder: the folder of the yearly files, or `None` for the default.
        download: whether to download the yearly files that are missing.
        dates: the columns of `data` with the date of each decision.
        reader: parameters for reading `source`, or `None`.

    Returns:
        The table, and a description of where it came from.

    """
    if source is None:
        start, stop = _years(data, start_year, stop_year, dates)
        with_district = utilities.to_bool(district)
        table = appeals(
            start,
            stop,
            utilities.locate(folder, merger.clerk) if folder else None,
            district = with_district,
            download = utilities.to_bool(download))
        described = f'FJC IDB appeals, {start}-{stop}' + (
            ', with district records' if with_district else '')
        return table, described
    table = merger.read(source, **dict(reader or {}))
    described = (
        str(source) if isinstance(source, str | pathlib.Path)
        else type(source).__name__)
    return table, described


def _missing(
    table: pd.DataFrame,
    report: Sequence[str] | str | None,
    by: str) -> pd.DataFrame:
    """Returns how the appeals that the data has differ from those it lacks.

    Args:
        table: the database's appeals that the data could have, with
            "_in_data" (whether the data has each).
        report: names of `_VARIABLES` or columns of `table`, or `None` for
            all of `_VARIABLES`.
        by: "circuit", "district" (for "district_of_origin"), or another
            column of `table`, for the groups.

    Raises:
        KeyError: if `by` or a variable of `report` is not a column of
            `table`.

    Returns:
        One row for each variable in each group, "All" first (see
            `CompareWithIdb`).

    """
    column = _BY.get(by, by)
    if column not in table.columns:
        message = f'the database lacks the column {column!r} to group by'
        raise KeyError(message)
    named = report is not None
    names = list(_VARIABLES) if report is None else utilities.listify(report)
    flags: dict[str, pd.Series] = {}
    for name in names:
        variable = _VARIABLES.get(name)
        values = _values(table, variable.idb if variable else name)
        if values is None:
            if named:
                message = f'the database lacks the variable {name!r}'
                raise KeyError(message)
            continue
        flags[name] = values
    groups = table[column].astype('string').fillna(f'No {by}')
    order = _group_order(groups, by)
    frame = pd.DataFrame({
        'group': pd.concat([pd.Series('All', index = table.index), groups]),
        'in_data': pd.concat([table['_in_data']] * 2).astype(bool)})
    totals = frame.groupby('group', sort = False)['in_data'].agg(
        ['size', 'sum']).astype('int64')
    sizes = totals['size'].to_dict()
    helds = totals['sum'].to_dict()
    rows = []
    for name, values in flags.items():
        frame['value'] = pd.concat([values, values]).to_numpy()
        known = frame.dropna(subset = ['value'])
        sums = known.pivot_table(
            index = 'group', columns = 'in_data', values = 'value',
            aggfunc = ['size', 'sum'], fill_value = 0)
        for group in order:
            size, held = int(sizes.get(group, 0)), int(helds.get(group, 0))
            n_in, x_in, n_out, x_out = (
                _cell(sums, group, kind, side)
                for side in (True, False) for kind in ('size', 'sum'))
            share_in = x_in / n_in if n_in else np.nan
            share_out = x_out / n_out if n_out else np.nan
            rows.append({
                'group': group,
                'variable': name,
                'appeals': int(size),
                'in_data': int(held),
                'coverage': held / size if size else np.nan,
                'known_in_data': n_in,
                'known_missing': n_out,
                'share_in_data': share_in,
                'share_missing': share_out,
                'difference': share_in - share_out,
                'p_value': _p_value(x_in, n_in, x_out, n_out)})
    columns = [
        'group', 'variable', 'appeals', 'in_data', 'coverage',
        'known_in_data', 'known_missing', 'share_in_data', 'share_missing',
        'difference', 'p_value']
    return pd.DataFrame(rows, columns = columns)


def _cell(sums: pd.DataFrame, group: str, kind: str, side: bool) -> int:
    """Returns one count of a table of counts by group and side.

    Args:
        sums: the number ("size") and number true ("sum") of the known values
            of each group (rows) and side (whether the data has the appeal).
        group: the group.
        kind: "size" or "sum".
        side: whether the data has the appeals.

    Returns:
        The count, or 0 if the table lacks it.

    """
    if (kind, side) not in sums.columns:
        return 0
    return int(sums[(kind, side)].to_dict().get(group, 0))


def _group_order(groups: pd.Series, by: str) -> list[str]:
    """Returns the groups of the second table in the order to report them.

    Args:
        groups: the group of each appeal.
        by: what the groups are.

    Returns:
        "All", and then the circuits in their order (for "circuit") or the
            other groups in alphabetical order.

    """
    found = set(groups.dropna().unique())
    if by == 'circuit':
        labels = [
            label for code, label in fjc_idb.rules.circuits.items()
            if code != '-8']
        ordered = [label for label in labels if label in found]
        ordered += sorted(found - set(ordered))
    else:
        ordered = sorted(found)
    return ['All', *ordered]


def _p_value(x_in: int, n_in: int, x_out: int, n_out: int) -> float:
    """Returns the p value of a two-proportion z test.

    Args:
        x_in: the number true among the appeals that the data has.
        n_in: the number of those appeals with a known value.
        x_out: the number true among the appeals that the data lacks.
        n_out: the number of those appeals with a known value.

    Returns:
        The two-sided p value that the shares are the same, or NaN if a
            side has no appeals or every value is the same.

    """
    if not n_in or not n_out:
        return np.nan
    pooled = (x_in + x_out) / (n_in + n_out)
    error = math.sqrt(pooled * (1 - pooled) * (1 / n_in + 1 / n_out))
    if error == 0:
        return np.nan
    z = (x_in / n_in - x_out / n_out) / error
    return math.erfc(abs(z) / math.sqrt(2))


def _universe(
    data: pd.DataFrame,
    table: pd.DataFrame,
    merits_only: bool,
    courts: Sequence[str],
    dates: Sequence[str]) -> np.ndarray:
    """Returns which appeals of the database the data could have.

    Args:
        data: the dockets.
        table: the database's table of appeals.
        merits_only: whether to keep only the appeals decided on the merits
            (those with a "disposition").
        courts: the columns of `data` with the court of each case.
        dates: the columns of `data` with the date of each decision.

    Raises:
        KeyError: if `merits_only` is true and `table` lacks "disposition".

    Returns:
        Whether each appeal is in one of the data's circuits, was judged
            between the data's first and last decisions, and (with
            `merits_only`) was decided on the merits.

    """
    circuits = {code for code in _circuits(data, courts) if code is not None}
    keep = _circuit_codes(table).isin(circuits).fillna(False).to_numpy(
        bool, copy = True)
    decided = pd.Series(_decided(data, dates), dtype = 'datetime64[ns]')
    if decided.notna().any() and 'judgment_date' in table.columns:
        judged = pd.to_datetime(
            table['judgment_date'], errors = 'coerce', format = 'ISO8601')
        keep = keep & judged.between(
            decided.min(), decided.max()).to_numpy(bool)
    if merits_only:
        if 'disposition' not in table.columns:
            message = (
                'the table of appeals needs "disposition" to keep the '
                'appeals decided on the merits (or set "merits_only" to '
                'false)'
            )
            raise KeyError(message)
        keep = keep & _codes(table['disposition']).notna().to_numpy(bool)
    return keep


def _values(
    frame: pd.DataFrame,
    spec: str | Callable[[pd.DataFrame], pd.Series | None],
) -> pd.Series | None:
    """Returns one side of a variable as 1s and 0s.

    Args:
        frame: the data or the database's records.
        spec: a column of `frame`, or a function that makes the values.

    Returns:
        The values (see `_flags`), or `None` if `frame` lacks what they need.

    """
    if callable(spec):
        values = spec(frame)
        return None if values is None else _flags(values)
    if spec not in frame.columns:
        return None
    return _flags(frame[spec])


@dataclasses.dataclass(frozen = True)
class _Variable:
    """A true-or-false variable that the data and the database both have.

    Attributes:
        data: the column of the data, or a function that makes its values.
        idb: the column of the database, or a function that makes its values.
        data_text: what the data's values are, for the table.
        idb_text: what the database's values are, for the table.

    """

    data: str | Callable[[pd.DataFrame], pd.Series | None]
    idb: str | Callable[[pd.DataFrame], pd.Series | None]
    data_text: str
    idb_text: str


_BY: dict[str, str] = {'district': 'district_of_origin'}
_FALSE_TEXT: frozenset[str] = frozenset({'false', 'f', 'no', 'n'})
_TRUE_TEXT: frozenset[str] = frozenset({'true', 't', 'yes', 'y'})
_VARIABLES: dict[str, _Variable] = {
    'criminal': _Variable(
        'type_criminal', _idb_criminal, 'type_criminal',
        'appeal_type (criminal)'),
    'civil': _Variable(
        'type_civil', _idb_civil, 'type_civil', 'appeal_type (not criminal)'),
    'reversal': _Variable(
        'outcome_reversal', _idb_reversal, 'outcome_reversal',
        'disposition (reversed or remanded)'),
    'published': _Variable('published', 'published', 'published', 'published'),
    'dissent': _Variable('dissents', 'dissents', 'dissents', 'dissents'),
    'us_appellant': _Variable(
        _data_us_appellant, 'us_appellant',
        'party{1,2}_united_states & party{1,2}_appellant', 'us_appellant'),
    'pro_se_appellant': _Variable(
        'pro_se_appellant', 'pro_se_appellant', 'pro_se_appellant',
        'pro_se_appellant'),
    'prisoner_appeal': _Variable(
        'prisoner_appeal', 'prisoner_appeal', 'prisoner_appeal',
        'prisoner_appeal')}
