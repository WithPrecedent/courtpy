"""The roster of judges, which finds the judge that a name refers to.

Contents:
    DownloadBiographies: downloads the Federal Judicial Center's files about
        judges and loads the roster that they make.
    LoadRoster: loads the table of a roster of judges.
    Roster: a table of judges that finds the judge a name refers to.
    build_roster: makes the table of a roster from the Federal Judicial
        Center's files with fjc-biographies.
    download: downloads the Federal Judicial Center's files about judges
        with fjc-biographies.
    _ALIASES: names that some judges signed opinions with, by their numbers.
    _APPELLATE: the kinds of courts whose judges are on panels of appeals.
    _CATEGORIES: the categories of the Federal Judicial Center's files that
        a roster is made from.
    _DISTRICT_COURT: the Federal Judicial Center's name for a district
        court.
    _FEWEST_TO_REPAIR: the fewest letters of a name that is matched with
        one edit.
    _IDENTIFIERS: columns of numbers that identify or date a judge's
        service, which are not attributes of the judge.
    _NEEDED: the columns that every roster needs.
    _OTHER_TEXT: pattern for the other columns of text in a roster.
    _PERMUTATIONS: the start of the names of the columns with each judge's
        full name written in different ways.
    _RELATIVE: attributes of a judge that depend on the year of a case.
    _ROSTER_FILE: the name of a saved roster's file.
    _TEXT: the columns of text in a roster.

"""

from __future__ import annotations

import dataclasses
import pathlib
import re
from collections.abc import Iterable
from typing import Any

import amos
import fjc_biographies
import pandas as pd

from ...core import cases, options, utilities
from ...wrangler import loaders, rules
from ._names import (
    _LEVELS,
    clean_name,
    edit_distance,
    name_forms,
    repaired_names,
    shorter_names,
)

# Judge Johnson of the Fifth Circuit signed opinions as "Sam D. Johnson",
# Judge King of the Fifth Circuit sat as Carolyn Dineen Randall until 1988,
# Judge Richman of the Fifth Circuit sat as Priscilla Owen until 2019, and
# Judge Forrest of the Ninth Circuit sat as Danielle J. Hunsaker (the
# Federal Judicial Center's files give only the names that judges have now).
_ALIASES: dict[int, str] = {
    1382851: 'Sam D. Johnson',
    1386716: 'Carolyn Dineen Randall',
    1392271: 'Priscilla Owen',
    7328941: 'Danielle J. Hunsaker'}
_APPELLATE: frozenset[str] = frozenset({
    'U.S. Court of Appeals', 'Supreme Court'})
# The categories of the Federal Judicial Center's files that a roster is made
# from, which are the names of the parameters of `build_roster` that take
# them.
_CATEGORIES: tuple[str, ...] = ('service', 'demographics', 'career')
_DISTRICT_COURT: str = 'U.S. District Court'
# The fewest letters of a name that `Roster` matches with one edit, since a
# shorter name is too near too many others.
_FEWEST_TO_REPAIR: int = 5
_IDENTIFIERS: frozenset[str] = frozenset({
    'nid', 'sequence', 'court_num', 'circuit_num', 'start_year', 'end_year',
    'senior_year', 'birth_year'})
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

    The first of them that fits any judge who was serving is used. A name
    that fits no judge at all is then tried in shorter forms, as a full name
    or initials (see `shorter_names`): an opinion's "Susan P. Graber" is
    "Susan Graber", and its "Ed Carnes" is "E. Carnes", but never the last
    name alone. Many
    judges share a name, especially a last name, so the judges whose names
    fit are then narrowed by the court of the case:

    1. to a judge of the case's court,
    2. or else to a judge of a district court in the case's circuit, who may
       sit on its court of appeals by designation,
    3. or else to a judge of any other court, such as a court of appeals or
       district court of another circuit, who may sit by designation.

    If more than one judge fits at the first step that any judge fits, the
    name is not matched, since there is no telling which judge was meant
    (`candidates` returns them all, so that other names on the case can
    tell them apart). A name that fits no judge at all is repaired, if it
    then fits exactly one judge: written without the damage that some
    opinions' text does to names ("P OSNER" for "POSNER"), or compared with
    the judges of the case's court for a scanning error ("KRAVTTCH" for
    "Kravitch"; see `_repaired`).
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
            dataclasses.field(
                default_factory = dict, init = False, repr = False))
    _forms: dict[str, dict[str, list[int]]] = dataclasses.field(
        default_factory = dict, init = False, repr = False)
    _found: dict[tuple[str, int | None, int | None], tuple[int, ...]] = (
        dataclasses.field(default_factory = dict, init = False, repr = False))
    _numbers: dict[str, list[int | None]] = dataclasses.field(
        default_factory = dict, init = False, repr = False)
    _seated: dict[tuple[int, int], list[int]] = dataclasses.field(
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
        cases.require_columns(self.data, _NEEDED, 'a roster of judges')
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
        rows = self.candidates(name, court_num, year)
        return rows[0] if len(rows) == 1 else None

    def candidates(
        self,
        name: str,
        court_num: int | None = None,
        year: int | None = None) -> list[int]:
        """Returns every judge that a name on a case may refer to.

        They are the judges that `match` chooses among: those whose names
        fit at the first of the steps that any judge's name fits (see the
        class's documentation). More than one means that the name is
        ambiguous, such as "SMITH" on a panel of the Ninth Circuit, which had
        two Judges Smith.

        Args:
            name: the name, as the opinion writes it.
            court_num: the number of the case's court. Defaults to `None`.
            year: the year of the case. Defaults to `None`.

        Returns:
            The row of each judge's service (the most recent of each judge's
                rows that fit), or none.

        """
        key = (clean_name(name), court_num, year)
        if key not in self._found:
            self._found[key] = self._candidates(*key)
        return list(self._found[key])

    def full_name(self, row: int) -> str:
        """Returns a judge's first, middle, and last names, as one name.

        It is a full name of the judge (see `name_forms`), which `match`
        finds before any shorter name that other judges share.

        Args:
            row: a row of the table.

        Returns:
            The name, such as "SANDRA LEA LYNCH".

        """
        parts = (
            self._text[column][row]
            for column in ('first_name', 'middle_name', 'last_name', 'suffix'))
        return clean_name(' '.join(part for part in parts if part))

    def name_words(self, row: int) -> set[str]:
        """Returns the words of a judge's name that a source may list alone.

        A source that lists the words of a panel's names separately (as
        CourtListener's list of judges can: "Jill, Marcus, Martin, Pryor", or
        "Brennan, Eve, Rovner, St") gives a judge's first name, the first name
        and middle initial run together ("ROBERTA" for "Robert A."), or a
        word of a last name of several words as a word of its own.

        Args:
            row: a row of the table.

        Returns:
            The first name, the middle name, the first name and middle
                initial run together, and each word of a last name of several
                words, as `clean_name` writes them, if they are longer than
                an initial.

        """
        first = clean_name(self._text['first_name'][row])
        middle = clean_name(self._text['middle_name'][row])
        last = clean_name(self._text['last_name'][row]).split()
        words = {
            first, middle, f'{first}{middle[:1]}' if middle else '',
            *(last if len(last) > 1 else [])}
        return {word for word in words if len(word) > 1}

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

    def _candidates(
        self,
        name: str,
        court_num: int | None,
        year: int | None) -> tuple[int, ...]:
        """Returns the judges that a cleaned name on a case may refer to.

        The name as it is, at every level, and then its shorter forms as
        full names or initials (never the last name alone) are tried first.
        Only a name that none of them fits is repaired (see `_repaired`).

        Args:
            name: the name, as `clean_name` returns it.
            court_num: the number of the case's court, or `None`.
            year: the year of the case, or `None`.

        Returns:
            The row of each judge's service, or none.

        """
        courts = self._numbers['court_num']
        if court_num is not None and court_num not in courts:
            return ()
        attempts = [(name, _LEVELS)] + [
            (form, _LEVELS[:-1]) for form in shorter_names(name)]
        for form, levels in attempts:
            rows = self._fitting(form, levels, year)
            if rows:
                return self._narrow(rows, court_num)
        return self._repaired(name, court_num, year)

    def _court_judges(self, court_num: int, year: int) -> list[int]:
        """Returns the judges of a court who were serving in a year.

        Args:
            court_num: the number of the court.
            year: the year.

        Returns:
            The row of each judge's service on the court (the most recent of
                each judge's), in the order of the table.

        """
        key = (court_num, year)
        if key not in self._seated:
            rows = [
                row for row, court in enumerate(self._numbers['court_num'])
                if court == court_num and self._serving(row, year)]
            self._seated[key] = list(self._narrow(rows, court_num))
        return self._seated[key]

    def _fitting(
        self,
        form: str,
        levels: Iterable[str],
        year: int | None) -> list[int]:
        """Returns the serving judges with a form of a name, at its first level.

        Args:
            form: a form of a name, as `clean_name` writes it.
            levels: the levels of the forms of names to look in, in order.
            year: the year of the case, or `None`.

        Returns:
            The rows of the judges who have the form at the first level that
                any serving judge has it, or none.

        """
        for level in levels:
            rows = [
                row for row in self._forms[level].get(form, ())
                if year is None or self._serving(row, year)]
            if rows:
                return rows
        return []

    def _narrow(
        self,
        rows: list[int],
        court_num: int | None) -> tuple[int, ...]:
        """Returns the judges that a name refers to among judges it fits.

        Args:
            rows: the rows of the judges whose names fit, who were serving.
            court_num: the number of the case's court, or `None`.

        Returns:
            The rows of the judges at the first of the steps (the case's
                court, a district court of its circuit, and any court) at
                which any judge fits, the most recent of each judge's rows.

        """
        courts = self._numbers['court_num']
        circuits = self._numbers['circuit_num']
        nids = self._numbers['nid']
        starts = self._numbers['start_year']
        tiers = (
            [r for r in rows if court_num is not None
             and courts[r] == court_num],
            [r for r in rows if court_num is not None
             and circuits[r] == court_num],
            rows)
        for tier in tiers:
            latest: dict[int | None, int] = {}
            for row in tier:
                kept = latest.get(nids[row])
                if kept is None or (starts[row] or 0) > (starts[kept] or 0):
                    latest[nids[row]] = row
            if latest:
                return tuple(latest.values())
        return ()

    def _repaired(
        self,
        name: str,
        court_num: int | None,
        year: int | None) -> tuple[int, ...]:
        """Returns the judge that a name that fits no judge was meant to be.

        The name is first written in the forms that undo the damage of some
        opinions' text (see `repaired_names`), each tried as a name is. Then
        it is compared with the judges of the case's court who were serving
        in its year: it is a judge's if it is the last word of the judge's
        last name of several words ("EVE" for "St. Eve", or "ANTWERPEN" for
        "Van Antwerpen"), the judge's first and last names run together
        ("REENARAGGI"), or, for a name of five letters or more, one edit from
        the judge's last name (`edit_distance`), as scanning errors make it
        ("KRAVTTCH" for "Kravitch", or "SCANNLAIN" for "O'Scannlain"). Only
        a name that fits exactly one judge there is repaired.

        Args:
            name: the name, as `clean_name` returns it.
            court_num: the number of the case's court, or `None`.
            year: the year of the case, or `None`.

        Returns:
            The row of the judge's service, or none.

        """
        for form in repaired_names(name):
            rows = self._fitting(form, _LEVELS, year)
            if rows:
                found = self._narrow(rows, court_num)
                if len(found) == 1:
                    return found
        if court_num is None or year is None or ' ' in name:
            return ()
        fits = []
        for row in self._court_judges(court_num, year):
            last = clean_name(self._text['last_name'][row])
            first = clean_name(self._text['first_name'][row])
            words = last.split()
            if (
                (len(words) > 1 and name == words[-1])
                or name == f'{first}{last}'.replace(' ', '')
                or (len(name) >= _FEWEST_TO_REPAIR
                    and edit_distance(name, last.replace(' ', '')) <= 1)):
                fits.append(row)
        return tuple(fits) if len(fits) == 1 else ()

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
class LoadRoster(loaders.ReferenceLoader):
    """Loads the table of a roster of judges.

    The table (see `Roster`), with a row for each court that each judge has
    served on, starts a study of the judges themselves. Its "source" is the
    path of a saved roster. Without one, the roster saved in "judges" in
    `courtpy.utilities.data_folder()` is used (see `Roster.load`). To add
    what a roster says about judges to cases, use `add_biography` or
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


""" Public Functions """


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
        cases.require_columns(scored, ['nid'], 'the table of scores')
        roster = amos.mergers.MergeKeys().apply(
            amos.Dataset(roster),
            source = scored.assign(
                nid = pd.to_numeric(scored['nid'], errors = 'coerce')),
            on = 'nid',
            duplicates = 'first').data
    return roster


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


""" Private Functions """


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


def _number_courts(courts: Iterable[str]) -> dict[str, int]:
    """Returns the numbers that the federal rules give courts.

    The numbers come from the rules that make "court_num" for cases from the
    names in the table of federal courts (see `rules.make_court_rules`), so
    a judge's court and a case's court always have the same number.

    Args:
        courts: the Federal Judicial Center's names of courts of appeals and
            the Supreme Court.

    Returns:
        The number of each court that the rules number, by its name.

    """
    numbering = amos.parsers.Rulebook.create(rules.make_court_rules())
    names = list(dict.fromkeys(courts))
    found = numbering.apply(
        pd.DataFrame({'court': pd.Series(names, dtype = 'str')}))
    return {
        court: int(number)
        for court, number in zip(names, found['court_num'], strict = True)
        if not pd.isna(number)}


def _whole(value: Any) -> int | None:
    """Returns a value as a whole number, or `None` if it is missing.

    Args:
        value: a number (or text of one) or a missing value.

    Returns:
        The number, or `None`.

    """
    return None if value is None or pd.isna(value) else int(value)
