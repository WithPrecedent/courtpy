"""courtpy's rulebooks, which find information in the text of court opinions.

The rules are rows of CSV files (spreadsheets) in courtpy's "instructions"
folder, so they can be read and changed without knowing Python. They are
`amos` rulebooks: each row is a rule of `amos.parsers.ParseAll`, which
documents the columns and kinds of rules (and also reads files in the older
layout, with "target", "variable", "label", and "section").

The rules of each topic (such as "criminal") are in two places. The file in
the "general" folder has the rules that fit opinions of any jurisdiction, and
the file of the same name in a jurisdiction's folder (such as "federal") has
the rules that fit only that jurisdiction, if there are any. A rulebook for a
topic applies the general rules and then the jurisdiction's (see
`find_rule_files`). courtpy reads only federal cases so far, so every
rulebook here is federal.

Each source's rules are in its folder of "sources" (such as
"sources/lexis_nexis"): the rules that find the sections of its cases, with
a file for each kind of court (such as "federal_appellate.csv"; see
`find_structure_file`), and the rules of its header ("header.csv"). The
header rulebook of a source (see `make_header_rules`) applies
"general/header.csv" (the rules that fit every source), rules made from the
jurisdiction's "agencies.csv" that find the agencies named in each party and
the history (see `make_agency_rules`), the source's "header.csv", and, for a
source whose cases name their court in text, rules made from the
jurisdiction's "courts.csv" that find "court_num" and "court_name" (see
`make_court_rules`). Rules made from "courts.csv" also find the court whose
decision is reviewed in every source's history ("lower_court_num" and
"lower_court_name").
So the header rules name no courts or agencies of their own, and a court or
agency added to the tables is found without changing them.

`register_rulebooks` makes a rulebook of each topic, a subclass of
`amos.parsers.ParseAll` that is added to the `amos` library, so it has a name
that `courtpy.parse`, the "rulebooks" of a case loader, other rulebooks, and
the "rules" of `parse_all` can use (such as "federal" or "civil"). Each is
also a technique of its own (such as `parse_civil`), which searches the
columns of text of a dataset (such as "opinion", which a case loader keeps
with "keep_text"). A study can make rulebooks of its own folders of rules the
same way. courtpy's own are in `RULEBOOKS`: "general",
"citations", "civil", "constitutional", "criminal", "review", "agencies",
"federal" (all of those, in that order), the header rulebooks "header" (for
a source with no rules of its own), "courtlistener_header", and
"lexis_nexis_header", and "lexis_nexis", which finds the sections of a
Lexis-Nexis case. The parser applies a source's header rulebook (named by
its `header`) before the others.

Rules that make several values in one cell (`names`, `matches`, and
`categories` rules, such as "panel_judges", "citations_case", and
"agencies") separate them with "; ", so that a table of cases can be saved
as a CSV file. The `split_values` technique (`coders.SplitValues`) turns
such text into lists or columns.

Contents:
    RULEBOOKS: courtpy's rulebooks, by their names.
    case_type_prefixes: returns the prefixes of the names of the rules of
        the topics of cases, each of which is a case type.
    find_rule_files: returns the files of rules of a topic in a jurisdiction.
    find_structure_file: returns the file of rules that finds the sections
        of a source's cases.
    make_agency_rules: returns rules that find the agencies named in
        sections of the header.
    make_court_rules: returns rules that find a case's court from its
        name.
    make_header_rules: returns the rules of a source's header.
    register_rulebooks: makes a rulebook of each topic in folders of rule
        files.
    _AGENCY_COLUMNS: the sections of the header whose agencies are found.
    _PARTY_AGENCY_END: what must follow an agency's name in a party.
    _PARTY_COLUMNS: the sections of the header that are parties.
    _CASE_TYPE_TOPICS: the topics whose rules' prefixes are case types.
    _COURT_NAME_COLUMNS: the columns of a table of courts with patterns of
        their names, in the order they are tried.
    _GENERAL: the folder of the rules that fit every jurisdiction.
    _HEADER: the stem of the files of header rules.
    _LOWER_COURT_LEVELS: the levels of courts, in the order they are tried,
        that the history is searched for to find the court whose decision is
        reviewed.
    _INSTRUCTIONS: courtpy's "instructions" folder.
    _JURISDICTION: the jurisdiction of the cases that courtpy reads.
    _SOURCES: the folder of the rules of each source.
    _TOPICS: the topics of courtpy's rules, in the order of the "federal"
        rulebook.

"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Sequence
from typing import Any

import amos
import pandas as pd

from ..core import utilities
from ..references import courts

_INSTRUCTIONS = utilities.instructions_folder()
_GENERAL = _INSTRUCTIONS / 'general'
_SOURCES = _INSTRUCTIONS / 'sources'
_HEADER = 'header'
# The sections of the header whose agencies are found, each into a column of
# its own ("party1_agencies" and so on), so a study can tell an agency that
# is a party from one whose decision is reviewed.
_AGENCY_COLUMNS: tuple[str, ...] = ('party1', 'party2', 'history')
# An agency that is a party is named as a party of its own, so its name ends
# the party or comes before a comma ("..., Respondent"), a semicolon (between
# parties), a closing parenthesis, or "et al." A name followed by other words
# is part of another party's name (such as "FMC WYOMING CORPORATION").
_PARTY_AGENCY_END: str = r'(?=\s*(?:[,;)]|\.?\s*$|(?i:et\s+al)\b))'
# The sections of the header that are parties, whose agencies must end a party
# (see `_PARTY_AGENCY_END`).
_PARTY_COLUMNS: tuple[str, ...] = ('party1', 'party2')
# A court is found by how opinions name it before the Federal Judicial
# Center's names for it, which opinions rarely use.
_COURT_NAME_COLUMNS: tuple[str, ...] = ('opinion_name', 'fjc_name')
# The courts whose decisions the courts of appeals review. The history of an
# appeal also cites earlier appeals and remands from the Supreme Court, which
# are not the court below, so courts of appeals and the Supreme Court are left
# out. (A CourtListener case of the Supreme Court has the court below from its
# docket.)
_LOWER_COURT_LEVELS: tuple[str, ...] = ('trial', 'specialty')
# The folder of the rules of each jurisdiction is named for it. courtpy reads
# only federal cases so far.
_JURISDICTION = 'federal'
# The topics whose rules find the subject of a case. The prefix of each rule's
# name (such as "tort" in "tort_negligence") is a case type.
_CASE_TYPE_TOPICS: tuple[str, ...] = ('criminal', 'civil', 'constitutional')
# The topics of the built-in rules, in the order of the "federal" rulebook.
# The header rules are not among them, since they depend on the source (see
# `make_header_rules`).
_TOPICS: tuple[str, ...] = (
    'general', 'citations', 'civil', 'constitutional', 'criminal', 'review',
    'agencies')


""" Public Functions """


def case_type_prefixes(
    jurisdiction: str | None = _JURISDICTION) -> list[str]:
    """Returns the prefixes of the rules of the topics of cases.

    Each rule of the "criminal", "civil", and "constitutional" files names a
    column with a prefix (such as "criminal" in "criminal_firearm", or "tort"
    in "tort_negligence"), and each prefix is a case type (see
    `code_case_type`). A prefix added to a file (such as "immigration_") is
    a case type too.

    Args:
        jurisdiction: the folder of the jurisdiction's rules, such as
            "federal". Defaults to `_JURISDICTION`. If it is `None`, only
            the general rules are read.

    Returns:
        The prefixes, in the order in which they first appear in the files.

    """
    prefixes: dict[str, None] = {}
    for topic in _CASE_TYPE_TOPICS:
        for path in find_rule_files(topic, jurisdiction):
            names = utilities.read_csv(path, usecols = ['name'])['name']
            for name in names.dropna().astype(str):
                prefix, separator, _ = name.strip().partition('_')
                if separator and prefix:
                    prefixes.setdefault(prefix)
    return list(prefixes)


def find_rule_files(
    topic: str,
    jurisdiction: str | None = _JURISDICTION) -> list[pathlib.Path]:
    """Returns the files of rules of a topic in a jurisdiction.

    Args:
        topic: the stem of the files, such as "criminal".
        jurisdiction: the folder of the jurisdiction's rules, such as
            "federal". Defaults to `_JURISDICTION`. If it is `None`, only
            the general rules are returned.

    Raises:
        FileNotFoundError: if neither the "general" folder nor the
            jurisdiction's folder has a file for the topic.

    Returns:
        The file in the "general" folder and then the file in the
            jurisdiction's folder, leaving out either one that does not
            exist (as "federal/citations.csv" does not, since every rule of
            citations fits every jurisdiction).

    """
    folders = [_GENERAL]
    if jurisdiction is not None:
        folders.append(_INSTRUCTIONS / jurisdiction)
    files = [
        folder / f'{topic}.csv' for folder in folders
        if (folder / f'{topic}.csv').is_file()]
    if not files:
        searched = ', '.join(str(folder) for folder in folders)
        message = f'there is no file of rules for {topic!r} in {searched}'
        raise FileNotFoundError(message)
    return files


def find_structure_file(source: str, courts: str) -> pathlib.Path:
    """Returns the file of rules that finds the sections of a source's cases.

    Args:
        source: the name of the source, which is also the name of its folder
            of rules in `_SOURCES`, such as "lexis_nexis".
        courts: the kind of courts whose cases the rules fit, which is the
            stem of the file, such as "federal_appellate".

    Raises:
        FileNotFoundError: if there is no such file.

    Returns:
        The path of the file.

    """
    path = _SOURCES / source / f'{courts}.csv'
    if not path.is_file():
        message = f'there are no rules for {courts!r} cases of {source!r}'
        raise FileNotFoundError(message)
    return path


def make_agency_rules(
    jurisdiction: str | None = _JURISDICTION,
    columns: Sequence[str] = _AGENCY_COLUMNS,
    party_columns: Sequence[str] = _PARTY_COLUMNS) -> list[dict[str, Any]]:
    """Returns rules that find the agencies named in sections of the header.

    Each rule of the jurisdiction's "agencies" files (see `find_rule_files`)
    is made into a rule for each of `columns`, which searches only that
    column and makes "{column}_agencies" (such as "party1_agencies"), so
    that the header names no agencies of its own. In a column of
    `party_columns`, an agency's name must end a party (see
    `_PARTY_AGENCY_END`), so that a company or person named for an agency is
    not taken for it.

    Args:
        jurisdiction: the folder of the jurisdiction's rules, such as
            "federal". Defaults to `_JURISDICTION`. If it is `None`, only
            the general rules are read.
        columns: the sections to search. Defaults to `_AGENCY_COLUMNS`
            ("party1", "party2", and "history").
        party_columns: the sections of `columns` that are parties. Defaults
            to `_PARTY_COLUMNS` ("party1" and "party2").

    Returns:
        The rules, as `dict`s with the columns of a file of rules, ordered by
            column and then by the order of the files. They are empty if
            there are no "agencies" files.

    """
    try:
        paths = find_rule_files('agencies', jurisdiction)
    except FileNotFoundError:
        return []
    tables = [
        utilities.read_csv(path, dtype = str, keep_default_na = False)
        for path in paths]
    made: list[dict[str, Any]] = []
    for column in columns:
        for table in tables:
            for row in table.to_dict('records'):
                rule = {str(key): value for key, value in row.items()}
                rule.update(column = column, name = f'{column}_agencies')
                if column in party_columns:
                    rule['pattern'] = (
                        f'(?:{rule["pattern"]}){_PARTY_AGENCY_END}')
                made.append(rule)
    return made


def make_court_rules(
    jurisdiction: str = _JURISDICTION,
    column: str = 'court',
    *,
    prefix: str = '',
    levels: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Returns rules that find a case's court from its name.

    Each court of the jurisdiction's table of courts (see
    `courtpy.courts.court_table`) gives two `category` rules for each
    pattern of its names: one makes "{prefix}court_num" (its number) and the
    other "{prefix}court_name" (its `court`, such as "tenth_circuit"), if
    the pattern matches, ignoring case. Every court's "opinion_name" is
    tried before any court's "fjc_name". Within each, the courts are tried in
    the order of `levels`, and then in the order of the table (the courts
    of appeals and the Supreme Court before the district courts, so that
    "DISTRICT OF COLUMBIA" does not take the D.C. Circuit's cases).

    Args:
        jurisdiction: the folder of the jurisdiction's instructions, such as
            "federal". Defaults to `_JURISDICTION`.
        column: the section with the name of the court. Defaults to "court".
        prefix: text put before the names of the columns that the rules make
            (such as "lower_" for the court whose decision is reviewed).
            Defaults to "", which makes "court_num" and "court_name".
        levels: the levels of courts (as in the table's "level") to try, in
            order. Courts of other levels are left out. Defaults to `None`,
            which tries every court in the order of the table.

    Returns:
        The rules, as `dict`s with the columns of a file of rules. They are
            empty if the jurisdiction has no table of courts.

    """
    try:
        table = courts.court_table(jurisdiction)
    except FileNotFoundError:
        return []
    if levels is not None:
        rank = {level: place for place, level in enumerate(levels)}
        table = table[table['level'].isin(rank)].sort_values(
            'level', key = lambda found: found.map(rank), kind = 'stable')
    made: list[dict[str, Any]] = []
    for names in _COURT_NAME_COLUMNS:
        for number, name, pattern in zip(
                table['court_num'], table['court'], table[names],
                strict = True):
            if pd.isna(pattern) or not str(pattern).strip():
                continue
            note = f'From the {names} of {name} in courts.csv'
            for made_name, value in (
                    ('court_num', str(number)), ('court_name', str(name))):
                made.append({
                    'column': column,
                    'name': f'{prefix}{made_name}',
                    'kind': 'category',
                    'pattern': str(pattern),
                    'value': value,
                    'flags': 'ignorecase',
                    'note': note})
    return made


def make_header_rules(
    source: str | None = None,
    jurisdiction: str = _JURISDICTION,
    *,
    courts_named: bool = False) -> list[Any]:
    """Returns the rules of a source's header.

    The rules are, in order: "general/header.csv" (which divides the parties
    and finds their roles, the disposition, the counsel, and the judges),
    the rules of `make_agency_rules`, rules of `make_court_rules` that find
    the court whose decision is reviewed in the history ("lower_court_num"
    and "lower_court_name", trying the levels of `_LOWER_COURT_LEVELS` in
    order), the source's "header.csv" in `_SOURCES` (if it has one), and,
    if `courts_named`, the rules of `make_court_rules` that find the case's
    own court ("court_num" and "court_name").

    Args:
        source: the name of the source, which is also the name of its folder
            of rules in `_SOURCES`, such as "lexis_nexis". Defaults to
            `None`, which uses only the rules that fit every source.
        jurisdiction: the folder of the jurisdiction's rules, such as
            "federal". Defaults to `_JURISDICTION`.
        courts_named: whether the source's cases name their court in a
            "court" section that `make_court_rules` should search. Defaults
            to `False` (as for CourtListener, whose cases have the id of
            their court, and of the court below if the docket names it).

    Returns:
        The rules, in any form that `amos.parsers.Rulebook.create` accepts.

    """
    found: list[Any] = [_GENERAL / f'{_HEADER}.csv']
    found.extend(make_agency_rules(jurisdiction))
    found.extend(make_court_rules(
        jurisdiction, 'history', prefix = 'lower_',
        levels = _LOWER_COURT_LEVELS))
    if source is not None:
        path = _SOURCES / source / f'{_HEADER}.csv'
        if path.is_file():
            found.append(path)
    if courts_named:
        found.extend(make_court_rules(jurisdiction))
    return found


def register_rulebooks(
    *folders: pathlib.Path | str,
    topics: Sequence[str] | None = None,
    combined: str | None = None,
    prefix: str = '') -> dict[str, type[amos.parsers.ParseAll]]:
    """Makes a rulebook of each topic in folders of rule files.

    Each CSV file in `folders` is a topic, named for its stem (such as
    "criminal" for "criminal.csv"). The rulebook of a topic applies the file
    of the topic in each folder that has one, in the order of `folders`, so
    a folder of general rules can come before a folder of a jurisdiction's
    rules. Each rulebook is a subclass of `amos.parsers.ParseAll`, which is
    added to the `amos` library, so settings and `courtpy.parse` can name it
    (such as "criminal"), and it is a technique of its own (such as
    "parse_criminal"). A study can call this with its own folder of rules:

    ```py
    courtpy.rules.register_rulebooks(STUDY_FOLDER / 'instructions')
    ```

    Calling it again with the same names replaces the rulebooks.

    Args:
        *folders: folders of CSV files of rules, in the order in which their
            rules are applied. "~" is the user's home folder.
        topics: the topics to make rulebooks of, in order. Defaults to
            `None`, which makes one of every file in `folders`, in
            alphabetical order.
        combined: the name of a rulebook that applies every topic, in the
            order of `topics` (such as "federal"). Defaults to `None`, which
            makes no such rulebook.
        prefix: text put before the name of each topic's rulebook (with "_"
            between), so that the topics of two jurisdictions can have
            rulebooks of their own (such as "texas_civil"). Defaults to "",
            which uses the names of the topics alone.

    Raises:
        FileNotFoundError: if a topic of `topics` has no file in `folders`,
            or `folders` have no CSV files.

    Returns:
        The rulebooks, by their names (as settings name them), in order,
            with the combined one (if any) last.

    """
    paths = [pathlib.Path(folder).expanduser() for folder in folders]
    found = sorted({
        file.stem for path in paths if path.is_dir()
        for file in path.glob('*.csv')})
    names = list(topics) if topics is not None else found
    if not names:
        searched = ', '.join(str(path) for path in paths)
        message = f'there are no files of rules in {searched}'
        raise FileNotFoundError(message)
    books: dict[str, type[amos.parsers.ParseAll]] = {}
    for topic in names:
        files = [
            path / f'{topic}.csv' for path in paths
            if (path / f'{topic}.csv').is_file()]
        if not files:
            searched = ', '.join(str(path) for path in paths)
            message = f'there is no file of rules for {topic!r} in {searched}'
            raise FileNotFoundError(message)
        name = f'{prefix}_{topic}' if prefix else topic
        listed = ', '.join(
            f'"{file.parent.name}/{file.name}"' for file in files)
        books[name] = _make_rulebook(
            name, files, f'Applies the rules of {listed}.')
    if combined is not None:
        listed = ', '.join(books)
        books[combined] = _make_rulebook(
            combined, list(books.values()),
            f'Applies the rulebooks of every topic, in order: {listed}.')
    return books


""" Private Functions """


def _make_rulebook(
    name: str,
    rules: Any,
    summary: str) -> type[amos.parsers.ParseAll]:
    """Makes a rulebook and adds it to the `amos` library.

    Args:
        name: the name of the rulebook, in snake case (such as "criminal").
            Its class is named "Parse" and the name in camel case (such as
            `ParseCriminal`).
        rules: the rules, in any form that `amos.parsers.Rulebook.create`
            accepts (such as a list of files).
        summary: the first line of the class's documentation.

    Returns:
        The rulebook, a subclass of `amos.parsers.ParseAll`.

    """
    class_name = 'Parse' + ''.join(
        part.capitalize() for part in name.split('_'))
    book = type(class_name, (amos.parsers.ParseAll,), {
        'rules': rules,
        '__doc__': summary,
        '__module__': __name__})
    return dataclasses.dataclass(book)


""" Rulebooks """

# courtpy's own rulebooks: the federal rules of each topic (the general file
# and then the federal one), "federal" for all of them, the rules of each
# source's header, and the rules that find the sections of a Lexis-Nexis
# case.
RULEBOOKS: dict[str, type[amos.parsers.ParseAll]] = {
    **register_rulebooks(
        _GENERAL,
        _INSTRUCTIONS / _JURISDICTION,
        topics = _TOPICS,
        combined = _JURISDICTION),
    _HEADER: _make_rulebook(
        _HEADER,
        make_header_rules(),
        'Finds the parties, their roles, and the judges in the header of a '
        'case from a source with no header rules of its own.'),
    f'courtlistener_{_HEADER}': _make_rulebook(
        f'courtlistener_{_HEADER}',
        make_header_rules('courtlistener'),
        'Finds the parties, their roles, and the judges in a CourtListener '
        'case.'),
    f'lexis_nexis_{_HEADER}': _make_rulebook(
        f'lexis_nexis_{_HEADER}',
        make_header_rules('lexis_nexis', courts_named = True),
        'Finds the court, the parties, their roles, and the judges in the '
        'header of a Lexis-Nexis case.'),
    'lexis_nexis': _make_rulebook(
        'lexis_nexis',
        find_structure_file('lexis_nexis', 'federal_appellate'),
        'Finds the sections of a Lexis-Nexis case of a federal court of '
        'appeals.')}
