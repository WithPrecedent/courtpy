"""Identifies the judges in parsed cases and adds what is known about them.

The federal rules find the names of the judges on each case as the opinion
writes them, such as "LYNCH" and "R THOMPSON" (the "panel_judges", "authors",
"concurring", and "dissenting" columns, with "; " between the names). To study the judges, each name has to
be matched to a person. A `Roster` is a table of judges, with one row for each
court that a judge has served on, which finds the judge that a name refers to
from the court and year of the case.

`build_roster` makes that table with the fjc-biographies package
(https://github.com/WithPrecedent/fjc_biographies), from three files of the
Federal Judicial Center's Biographical Directory of Article III Federal
Judges (which `download` gets with it): the judges' service on each court,
their demographics, and their careers before the bench. The rules in its
"judges" rulebook code the careers, and another rulebook can be named, so
they can be changed without changing courtpy. fjc-biographies also adds
scores of the judges' ideology, which it gets from the judicial-common-space
package (https://github.com/WithPrecedent/judicial_common_space): each
appointment's Judicial Common Space score ("jcs") and the justices'
Martin-Quinn scores ("mq_first", "mq_last", "mq_mean", and "mq_terms"):

```python
import courtpy

roster = courtpy.judges.Roster.from_fjc(jcs = True, martin_quinn = True)
roster.save()
```

A saved roster is kept outside of projects (in "judges" in
`courtpy.utilities.data_folder()`), where the techniques look for it when no
roster is named. It is a CSV file, so judges and columns (such as a score of
each judge's ideology) can be added to it in a spreadsheet. Every column of
numbers or booleans that does not identify or date a judge's service is an
attribute of the judge, which the techniques use.

These techniques use a roster or the tables that it makes. They are added
to the `amos` library as soon as courtpy is imported, so they can be named
in settings. Cases and judges are different things, so the techniques are
built from the mergers and shapers of `amos`, which join tables whose rows
are not the same:

* `merge_biographies` (an `amos.Merger`) adds what the roster says about the
  judge that each row names, such as the author of each opinion.
* `code_panels` (an `amos.Munger`) adds the composition of each case's
  panel: the share of its judges who are women, the mean party of the
  presidents who appointed them, and so on. It makes a row for each judge on
  each case (with `lists_to_rows`), finds the judges (with
  `merge_biographies`), and adds summaries of each case's judges to the case
  (with `merge_summary`).
* `reshape_by_votes` (an `amos.Shaper`) makes a table with one row for each
  judge on each case, with the judge's attributes, those of the other judges
  on the panel, and how the judge voted.
* `reshape_by_panel` (an `amos.Shaper`) undoes `reshape_by_votes`: it makes
  the table of votes a table of cases again.
* `reshape_by_judge` (an `amos.Shaper`) makes a table with one row for each
  judge, which summarizes the judge's votes (with `group_rows`).
* `load_roster` and `download_biographies` (reference loaders, see
  `courtpy.loaders.ReferenceLoader`) start a study of the judges themselves
  with a saved roster or one made from the Federal Judicial Center's files.

Contents:
    CodePanels: adds the judges and the composition of each case's panel.
    DownloadBiographies: downloads the Federal Judicial Center's files about
        judges and loads the roster that they make.
    LoadRoster: loads the table of a roster of judges.
    MergeBiographies: adds what a roster says about the judge that each row
        names.
    ReshapeByJudge: makes a table with one row for each judge.
    ReshapeByPanel: makes a table of votes a table of cases again.
    ReshapeByVotes: makes a table with one row for each judge on each case.
    Roster: a table of judges that finds the judge a name refers to.
    build_roster: makes the table of a roster from the Federal Judicial
        Center's files with fjc-biographies.
    clean_name: returns a name the way that names are compared.
    download: downloads the Federal Judicial Center's files about judges
        with fjc-biographies.
    name_forms: returns the ways that an opinion may write a judge's name,
        grouped by how much of the name they give.
    vote_table: returns a table with one row for each judge on each case.
    _JUDGE_PREFIXES: the starts of the names of the columns that
        `vote_table` makes for each judge, which `ReshapeByPanel` removes.
    _NID: the column of a table of votes with each judge's number, which
        labels the table that `ReshapeByJudge` makes.

"""

from __future__ import annotations

import dataclasses
import pathlib
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import amos
import fjc_biographies
import numpy as np
import pandas as pd

from . import cases, coders, loaders, options, rules, utilities

# Judge Johnson of the Fifth Circuit signed opinions as "Sam D. Johnson", and
# Judge King of the Fifth Circuit sat as Carolyn Dineen Randall until 1988.
_ALIASES: dict[int, str] = {
    1382851: 'Sam D. Johnson',
    1386716: 'Carolyn Dineen Randall'}
_APPELLATE: frozenset[str] = frozenset({
    'U.S. Court of Appeals', 'Supreme Court'})
# The categories of the Federal Judicial Center's files that a roster is made
# from, which are the names of the parameters of `build_roster` that take
# them.
_CATEGORIES: tuple[str, ...] = ('service', 'demographics', 'career')
# Names of the columns that the techniques add to the tables that they make
# on the way to their results, which no table of cases or roster has.
_CASE: str = '__case__'
_FOUND: str = '__found__'
_NAME: str = '__name__'
_OTHER: str = '__other__'
_PLACE: str = '__place__'
_SEAT: str = '__seat__'
_DISTRICT_COURT: str = 'U.S. District Court'
_IDENTIFIERS: frozenset[str] = frozenset({
    'nid', 'sequence', 'court_num', 'circuit_num', 'start_year', 'end_year',
    'senior_year', 'birth_year'})
# The groups of the forms of a judge's name (see `name_forms`), in the order
# that `Roster.match` tries them: from the most of the name to the least.
_LEVELS: tuple[str, ...] = ('full', 'initials', 'last')
# The curly apostrophe (U+2019) is added with `chr` so that the source file
# has only plain characters.
_NAME_PUNCTUATION: re.Pattern[str] = re.compile(
    r"[.,\[\]'" + chr(0x2019) + ']')
_NEEDED: tuple[str, ...] = (
    'nid', 'judge', 'last_name', 'first_name', 'court_num', 'circuit_num',
    'start_year', 'end_year')
# The other columns of text that fjc-biographies puts in a roster: the career
# that the rules searched, the ways of writing each judge's name, and the
# dates of each appointment. A saved roster would read such a column that is
# blank in every row as numbers, which would make it an attribute.
_OTHER_TEXT: re.Pattern[str] = re.compile(r'career|name_.+|.+_date')
# The start of the names of the columns in which fjc-biographies writes each
# judge's full name in different ways.
_PERMUTATIONS: str = 'name_'
_RELATIVE: tuple[str, ...] = ('age', 'senior', 'designated', 'district_judge')
_ROLES: dict[str, str] = {
    'authors': 'judge_author',
    'concurring': 'judge_concurred',
    'dissenting': 'judge_dissented'}
# The column of a table of votes with the Federal Judicial Center's number
# for each judge, which labels a table of judges.
_NID: str = 'judge_nid'
# The starts of the names of the columns that `vote_table` makes for each
# judge (with "judge" itself), which a table of cases does not have.
_JUDGE_PREFIXES: tuple[str, ...] = ('judge_', 'colleagues_', 'vote_')
_ROSTER_FILE: str = 'roster.csv'
_TEXT: tuple[str, ...] = (
    'judge', 'last_name', 'first_name', 'middle_name', 'suffix', 'aliases',
    'court', 'court_type', 'president')


@dataclasses.dataclass
class Roster:
    """A table of judges that finds the judge a name in an opinion refers to.

    Each row of the table is a judge's service on one court, so a judge who
    was promoted from a district court to a court of appeals has two rows,
    with the president who made each appointment. Only judges who were
    serving in the year of the case (or had left their court no more than
    `grace` years before it) are considered. A name is matched by how much of
    a judge's name it gives, from the most to the least (see `name_forms`):

    1. a full name: one of the ways that fjc-biographies writes the judge's
       name (the "name_..." columns, such as "Sandra Lea Lynch", "Sandra L.
       Lynch", "Sandra Lynch", and each with any suffix), or one of the
       judge's "aliases",
    2. or else initials and the last name ("S. Lynch", "S. L. Lynch", "S.L.
       Lynch", or "S. Lea Lynch"), or the middle and last names ("Lea Lynch",
       for a judge who goes by a middle name),
    3. or else the last name alone, which is how opinions usually name
       judges.

    The first of them that fits any judge who was serving is used. Many
    judges share a name, especially a last name, so the judges whose names
    fit are then narrowed by the court of the case:

    1. to a judge of the case's court,
    2. or else to a judge of a district court in the case's circuit, who may
       sit on its court of appeals by designation,
    3. or else to a judge of any other court, such as a court of appeals or
       district court of another circuit, who may sit by designation.

    If more than one judge fits at the first step that any judge fits, the
    name is not matched, since there is no telling which judge was meant.
    Nor is a name on a case of a court that has no judges in the table (such
    as a bankruptcy appellate panel, whose judges are not in the Federal
    Judicial Center's files), since a judge of another court who shares the
    name would be a guess.

    Args:
        data: the table. It needs the columns "nid" (a number that identifies
            each judge), "judge" (the judge's name, as it is reported),
            "last_name", "first_name", "court_num" and "circuit_num" (the
            numbers that the federal rules give the judge's court and its
            circuit), and "start_year" and "end_year" (of the judge's service
            on the court). "middle_name", "suffix", the "name_..." columns
            that fjc-biographies makes, "aliases" (other names that opinions
            use for the judge, as "First Middle Last", separated by
            semicolons), "senior_year", "birth_year", and "court_type" are
            used if they are there.
        grace: years after a judge's service on a court ended in which an
            opinion may still name the judge. Defaults to
            `options._JUDGE_GRACE` (as it is when the roster is made).

    """

    data: pd.DataFrame
    grace: int = dataclasses.field(
        default_factory = lambda: options._JUDGE_GRACE)
    _described: dict[
        tuple[int, int | None, int | None], dict[str, float | None]] = (
            dataclasses.field(default_factory = dict, init = False, repr = False))
    _forms: dict[str, dict[str, list[int]]] = dataclasses.field(
        default_factory = dict, init = False, repr = False)
    _found: dict[tuple[str, int | None, int | None], int | None] = (
        dataclasses.field(default_factory = dict, init = False, repr = False))
    _numbers: dict[str, list[int | None]] = dataclasses.field(
        default_factory = dict, init = False, repr = False)
    _text: dict[str, list[str]] = dataclasses.field(
        default_factory = dict, init = False, repr = False)
    _values: dict[str, list[float | None]] = dataclasses.field(
        default_factory = dict, init = False, repr = False)

    """ Initialization Methods """

    def __post_init__(self) -> None:
        """Checks the table and indexes the names and numbers of its judges.

        Raises:
            KeyError: if the table lacks a column that every roster needs.

        """
        _require(self.data, _NEEDED, 'a roster of judges')
        self.data = cases.tidy(self.data.reset_index(drop = True))
        for column in _TEXT:
            self._text[column] = (
                self.data[column].fillna('').astype(str).tolist()
                if column in self.data.columns else [''] * len(self.data))
        permutations = [
            self.data[column].tolist() for column in self.data.columns
            if str(column).startswith(_PERMUTATIONS)]
        self._forms = {level: {} for level in _LEVELS}
        people = zip(
            self._text['first_name'], self._text['middle_name'],
            self._text['last_name'], self._text['suffix'],
            self._text['aliases'], strict = True)
        for row, (first, middle, last, suffix, aliases) in enumerate(people):
            levels = name_forms(first, middle, last, suffix)
            # The ways that fjc-biographies writes a name are full names.
            levels['full'].extend(
                clean_name(values[row]) for values in permutations
                if isinstance(values[row], str))
            for alias in aliases.split(';'):
                parts = alias.split()
                if len(parts) > 1:
                    found = name_forms(
                        parts[0], ' '.join(parts[1:-1]), parts[-1])
                    for level, forms in found.items():
                        levels[level].extend(forms)
            # A form is indexed only at the first level that has it, so a
            # judge whose first name is an initial ("J. Smith") is matched by
            # it as a full name.
            seen: set[str] = set()
            for level in _LEVELS:
                for form in levels[level]:
                    if form and form not in seen:
                        seen.add(form)
                        self._forms[level].setdefault(form, []).append(row)
        for column in sorted(_IDENTIFIERS):
            self._numbers[column] = (
                [_whole(value) for value in self.data[column]]
                if column in self.data.columns else [None] * len(self.data))
        for column in self.attributes:
            self._values[column] = [
                None if pd.isna(value) else float(value)
                for value in self.data[column]]

    """ Class Methods """

    @classmethod
    def create(
        cls,
        source: Roster | pd.DataFrame | pathlib.Path | str | None = None) -> (
            Roster):
        """Returns a roster made from `source`.

        Args:
            source: a roster, the table of one, or the path of a saved one.
                Defaults to `None`, in which case the roster saved in
                "judges" in `utilities.data_folder()` is loaded.

        Returns:
            The roster.

        """
        if isinstance(source, Roster):
            return source
        if isinstance(source, pd.DataFrame):
            return cls(source)
        return cls.load(source)

    @classmethod
    def from_fjc(
        cls,
        folder: pathlib.Path | str | None = None,
        *,
        update: bool = False,
        scores: pd.DataFrame | pathlib.Path | str | None = None,
        jcs: bool = False,
        martin_quinn: bool | pathlib.Path | str = False,
        rulebook: fjc_biographies.Rulebook | pathlib.Path | str = 'judges') -> (
            Roster):
        """Returns a roster made from the Federal Judicial Center's files.

        Any of the files that `folder` lacks is downloaded to it first (see
        `download`). The files that the scores of `jcs` and `martin_quinn`
        are computed from (Voteview's NOMINATE scores, the dates of
        senators' service, and the justices' Martin-Quinn scores) are
        downloaded by fjc-biographies and judicial-common-space into
        `utilities.data_folder()`, where `courtpy.politics` keeps the same
        files.

        Args:
            folder: the folder with the files, whose "raw" folder they are
                kept in. Defaults to `None`, in which case "judges" in
                `utilities.data_folder()` is used.
            update: whether to download the files again even if they are
                there, to get the judges and changes since they were
                downloaded. Defaults to `False`.
            scores: scores of the judges to add (see `build_roster`). Defaults
                to `None`.
            jcs: whether to add each appointment's Judicial Common Space
                score as "jcs" (see `fjc_biographies.add_jcs`): the NOMINATE
                score of the judge's home-state senators of the president's
                party, or else of the president, and for a justice, the
                Martin-Quinn score of the appointment's first term on the
                same scale. Defaults to `False`.
            martin_quinn: whether to add the Martin-Quinn scores of each
                appointment to the Supreme Court as "mq_first", "mq_last",
                "mq_mean", and "mq_terms" (see
                `fjc_biographies.add_martin_quinn`), or the path of the file
                of the justices' scores ("justices.csv" from
                https://mqscores.wustl.edu/measures.php), which is used for
                `jcs` too. The Martin-Quinn website sometimes refuses
                automated requests, so the file may have to be saved in a
                browser. Defaults to `False`.
            rulebook: the rules that code the judges' careers (see
                `build_roster`). Defaults to "judges".

        Returns:
            The roster.

        """
        folder = pathlib.Path(folder).expanduser() if folder else _folder()
        files = download(folder, overwrite = update)
        table = build_roster(
            files['service'], files['demographics'], files['career'],
            scores = scores, rulebook = rulebook)
        named = None if isinstance(martin_quinn, bool) else martin_quinn
        if jcs:
            table = fjc_biographies.add_jcs(
                table, folder, scores_folder = utilities.data_folder(),
                martin_quinn = named, update = update)
        if martin_quinn is not False:
            table = fjc_biographies.add_martin_quinn(
                table, folder, scores_folder = utilities.data_folder(),
                martin_quinn = named, update = update)
        return cls(table)

    @classmethod
    def load(cls, path: pathlib.Path | str | None = None) -> Roster:
        """Loads a roster saved by `save` (or made in a spreadsheet).

        Args:
            path: path of the CSV file. Defaults to `None`, in which case it
                is "roster.csv" in "judges" in `utilities.data_folder()`.

        Raises:
            FileNotFoundError: if there is no file at `path`.

        Returns:
            The roster.

        """
        found = (
            pathlib.Path(path).expanduser() if path
            else _folder() / _ROSTER_FILE)
        if not found.is_file():
            message = (
                f'there is no roster of judges at {found}: make one with '
                f'`courtpy.judges.Roster.from_fjc()` and save it with its '
                f'`save` method'
            )
            raise FileNotFoundError(message)
        columns = pd.read_csv(found, encoding = 'utf-8', nrows = 0).columns
        return cls(pd.read_csv(
            found, encoding = 'utf-8',
            dtype = {column: str for column in columns if _is_text(column)}))

    """ Properties """

    @property
    def attributes(self) -> list[str]:
        """Returns the names of the columns that describe the judges.

        Returns:
            The columns of numbers or booleans that do not identify or date a
                judge's service (such as "party" and "woman"), in order.

        """
        return [
            column for column in self.data.columns
            if column not in _IDENTIFIERS and not _is_text(column) and (
                pd.api.types.is_bool_dtype(self.data[column].dtype)
                or pd.api.types.is_numeric_dtype(self.data[column].dtype))]

    @property
    def described(self) -> list[str]:
        """Returns the names of everything that `describe` reports.

        Returns:
            `attributes`, followed by the attributes that depend on the case
                ("age", "senior", "designated", and "district_judge").

        """
        return [*self.attributes, *_RELATIVE]

    """ Public Methods """

    def describe(
        self,
        row: int,
        court_num: int | None = None,
        year: int | None = None) -> dict[str, float | None]:
        """Returns what is known about a judge on a case.

        Args:
            row: the judge's row of the table (as `match` returns it).
            court_num: the number of the case's court. Defaults to `None`.
            year: the year of the case. Defaults to `None`.

        Returns:
            Each of `described`, as a number (1 and 0 for true and false) or
                `None` if it is not known. "age" is the judge's age at the
                end of `year`, "senior" is whether the judge had taken senior
                status by `year`, "designated" is whether the judge's court
                is not the case's court (so the judge sat by designation),
                and "district_judge" is whether it is a district court. The
                same `dict` is returned each time for a judge, court, and
                year, so copy it before changing it.

        """
        key = (row, court_num, year)
        if key in self._described:
            return self._described[key]
        known = {name: values[row] for name, values in self._values.items()}
        birth = self._numbers['birth_year'][row]
        senior = self._numbers['senior_year'][row]
        known['age'] = (
            None if year is None or birth is None else float(year - birth))
        known['senior'] = (
            None if year is None or 'senior_year' not in self.data.columns
            else float(senior is not None and senior <= year))
        known['designated'] = (
            None if court_num is None
            else float(self._numbers['court_num'][row] != court_num))
        known['district_judge'] = (
            float(self._text['court_type'][row] == _DISTRICT_COURT)
            if 'court_type' in self.data.columns else None)
        self._described[key] = known
        return known

    def identify(
        self,
        names: Iterable[str],
        court_num: int | None = None,
        year: int | None = None) -> list[int]:
        """Returns the judges that the names on a case refer to.

        Args:
            names: the names, as the opinion writes them.
            court_num: the number of the case's court. Defaults to `None`.
            year: the year of the case. Defaults to `None`.

        Returns:
            The rows of the judges who were found, in the order of `names`,
                with each judge once.

        """
        rows: list[int] = []
        judges: set[int | None] = set()
        for name in names:
            row = self.match(name, court_num, year)
            if row is not None and self._numbers['nid'][row] not in judges:
                rows.append(row)
                judges.add(self._numbers['nid'][row])
        return rows

    def match(
        self,
        name: str,
        court_num: int | None = None,
        year: int | None = None) -> int | None:
        """Returns the judge that a name on a case refers to.

        Args:
            name: the name, as the opinion writes it (such as "LYNCH",
                "R. Thompson", or "Sandra L. Lynch").
            court_num: the number of the case's court, which is needed to
                prefer its own judges and those of its circuit. Defaults to
                `None`, in which case judges of every court are considered.
            year: the year of the case. Defaults to `None`, in which case
                judges of every year are considered.

        Returns:
            The row of the judge's service in the table (the most recent, if
                more than one fits), or `None` if the name is not matched
                (see the class's documentation).

        """
        key = (clean_name(name), court_num, year)
        if key not in self._found:
            self._found[key] = self._match(*key)
        return self._found[key]

    def names(self, rows: Iterable[int]) -> list[str]:
        """Returns the names of judges as the roster reports them.

        Args:
            rows: rows of the table (as `identify` returns them).

        Returns:
            The "judge" of each row, such as "Lynch, Sandra Lea".

        """
        return [self._text['judge'][row] for row in rows]

    def nids(self, rows: Iterable[int]) -> list[int]:
        """Returns the numbers that identify judges.

        Args:
            rows: rows of the table (as `identify` returns them).

        Returns:
            The "nid" of each row.

        """
        return [int(self._numbers['nid'][row] or 0) for row in rows]

    def save(self, path: pathlib.Path | str | None = None) -> pathlib.Path:
        """Saves the table as a CSV file, which a spreadsheet can change.

        Args:
            path: path to save it to. Its folder is created if needed.
                Defaults to `None`, in which case it is "roster.csv" in
                "judges" in `utilities.data_folder()`, where `load` and the
                techniques look for it.

        Returns:
            The path the table was saved to.

        """
        saved = (
            pathlib.Path(path).expanduser() if path
            else _folder() / _ROSTER_FILE)
        saved.parent.mkdir(parents = True, exist_ok = True)
        self.data.to_csv(saved, index = False, encoding = 'utf-8')
        return saved

    """ Private Methods """

    def _match(
        self,
        name: str,
        court_num: int | None,
        year: int | None) -> int | None:
        """Returns the judge that a cleaned name on a case refers to.

        Args:
            name: the name, as `clean_name` returns it.
            court_num: the number of the case's court, or `None`.
            year: the year of the case, or `None`.

        Returns:
            The row of the judge's service, or `None`.

        """
        courts = self._numbers['court_num']
        if court_num is not None and court_num not in courts:
            return None
        for level in _LEVELS:
            rows = [
                row for row in self._forms[level].get(name, ())
                if year is None or self._serving(row, year)]
            if rows:
                return self._choose(rows, court_num)
        return None

    def _choose(self, rows: list[int], court_num: int | None) -> int | None:
        """Returns the judge that a name refers to among judges it fits.

        Args:
            rows: the rows of the judges whose names fit, who were serving.
            court_num: the number of the case's court, or `None`.

        Returns:
            The row of the judge's service at the first of the steps (the
                case's court, a district court of its circuit, and any
                court) at which any judge fits, the most recent if more than
                one of the judge's rows fits, or `None` if more than one
                judge fits there.

        """
        courts = self._numbers['court_num']
        circuits = self._numbers['circuit_num']
        tiers = (
            [r for r in rows if court_num is not None
             and courts[r] == court_num],
            [r for r in rows if court_num is not None
             and circuits[r] == court_num],
            rows)
        for tier in tiers:
            judges = {self._numbers['nid'][row] for row in tier}
            if len(judges) > 1:
                return None
            if judges:
                starts = self._numbers['start_year']
                return max(tier, key = lambda row: starts[row] or 0)
        return None

    def _serving(self, row: int, year: int) -> bool:
        """Returns whether an opinion of a year may name a judge.

        Args:
            row: a row of the table.
            year: the year of a case.

        Returns:
            Whether the service of `row` had begun by `year` and had not
                ended more than `grace` years before it.

        """
        start = self._numbers['start_year'][row]
        end = self._numbers['end_year'][row]
        return (
            start is not None and start <= year
            and (end is None or year <= end + self.grace))


@dataclasses.dataclass
class CodePanels(amos.Munger):
    """Adds the judges and the composition of each case's panel.

    Each name in "panel_judges" is matched to a judge in a roster (see
    `Roster`) with the case's court and year. The judges who are found are
    listed in "panel_names" (as the roster names them, such as "Lynch, Sandra
    Lea"), and "panel_found" is how many there are, which can be compared
    with "panel_size". Each of them also has columns of its own, numbered by
    the place of the judge's name in "panel_judges": "judge1" (the judge's
    name as the Federal Judicial Center reports it) and "judge1_nid" (the
    center's number for the judge), "judge2" and "judge2_nid", and so on, for
    as many names as the longest panel lists. A name that is not matched
    leaves its place missing, so the judges after it keep theirs, and a case
    with fewer names has missing values in the rest. For each attribute in the roster, "panel_{attribute}"
    is its mean among those judges: "panel_woman" is the share of the judges
    who are women, and "panel_party" is the mean party of the presidents who
    appointed them (-1 for a Democrat and 1 for a Republican). So are
    "panel_age", "panel_senior", "panel_designated", and
    "panel_district_judge" (see `Roster.describe`). A mean is missing if no
    judge was found (or none has the attribute).

    If the cases have "authors", "concurring", or "dissenting" columns, the
    judges they name are added as "author_name" (the first author found),
    "concurring_names", and "dissenting_names".

    The judges of each case are found as `merge_biographies` finds them (see
    `MergeBiographies`), in a table with a row for each judge on each case, and
    the case gets summaries of its rows (as the `merge_summary` technique of
    `amos` adds them).

    Needs "panel_judges", "court_num", and "year".

    """

    def munge(
        self,
        data: pd.DataFrame,
        roster: Roster | pd.DataFrame | pathlib.Path | str | None = None,
        **kwargs: Any) -> pd.DataFrame:
        """Adds the judges and the composition of each panel.

        Args:
            data: the parsed cases.
            roster: a roster, the table of one, or the path of a saved one.
                Defaults to `None`, in which case the roster saved in
                "judges" in `utilities.data_folder()` is used.
            **kwargs: not used.

        Returns:
            The cases, with the new columns.

        """
        coders._require(data, ['panel_judges', 'court_num', 'year'], self.name)
        judges = Roster.create(roster)
        described = judges.described
        seated = _named(
            data, 'panel_judges', judges, ['judge', *described],
            unmatched = True)
        panel = seated[seated['nid'].notna()].astype({'nid': 'int64'})
        panels = _summarize(
            panel,
            len(data),
            {'judge': 'list', **dict.fromkeys(described, 'mean')},
            count = _FOUND)
        names = {
            column: _summarize(
                _named(data, column, judges, ['judge']),
                len(data),
                {'judge': 'list'})['judge'].tolist()
            for column in _ROLES if column in data.columns}
        data['panel_names'] = pd.Series(
            panels['judge'].tolist(), index = data.index, dtype = object)
        data['panel_found'] = panels[_FOUND].to_numpy()
        for column, values in _numbered(seated, len(data)).items():
            data[column] = pd.Series(values.array, index = data.index)
        if 'authors' in names:
            data['author_name'] = pd.Series(
                [found[0] if found else None for found in names['authors']],
                index = data.index, dtype = object)
        for column in ('concurring', 'dissenting'):
            if column in names:
                data[f'{column}_names'] = pd.Series(
                    names[column], index = data.index, dtype = object)
        for name in described:
            data[f'panel_{name}'] = panels[name].to_numpy(dtype = 'float64')
        return data


@dataclasses.dataclass
class ReshapeByVotes(amos.Shaper):
    """Makes a table with one row for each judge on each case.

    The table is for studying how judges vote, rather than what courts
    decide. See `vote_table` for its columns. It replaces the table of cases,
    so it should come after the techniques that code the cases (such as
    `code_outcome`) and, like every shaper of `amos`, before the data is
    split. Its "case_id" column can be the "groups" of a study, which keeps
    the judges of a case together.

    Like every shaper, it takes "label", "task", and "groups", which name the
    label and groups of the table of votes (such as "vote_reversal" and
    "case_id"). Without them, the dataset keeps the label and groups that it
    has.

    """

    def shape(
        self,
        data: pd.DataFrame,
        roster: Roster | pd.DataFrame | pathlib.Path | str | None = None,
        outcomes: Sequence[str] | str | None = None,
        **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each judge on each case.

        Args:
            data: the parsed cases.
            roster: a roster, the table of one, or the path of a saved one.
                Defaults to `None`, in which case the roster saved in
                "judges" in `utilities.data_folder()` is used.
            outcomes: names of the columns with the outcomes of the cases,
                for which each judge's vote is added. Defaults to `None`, in
                which case they are the columns whose names start with
                "outcome_".
            **kwargs: not used.

        Returns:
            The table of judges' votes.

        """
        return vote_table(
            data, roster, outcomes = utilities.listify(outcomes) or None)


@dataclasses.dataclass
class ReshapeByPanel(amos.Shaper):
    """Makes a table of votes a table of cases again.

    It undoes `reshape_by_votes`: the rows of each case become one row,
    labeled by "case_id" as a table of parsed cases is, with the case's
    columns in their order. The columns that `reshape_by_votes` makes for
    each judge are removed: "judge", and those whose names begin with
    "judge_", "colleagues_", or "vote_" (such as "judge_party",
    "colleagues_party", "judge_dissented", and "vote_reversal"). Every other
    column is the case's, so each case keeps the value of its first row. A
    case with no judge who was found in the roster has no rows in the table
    of votes, so it is not in the table of cases either. To summarize the
    judges of each case instead, use `code_panels` on the cases, or
    `group_rows` on the votes.

    Like every shaper, it takes "label", "task", and "groups". Without them,
    a label of votes (such as "vote_reversal") becomes the outcome that it
    was made from ("outcome_reversal"), and the groups are those of the
    votes other than "case_id" and the judges' columns.

    """

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        label: str | None = None,
        groups: Sequence[str] | str | None = None,
        **kwargs: Any) -> amos.Dataset:
        """Makes the table of votes of `item` a table of cases.

        Args:
            item: the dataset of votes.
            label: name of the label of the cases. Defaults to `None`, in
                which case it is the outcome that the label of the votes was
                made from, if it was made from one, and otherwise the label
                of `item`.
            groups: names of the groups of the cases. Defaults to `None`, in
                which case they are the groups of `item` that are columns of
                the cases.
            **kwargs: "task", and parameters for `shape`.

        Returns:
            The dataset of cases.

        """
        if label is None and item.label is not None:
            outcome = 'outcome_' + str(item.label).removeprefix('vote_')
            if (str(item.label).startswith('vote_')
                    and outcome in item.data.columns):
                label = outcome
        if groups is None:
            groups = [
                group for group in item.groups
                if group != 'case_id' and not _is_judge_column(group)]
        return super().apply(item, label = label, groups = groups, **kwargs)

    def shape(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each case.

        Args:
            data: the table of votes (see `vote_table`).
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks "case_id".

        Returns:
            The table of cases, labeled by "case_id".

        """
        _require(data, ['case_id'], repr(self.name))
        judged = [c for c in data.columns if _is_judge_column(c)]
        table = data.drop(columns = judged).drop_duplicates(subset = 'case_id')
        return table.set_index('case_id')


@dataclasses.dataclass
class ReshapeByJudge(amos.Shaper):
    """Makes a table with one row for each judge.

    The rows of each judge in a table of votes (see `vote_table`) become one
    row, labeled by "judge_nid" (the Federal Judicial Center's number for the
    judge), with "judge" (the judge's name), "cases" (the number of the
    judge's votes), and summaries of the other columns, as `group_rows`
    takes them. A column that has one value among each judge's votes keeps
    it (such as "judge_woman", or "court" for judges of one court). Of the
    other columns of numbers and booleans, the mean is taken, which is a
    share for a boolean: "vote_reversal" is the share of the judge's votes
    to reverse, "judge_dissented" the share of the judge's cases in which
    the judge dissented, and "judge_age" the judge's mean age when deciding
    them. Columns of text or lists that differ among a judge's votes (such
    as "case_id" and the cases' names) are left out, and so are ids (columns
    whose names end with "_id"), unless "how" names a summary for them.

    If the data is a table of cases (it has no "judge_nid" column), the
    table of votes is made first, as `reshape_by_votes` makes it, with
    "roster" and "outcomes".

    Like every shaper, it takes "label", "task", and "groups". Without
    "groups", the table has none, since the groups of votes (such as
    "case_id") are not columns of it. Without "task", the task is inferred
    from the label, since a label that was a vote is now a share.

    """

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        task: str | None = None,
        groups: Sequence[str] | str | None = None,
        **kwargs: Any) -> amos.Dataset:
        """Makes the table of `item` a table of judges.

        Args:
            item: the dataset of votes or of cases.
            task: "classify" or "regress". Defaults to `None`, in which case
                it is inferred from the label (see `amos.Dataset.infer_task`).
            groups: names of the groups of the judges. Defaults to `None`,
                for none.
            **kwargs: "label", and parameters for `shape`.

        Returns:
            The dataset of judges.

        """
        dataset = super().apply(
            item, task = task, groups = [] if groups is None else groups,
            **kwargs)
        if task is None and dataset.label is not None:
            dataset.task = dataset.infer_task()
        return dataset

    def shape(
        self,
        data: pd.DataFrame,
        roster: Roster | pd.DataFrame | pathlib.Path | str | None = None,
        outcomes: Sequence[str] | str | None = None,
        how: Mapping[str, Any] | None = None,
        count: str | None = 'cases',
        **kwargs: Any) -> pd.DataFrame:
        """Returns a table with one row for each judge.

        Args:
            data: a table of votes (see `vote_table`), or the parsed cases.
            roster: for a table of cases, a roster, the table of one, or the
                path of a saved one. Defaults to `None`, in which case the
                roster saved in "judges" in `utilities.data_folder()` is
                used.
            outcomes: for a table of cases, names of the columns with the
                outcomes of the cases, for which each judge's vote is added.
                Defaults to `None`, in which case they are the columns whose
                names start with "outcome_".
            how: the summaries of columns, by their names, which take the
                place of the usual ones (see `group_rows`), such as
                {"court": "list"}. Defaults to `None`.
            count: name of the column with the number of each judge's votes,
                or `None` for no such column. Defaults to "cases".
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks a column that is needed or named.

        Returns:
            The table of judges, labeled by "judge_nid".

        """
        votes = data if _NID in data.columns else vote_table(
            data, roster, outcomes = utilities.listify(outcomes) or None)
        votes = votes.reset_index(drop = True)
        chosen = dict(how or {})
        summarized = [
            column for column in votes.columns
            if column != _NID and (
                column in chosen or column == 'judge'
                or _is_number(votes[column], column))]
        others = [
            column for column in votes.columns
            if column != _NID and column not in summarized]
        constant = _constant(votes, _NID, others)
        kept = [
            column for column in votes.columns
            if column in summarized or column in constant]
        table = amos.shapers.GroupRows().shape(
            votes[[_NID, *kept]], by = _NID, how = chosen or None,
            count = count)
        first = [c for c in ('judge', count) if c is not None and c in table]
        ordered = [_NID, *first, *[
            c for c in table.columns if c != _NID and c not in first]]
        return table[ordered].set_index(_NID)


@dataclasses.dataclass
class MergeBiographies(amos.Merger):
    """Adds what a roster says about the judge that each row names.

    Each row of the data names one judge, as an opinion writes the name
    (such as "LYNCH"). The name is matched to a judge in a roster (see
    `Roster`) with the court and year of the row's case, and the columns of
    the judge's row of the roster are added, with a prefix before their
    names. So a table with a row for each judge on each case gets
    "judge_party", "judge_woman", and so on. A table of cases gets what is
    known about the author of each opinion with "name" set to "author" and
    "prefix" to "author_". A row whose name is not matched gets missing
    values.

    Like every merger of `amos`, it takes these parameters, never adds,
    removes, or reorders rows, and records how many rows it matched in the
    dataset's history:

    | Parameter | Meaning |
    | --- | --- |
    | `source` | The roster: the path of a saved one (looked for in the current folder and then in the clerk's input folder), a roster, or the table of one. Without it, the roster saved in "judges" in `utilities.data_folder()` is used. |
    | `columns` | The columns to add. By default, they are the roster's attributes (see `Roster.attributes`) and those that depend on the case: "age", "senior", "designated", and "district_judge" (see `Roster.describe`). All of them are added as numbers (1 and 0 for true and false). Any other column of the roster can be named too, such as "judge" (the judge's name, as the roster reports it), "nid", or "president". |
    | `prefix` | Text to put before the names of the added columns. It is "judge_" unless another is set. |
    | `indicator` | The name of a column to make that says whether each row's judge was found. |
    | `name`, `court`, `year` | The columns of the data with the judge's name and the number of the court and the year of the row's case. They are "judge", "court_num", and "year" unless others are set. |

    """

    """ Public Methods """

    def apply(
        self,
        item: amos.Dataset,
        *,
        source: Any = None,
        columns: Sequence[str] | str | None = None,
        prefix: str | None = 'judge_',
        indicator: str | None = None,
        name: str = 'judge',
        court: str = 'court_num',
        year: str = 'year',
        **kwargs: Any) -> amos.Dataset:
        """Adds the columns of the judge that each row of `item` names.

        Args:
            item: the dataset to add columns to.
            source: the roster: a roster, the table of one, or the path of a
                saved one. Defaults to `None`, in which case the roster saved
                in "judges" in `utilities.data_folder()` is used.
            columns: the columns to add: attributes of the judge (see
                `Roster.described`) or other columns of the roster. Defaults
                to `None`, in which case they are every attribute.
            prefix: text to put before the names of the added columns.
                Defaults to "judge_".
            indicator: name of a boolean column to make that says whether
                each row's judge was found. Defaults to `None`, which makes
                no such column.
            name: the column of `item` with the judge's name, as an opinion
                writes it. Defaults to "judge".
            court: the column of `item` with the number of the court of the
                row's case. Defaults to "court_num".
            year: the column of `item` with the year of the row's case.
                Defaults to "year".
            **kwargs: not used.

        Raises:
            KeyError: if `item` lacks one of the columns `name`, `court`, and
                `year`, or one of `columns` is not in the roster.
            ValueError: if an added column would have the name of a column
                of the data.

        Returns:
            The dataset with the added columns. Its rows and index are not
                changed.

        """
        if source is None:
            source = _folder() / _ROSTER_FILE
        roster = (
            Roster.create(utilities.locate(source, self.clerk))
            if isinstance(source, str | pathlib.Path)
            else Roster.create(source))
        data = item.data
        rows = np.asarray(
            self.match(data, roster, name = name, court = court, year = year),
            dtype = 'int64')
        chosen = (
            roster.described if columns is None
            else utilities.listify(columns))
        missing = [
            c for c in chosen
            if c not in roster.described and c not in roster.data.columns]
        if missing:
            message = f'the columns {missing} are not in the roster of judges'
            raise KeyError(message)
        described = pd.DataFrame(columns = roster.described, dtype = 'float64')
        if any(column in roster.described for column in chosen):
            blank: dict[str, float | None] = dict.fromkeys(roster.described)
            cases_of = zip(
                rows.tolist(), data[court].tolist(), data[year].tolist(),
                strict = True)
            described = pd.DataFrame.from_records(
                [roster.describe(row, _whole(number), _whole(when))
                 if row >= 0 else blank for row, number, when in cases_of],
                columns = roster.described).astype('float64')
        # A row of -1 is no row of the roster, so its values are missing.
        listed = roster.data.reindex(rows)
        added = pd.DataFrame({
            f'{prefix or ""}{column}': (
                described[column] if column in roster.described
                else listed[column]).to_numpy()
            for column in chosen}, index = data.index)
        if indicator is not None:
            added[indicator] = rows >= 0
        clashes = [c for c in added.columns if c in data.columns]
        if clashes:
            message = (
                f'{self.name!r} would add columns named {clashes}, which the '
                f'data already has: set "prefix" to tell them apart, or name '
                f'the columns to add in "columns"'
            )
            raise ValueError(message)
        item.replace(pd.concat([data, added], axis = 1))
        item.record(
            self.name,
            source = (
                str(source) if isinstance(source, str | pathlib.Path)
                else type(source).__name__),
            rows = len(data),
            matched = int((rows >= 0).sum()),
            created = list(added.columns))
        return item

    def match(
        self,
        data: pd.DataFrame,
        other: pd.DataFrame | Roster,
        *,
        name: str = 'judge',
        court: str = 'court_num',
        year: str = 'year',
        **kwargs: Any) -> Any:
        """Returns the row of a roster for the judge that each row names.

        Args:
            data: the data, with a row for each judge to find.
            other: a roster, or the table of one.
            name: the column of `data` with the judge's name, as an opinion
                writes it. Defaults to "judge".
            court: the column of `data` with the number of the court of the
                row's case. Defaults to "court_num".
            year: the column of `data` with the year of the row's case.
                Defaults to "year".
            **kwargs: not used.

        Raises:
            KeyError: if `data` lacks one of the columns.

        Returns:
            The position of the judge's row in the roster for each row of
                `data` (see `Roster.match`), or -1 if the name is missing or
                is not matched.

        """
        _require(data, [name, court, year], repr(self.name))
        roster = Roster.create(other)
        named = zip(
            data[name].tolist(), data[court].tolist(), data[year].tolist(),
            strict = True)
        found = (
            roster.match(written, _whole(number), _whole(when))
            if isinstance(written, str) and written.strip() else None
            for written, number, when in named)
        return np.array(
            [-1 if row is None else row for row in found], dtype = 'int64')


@dataclasses.dataclass
class LoadRoster(loaders.ReferenceLoader):
    """Loads the table of a roster of judges.

    The table (see `Roster`), with a row for each court that each judge has
    served on, starts a study of the judges themselves. Its "source" is the
    path of a saved roster. Without one, the roster saved in "judges" in
    `courtpy.utilities.data_folder()` is used (see `Roster.load`). To add
    what a roster says about judges to cases, use `merge_biographies` or
    `code_panels` instead.

    """

    """ Public Methods """

    def load(self, source: Any, **kwargs: Any) -> pd.DataFrame:
        """Returns the table of a saved roster.

        Args:
            source: the path of a saved roster, or "current" for the roster
                saved in "judges" in `utilities.data_folder()`.
            **kwargs: not used.

        Raises:
            FileNotFoundError: if there is no roster at the path.

        Returns:
            The roster's table.

        """
        return Roster.load(self._locate(source)).data


@dataclasses.dataclass
class DownloadBiographies(loaders.ReferenceLoader):
    """Downloads the Federal Judicial Center's files and loads their roster.

    The center's files about judges are downloaded unless they are there
    already, or "refresh" is true (see `download`), and a roster is made from
    them (see `Roster.from_fjc`), which is saved too if "save" is set. Its
    "source" is the folder to keep the files in, which is "judges" in
    `courtpy.utilities.data_folder()` unless another is set.

    """

    """ Public Methods """

    def load(
        self,
        source: Any,
        *,
        refresh: bool | str = False,
        scores: pathlib.Path | str | None = None,
        jcs: bool | str = False,
        martin_quinn: bool | pathlib.Path | str = False,
        rulebook: str = 'judges',
        save: bool | pathlib.Path | str = False,
        **kwargs: Any) -> pd.DataFrame:
        """Downloads the files and returns the table of the roster they make.

        Args:
            source: the folder to keep the files in, or "current" for
                "judges" in `utilities.data_folder()`.
            refresh: whether to download the files even if they are there,
                to get the judges and changes since. Defaults to `False`.
            scores: the path of a file of scores of the judges to add (see
                `build_roster`). Defaults to `None`.
            jcs: whether to add each appointment's Judicial Common Space
                score as "jcs". Defaults to `False`.
            martin_quinn: whether to add the justices' Martin-Quinn scores,
                or the path of the file of them. Defaults to `False`.
            rulebook: the rules that code the judges' careers. Defaults to
                "judges".
            save: whether to save the roster where the techniques look for
                it (see `Roster.save`), or the path to save it to. Defaults
                to `False`.
            **kwargs: not used.

        Returns:
            The roster's table.

        """
        chosen = self._choose(martin_quinn)
        roster = Roster.from_fjc(
            self._locate(source),
            update = utilities.to_bool(refresh),
            scores = None if scores is None else utilities.locate(
                scores, self._get_clerk()),
            jcs = utilities.to_bool(jcs),
            martin_quinn = False if chosen is None else chosen,
            rulebook = rulebook)
        target = self._choose(save)
        if target is True:
            roster.save()
        elif isinstance(target, pathlib.Path):
            roster.save(target)
        return roster.data


def build_roster(
    service: pd.DataFrame | pathlib.Path | str,
    demographics: pd.DataFrame | pathlib.Path | str,
    career: pd.DataFrame | pathlib.Path | str | None = None,
    *,
    scores: pd.DataFrame | pathlib.Path | str | None = None,
    rulebook: fjc_biographies.Rulebook | pathlib.Path | str = 'judges') -> (
        pd.DataFrame):
    """Makes the table of a roster from the Federal Judicial Center's files.

    The files are those of the Biographical Directory of Article III Federal
    Judges that are organized by category (see `download`). The table is the
    roster that `fjc_biographies.build_roster` makes, with one row for each
    court that each judge has served on, and the two columns that courtpy
    adds to find the judges of cases. Among its columns are:

    | Column | Meaning |
    | --- | --- |
    | `nid` | The center's number for the judge. |
    | `judge` | The judge's name, as the center reports it. |
    | `last_name`, `first_name`, `middle_name`, `suffix` | Its parts. |
    | `aliases` | Other names that opinions use for the judge. Added by courtpy. |
    | `name_first_middle_last`, ... | The name written in the ways that fjc-biographies writes it, for matching it against other sources. |
    | `sequence` | The center's number for the order of the judge's service on the court among the judge's. |
    | `court`, `court_type` | The court's name and its type. |
    | `court_num` | The number that the federal rules give a court of appeals or the Supreme Court. Missing for other courts. Added by courtpy. |
    | `circuit_num` | The number of the court's circuit: its own `court_num`, or for a district court, that of its state. |
    | `start_date`, `end_date`, `senior_date` | The dates the judge's service on the court began (with a commission or a recess appointment) and ended, and the judge took senior status. |
    | `start_year`, `end_year`, `senior_year` | Their years. `end_year` is missing for a judge who is still serving. |
    | `birth_year` | The year the judge was born. |
    | `president` | The president who appointed the judge. |
    | `party` | That president's party: -1 for Democratic and 1 for Republican. Missing for other parties. |
    | `aba_rating` | The American Bar Association's rating, from 1 (not qualified) to 4 (exceptionally well qualified). Missing if there was none. |
    | `recess` | Whether the judge first took the seat by a recess appointment. |
    | `senate_vote` | The share of senators who voted to confirm the judge (1 for a voice vote). Missing if the vote is not recorded. |
    | `woman`, `minority` | Whether the judge is a woman, and whether the judge's race or ethnicity is anything other than white. |

    A judge who was reassigned to another court without a new appointment
    (as when the Eleventh Circuit was divided from the Fifth) keeps the
    president, party, rating, recess appointment, and vote of the judge's
    last appointment.

    If `career` is passed, the judge's career is the column "career" (each
    position on its own line), and each variable that `rulebook` makes from
    it is a column too. The "judges" rulebook of fjc-biographies makes
    "prosecutor", "public_defender", "law_clerk", "supreme_court_clerk",
    "solicitor_general", and "law_professor".

    Args:
        service: the file of federal judicial service
            ("federal-judicial-service.csv"), as a path or a table.
        demographics: the file of demographics ("demographics.csv").
        career: the file of professional careers
            ("professional-career.csv"). Defaults to `None`, in which case no
            careers are coded.
        scores: a table (or the path of a CSV file) with an "nid" column and
            columns of scores for the judges, which are added to the roster
            with the `merge_keys` technique of `amos`. If it has more than
            one row for a judge, the first is used, and a column whose name
            the roster already has is left out. Defaults to `None`.
        rulebook: the rules that code careers: a rulebook of fjc-biographies,
            or the name of one of its built-in rulebooks or the path of a CSV
            file. Its rules search the section "career", which has each
            position that a judge held on its own line. Defaults to "judges".

    Raises:
        KeyError: if a file lacks a column that is needed.
        ValueError: if the file of demographics has more than one row for a
            judge.

    Returns:
        The table, sorted by judge and then by the order of the judge's
            service.

    """
    roster = fjc_biographies.build_roster(
        service, demographics, career, rulebook = rulebook)
    numbers = _number_courts(
        roster.loc[roster['court_type'].isin(_APPELLATE), 'court'])
    court_num = roster['court'].map(numbers).astype('Int64')
    # A court of appeals or the Supreme Court is the circuit of its own cases,
    # as `Roster.match` compares them, so its circuit is its number.
    roster['circuit_num'] = court_num.where(
        roster['court_type'] != _DISTRICT_COURT, roster['circuit_num'])
    columns = list(roster.columns)
    roster.insert(columns.index('circuit_num'), 'court_num', court_num)
    roster.insert(
        columns.index('suffix') + 1, 'aliases',
        roster['nid'].map(_ALIASES).fillna('').astype(str))
    if scores is not None:
        scored = (
            scores.copy() if isinstance(scores, pd.DataFrame)
            else utilities.read_csv(scores))
        _require(scored, ['nid'], 'the table of scores')
        roster = amos.mergers.MergeKeys().apply(
            amos.Dataset(roster),
            source = scored.assign(
                nid = pd.to_numeric(scored['nid'], errors = 'coerce')),
            on = 'nid',
            duplicates = 'first').data
    return roster


def clean_name(name: str) -> str:
    """Returns a name the way that names are compared.

    Args:
        name: a name or a part of one, such as "R[obert] Lanier" or
            "O'Scannlain".

    Returns:
        The name in capital letters, without accents, periods, commas,
            brackets, or apostrophes, and with single spaces (as the `names`
            rules of a rulebook write the names they find). Accents are left
            out because sources differ in whether they write them (so a name
            with an accented letter matches the same name without it).

    """
    letters = "".join(
        character for character in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(character))
    return " ".join(_NAME_PUNCTUATION.sub("", letters.upper()).split())


def download(
    folder: pathlib.Path | str | None = None,
    *,
    overwrite: bool = False) -> dict[str, pathlib.Path]:
    """Downloads the Federal Judicial Center's files about judges.

    The files are three of those of the Biographical Directory of Article III
    Federal Judges that are organized by category (see
    https://www.fjc.gov/history/judges/biographical-directory-article-iii-federal-judges-export):
    federal judicial service, demographics, and professional careers. They
    need no account and are a few megabytes together. fjc-biographies
    downloads them (see `fjc_biographies.download`), into the "raw" folder of
    `folder`, which is where its scores look for them too.

    Args:
        folder: the folder whose "raw" folder they are saved in. Defaults to
            `None`, in which case "judges" in `utilities.data_folder()` is
            used.
        overwrite: whether to download a file that is already there. The
            center adds new judges and changes as they happen. Defaults to
            `False`.

    Raises:
        urllib.error.URLError: if a file cannot be downloaded.

    Returns:
        The path of each file, by the name of the parameter of `build_roster`
            that takes it ("service", "demographics", and "career").

    """
    folder = pathlib.Path(folder).expanduser() if folder else _folder()
    return fjc_biographies.download(
        _CATEGORIES, folder, overwrite = overwrite)


def name_forms(
    first: str,
    middle: str,
    last: str,
    suffix: str = '') -> dict[str, list[str]]:
    """Returns the ways that an opinion may write a judge's name.

    Opinions name judges by their last names, with initials or first names
    only when two judges of a court share one. The forms are grouped by how
    much of the name they give, which is the order in which `Roster.match`
    tries them. For Sandra Lea Lynch, they are:

    | Level | Forms |
    | --- | --- |
    | `full` | "SANDRA LEA LYNCH", "SANDRA L LYNCH", and "SANDRA LYNCH". |
    | `initials` | "S LEA LYNCH", "S L LYNCH", "SL LYNCH" (as "S.L." is written once its periods are removed), "S LYNCH", and "LEA LYNCH" (for a judge who goes by a middle name). |
    | `last` | "LYNCH". |

    With a suffix, each form is also written with it after the last name
    (such as "M D SMITH JR" and "SMITH JR"). A form is in only the first
    level that has it.

    Args:
        first: the judge's first name.
        middle: the judge's middle name or names, which may be blank.
        last: the judge's last name.
        suffix: the suffix of the judge's name, such as "Jr." or "III".
            Defaults to an empty `str`.

    Returns:
        The forms of each level ("full", "initials", and "last"), as
            `clean_name` writes them, without repeats. There are none if
            `last` is blank.

    """
    first, middle, last, suffix = (
        clean_name(part) for part in (first, middle, last, suffix))
    levels: dict[str, list[str]] = {level: [] for level in _LEVELS}
    if not last:
        return levels
    written = {
        'full': [
            f'{first} {middle} {last}',
            f'{first} {middle[:1]} {last}',
            f'{first} {last}'],
        'initials': [
            f'{first[:1]} {middle} {last}',
            f'{first[:1]} {middle[:1]} {last}',
            f'{first[:1]}{middle[:1]} {last}',
            f'{first[:1]} {last}',
            # An initial alone is not a name that a judge goes by.
            f'{middle} {last}' if len(middle) > 1 else ''],
        'last': [last]}
    # Without a first name, a full name or initials would be the last name
    # alone, which belongs to the last level.
    alone = {last, f'{last} {suffix}'.strip()}
    seen: set[str] = set()
    for level, forms in written.items():
        for form in forms:
            for written_form in (form, f'{form} {suffix}' if suffix else ''):
                named = ' '.join(written_form.split())
                if not named or named in seen or (
                    level != 'last' and named in alone):
                    continue
                seen.add(named)
                levels[level].append(named)
    return levels


def vote_table(
    data: pd.DataFrame,
    roster: Roster | pd.DataFrame | pathlib.Path | str | None = None,
    *,
    outcomes: Sequence[str] | None = None) -> pd.DataFrame:
    """Returns a table with one row for each judge on each case.

    Each name in "panel_judges" is matched to a judge in a roster (see
    `Roster`), and each judge who is found gets a row, labeled by the case's
    id and the judge's place among them (such as "4567890-2"). Cases with no
    judge who is found are left out. The table is made as `amos` reshapes
    and merges data: the `lists_to_rows` technique makes a row for each name,
    and `merge_biographies` (see `MergeBiographies`) adds the judge that each
    name refers to. The columns are:

    | Column | Meaning |
    | --- | --- |
    | `case_id` | The case's id, which the rows of its judges share. |
    | `judge`, `judge_nid` | The judge's name and number in the roster. |
    | (the columns of `data`) | The case's columns, repeated for each judge. |
    | `judge_{attribute}` | Each attribute of the judge (see `Roster.describe`), such as `judge_party`, `judge_woman`, and `judge_age`. |
    | `colleagues_{attribute}` | The mean of the attribute among the other judges of the panel who were found. Missing if there are none. |
    | `judge_author`, `judge_concurred`, `judge_dissented` | Whether the judge wrote the opinion of the court, and wrote or joined a concurrence or a dissent. A judge who concurred in part and dissented in part did both. |
    | `vote_{outcome}` | For each outcome of the case, how the judge voted: the outcome itself, or its opposite if the judge dissented. So with "outcome_reversal", `vote_reversal` is whether the judge voted to reverse. Missing if the outcome is. |

    Args:
        data: the parsed cases, which need "panel_judges", "court_num", and
            "year". "authors", "concurring", and "dissenting" are used if
            they are there.
        roster: a roster, the table of one, or the path of a saved one.
            Defaults to `None`, in which case the roster saved in "judges" in
            `utilities.data_folder()` is used.
        outcomes: names of the columns with the outcomes of the cases.
            Defaults to `None`, in which case they are the columns whose
            names start with "outcome_".

    Raises:
        KeyError: if `data` lacks a column that is needed or named.

    Returns:
        The table, labeled by "vote_id".

    """
    _require(data, ['panel_judges', 'court_num', 'year'], 'a table of votes')
    if outcomes is None:
        outcomes = [c for c in data.columns if str(c).startswith('outcome_')]
    _require(data, outcomes, 'a table of votes')
    judges = Roster.create(roster)
    described = judges.described
    panel = _named(data, 'panel_judges', judges, ['judge', *described])
    origins = panel[_CASE].to_numpy()
    labels = data.index[origins]
    places = (panel.groupby(_CASE).cumcount() + 1).tolist()
    index = pd.Index(
        [f'{label}-{place}' for label, place in zip(
            labels, places, strict = True)],
        name = 'vote_id', dtype = object)
    votes = pd.DataFrame({
        'case_id': labels.to_numpy(),
        'judge': panel['judge'].to_numpy(),
        'judge_nid': panel['nid'].to_numpy()}, index = index)
    numbers = pd.concat([
        panel[described].add_prefix('judge_'),
        _colleagues(panel, described).add_prefix('colleagues_')], axis = 1)
    made = numbers[[
        f'{kind}_{name}' for name in described
        for kind in ('judge', 'colleagues')]].astype('float64')
    made.index = index
    # Whether each judge is one of the judges that each kind of opinion
    # names, which are found in the roster as the judges of the panel are.
    keys = pd.MultiIndex.from_arrays([origins, votes['judge_nid']])
    for column, role in _ROLES.items():
        made[role] = False
        if column in data.columns:
            acted = _named(data, column, judges)
            made[role] = keys.isin(
                pd.MultiIndex.from_arrays([acted[_CASE], acted['nid']]))
    repeated = data.iloc[origins].drop(columns = [
        c for c in data.columns if c in votes.columns or c in made.columns])
    repeated.index = index
    table = pd.concat([votes, repeated, made], axis = 1)
    dissented = table['judge_dissented'].astype('boolean')
    for column in outcomes:
        name = str(column).removeprefix('outcome_')
        table[f'vote_{name}'] = table[column].astype('boolean') ^ dissented
    return table


""" Private Functions """


def _colleagues(panel: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """Returns the means of columns among the other judges of each case.

    Each judge is paired with every other judge of the same case, and the
    means are taken of the pairs of each judge.

    Args:
        panel: a table with a row for each judge on each case (as `_named`
            returns it), labeled 0, 1, 2, and so on.
        columns: names of the columns of numbers to take the means of.

    Returns:
        A table with a row for each row of `panel`, in order, and a column
            for each of `columns` with the mean of the values that are known
            among the other judges of the row's case. It is missing if there
            are no other judges, or none has a value.

    """
    place = panel.groupby(_CASE).cumcount()
    judges = pd.DataFrame({_CASE: panel[_CASE], _PLACE: place})
    pairs = judges.merge(
        panel[[_CASE, *columns]].assign(**{_OTHER: place}), on = _CASE)
    pairs = pairs[pairs[_PLACE] != pairs[_OTHER]]
    means = pairs.groupby([_CASE, _PLACE])[list(columns)].mean()
    others: pd.DataFrame = means.reindex(
        pd.MultiIndex.from_frame(judges)).reset_index(drop = True)
    return others


def _constant(
    data: pd.DataFrame,
    key: str,
    columns: Sequence[str]) -> list[str]:
    """Returns the columns that have one value among each group's rows.

    Args:
        data: the table.
        key: the column that says which group each row belongs to.
        columns: the columns to check.

    Returns:
        Those of `columns`, in order, whose values (missing ones included)
            are the same in every row of each group. A column with lists (or
            other values that cannot be compared as wholes) is left out.

    """
    whole = [
        column for column in columns
        if data[column].dtype != object
        or not data[column].map(_is_container).any()]
    if not whole:
        return []
    counts = data.groupby(key, sort = False)[whole].nunique(dropna = False)
    return [column for column in whole if bool((counts[column] <= 1).all())]


def _is_container(value: Any) -> bool:
    """Returns whether a value holds other values, such as a list.

    Args:
        value: a value of a table.

    Returns:
        Whether it is a list, tuple, set, `dict`, or array.

    """
    return isinstance(value, list | tuple | set | frozenset | dict | np.ndarray)


def _is_judge_column(column: Any) -> bool:
    """Returns whether a column of a table of votes is about one judge.

    Args:
        column: the name of the column.

    Returns:
        Whether it is "judge" or begins with one of `_JUDGE_PREFIXES`.

    """
    name = str(column)
    return name == 'judge' or name.startswith(_JUDGE_PREFIXES)


def _is_number(values: pd.Series, column: Any) -> bool:
    """Returns whether a column is numbers or booleans that can be averaged.

    Args:
        values: the column.
        column: the name of the column.

    Returns:
        Whether it is numbers or booleans and is not an id (a column whose
            name is "id" or ends with "_id").

    """
    name = str(column)
    return (
        pd.api.types.is_numeric_dtype(values.dtype)
        and name != 'id' and not name.endswith('_id'))


def _folder() -> pathlib.Path:
    """Returns the folder where a roster and its sources are kept.

    Returns:
        "judges" in `utilities.data_folder()`. It is not created.

    """
    return utilities.data_folder() / 'judges'


def _is_text(column: Any) -> bool:
    """Returns whether a column of a roster is text.

    Args:
        column: the name of the column.

    Returns:
        Whether it is one of `_TEXT` or matches `_OTHER_TEXT`.

    """
    return column in _TEXT or bool(_OTHER_TEXT.fullmatch(str(column)))


def _named(
    data: pd.DataFrame,
    column: str,
    roster: Roster,
    columns: Sequence[str] = (),
    *,
    unmatched: bool = False) -> pd.DataFrame:
    """Finds the judges that a column of the cases names.

    The `lists_to_rows` technique of `amos` makes a row for each name that a
    case lists, and `MergeBiographies` finds the judge that each name refers to.

    Args:
        data: the parsed cases, with "court_num" and "year".
        column: name of the column that lists judges' names: text with
            "; " between the names, as the federal rules write them, or
            lists of names (as `split_values` makes them).
        roster: the roster to find the judges in.
        columns: the columns to add for each judge, other than "nid" (see
            `MergeBiographies`). Defaults to an empty `tuple`.
        unmatched: whether to keep the names that are not matched, with
            missing values. Defaults to `False`.

    Returns:
        A table with a row for each judge who was found (and, with
            `unmatched`, each name that was not), in the order of the cases
            and then of the names, with each judge once for a case. Its
            columns are the position of the judge's case in `data`, the
            place of the judge's name in the case's list (1 for the first),
            the judge's "nid" (missing for a name that was not matched), and
            `columns`, and its rows are labeled 0, 1, 2, and so on.

    """
    names = pd.DataFrame({
        _CASE: np.arange(len(data)),
        _NAME: pd.Series(data[column].tolist(), dtype = object),
        'court_num': pd.Series(data['court_num'].tolist(), dtype = object),
        'year': pd.Series(data['year'].tolist(), dtype = object)})
    listed = amos.shapers.ListsToRows().shape(
        names, column = _NAME, separator = cases._SEPARATOR.strip())
    # A case with no names has one row, whose name is missing, so each name's
    # place is its row among its case's.
    listed[_SEAT] = listed.groupby(_CASE).cumcount() + 1
    merged = MergeBiographies().apply(
        amos.Dataset(listed),
        source = roster,
        name = _NAME,
        columns = ['nid', *columns],
        prefix = None,
        indicator = _FOUND).data
    repeated = merged[_FOUND] & merged.duplicated([_CASE, 'nid'])
    kept = (merged[_FOUND] | (unmatched & merged[_NAME].notna())) & ~repeated
    found: pd.DataFrame = merged[kept][[_CASE, _SEAT, 'nid', *columns]]
    return found.astype(
        {'nid': 'Int64' if unmatched else 'int64'}).reset_index(drop = True)


def _numbered(panel: pd.DataFrame, size: int) -> pd.DataFrame:
    """Returns the name and number of each judge of each case, in columns.

    Args:
        panel: a table with a row for each name on each case, with "judge"
            and "nid" (as `_named` returns it with `unmatched`).
        size: the number of cases.

    Returns:
        A table with a row for each case, in order, and "judge1",
            "judge1_nid", "judge2", "judge2_nid", and so on, numbered by the
            places of the names in the cases' lists, for as many as the
            longest list has. A name that was not matched leaves its place
            missing. It has no columns if `panel` has no rows.

    """
    place = panel[_SEAT].to_numpy()
    columns: dict[str, pd.Series] = {}
    for number in range(1, int(place.max(initial = 0)) + 1):
        judges = panel[place == number].set_index(_CASE)
        columns[f'judge{number}'] = judges['judge'].astype(object).reindex(
            range(size))
        columns[f'judge{number}_nid'] = judges['nid'].astype('Int64').reindex(
            range(size))
    return pd.DataFrame(columns, index = pd.RangeIndex(size))


def _number_courts(courts: Iterable[str]) -> dict[str, int]:
    """Returns the numbers that the federal rules give courts.

    The numbers come from the rules that make "court_num" for cases (in
    "general/header.csv"), so a judge's court and a case's court always have
    the same number.

    Args:
        courts: names of courts of appeals and the Supreme Court.

    Returns:
        The number of each court that the rules number, by its name.

    """
    numbering = amos.parsers.Rulebook(rules = [
        rule for rule in amos.parsers.Rulebook.create(rules.ParseHeader)
        if rule.names == ('court_num',)])
    names = list(dict.fromkeys(courts))
    found = numbering.apply(
        pd.DataFrame({'court': pd.Series(names, dtype = 'str')}))
    return {
        court: int(number)
        for court, number in zip(names, found['court_num'], strict = True)
        if not pd.isna(number)}


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
        message = f'{name} needs the columns {missing}, which it does not have'
        raise KeyError(message)


def _summarize(
    named: pd.DataFrame,
    size: int,
    how: Mapping[str, str],
    count: str | None = None) -> pd.DataFrame:
    """Returns summaries of the judges of each case.

    The `merge_summary` technique of `amos` adds summaries of the rows of
    another table that have the same keys: here, of the judges of each case.

    Args:
        named: a table with a row for each judge on each case (as `_named`
            returns it).
        size: the number of cases.
        how: the summary to take of each column of `named` to summarize,
            such as "mean" or "list", by the name of the column.
        count: name of a column to make with the number of judges of each
            case. Defaults to `None`, which makes no such column.

    Returns:
        A table with a row for each case, in order, and the summaries of its
            judges as columns. A case with no judges has an empty `list` for
            a "list", no judges for `count`, and other summaries that are
            missing.

    """
    table = amos.Dataset(pd.DataFrame({_CASE: np.arange(size)}))
    if named.empty:
        # There is nothing to summarize, so every summary is missing.
        blank = pd.DataFrame(
            np.nan, index = table.data.index,
            columns = [*how, *([count] if count else [])])
        table.replace(pd.concat([table.data, blank], axis = 1))
    else:
        amos.mergers.MergeSummary().apply(
            table, source = named, on = _CASE, how = dict(how), count = count)
    summaries = table.data.drop(columns = _CASE)
    for column, summary in how.items():
        if summary == 'list':
            summaries[column] = pd.Series(
                [found if isinstance(found, list) else []
                 for found in summaries[column].tolist()],
                index = summaries.index, dtype = object)
    if count is not None:
        summaries[count] = summaries[count].fillna(0).astype('int64')
    return summaries


def _whole(value: Any) -> int | None:
    """Returns a value as a whole number, or `None` if it is missing.

    Args:
        value: a number (or text of one) or a missing value.

    Returns:
        The number, or `None`.

    """
    return None if value is None or pd.isna(value) else int(value)
