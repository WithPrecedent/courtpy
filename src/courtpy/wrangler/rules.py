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

The rules that find the sections of a source's cases are in a folder named
for the source, with a file for each kind of court (such as
"lexis_nexis/federal_appellate.csv"; see `find_structure_file`).

`register_rulebooks` makes a rulebook of each topic, a subclass of
`amos.parsers.ParseAll` that is added to the `amos` library, so it has a name
that `courtpy.parse`, the "rulebooks" of a case loader, other rulebooks, and
the "rules" of `parse_all` can use (such as "federal" or "civil"). Each is
also a technique of its own (such as `parse_civil`), which searches the
columns of text of a dataset (such as "opinion", which a case loader keeps
with "keep_text"). A study can make rulebooks of its own folders of rules the
same way. courtpy's own are in `RULEBOOKS`: "header", "general",
"citations", "civil", "constitutional", "criminal", "review", "agencies",
"federal" (all of those, in that order), and "lexis_nexis".

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
    register_rulebooks: makes a rulebook of each topic in folders of rule
        files.
    _CASE_TYPE_TOPICS: the topics whose rules' prefixes are case types.
    _GENERAL: the folder of the rules that fit every jurisdiction.
    _INSTRUCTIONS: courtpy's "instructions" folder.
    _JURISDICTION: the jurisdiction of the cases that courtpy reads.
    _TOPICS: the topics of courtpy's rules, in the order of the "federal"
        rulebook.

"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Sequence
from typing import Any

import amos

from ..core import utilities

_INSTRUCTIONS = utilities.instructions_folder()
_GENERAL = _INSTRUCTIONS / 'general'
# The folder of the rules of each jurisdiction is named for it. courtpy reads
# only federal cases so far.
_JURISDICTION = 'federal'
# The topics whose rules find the subject of a case. The prefix of each rule's
# name (such as "tort" in "tort_negligence") is a case type.
_CASE_TYPE_TOPICS: tuple[str, ...] = ('criminal', 'civil', 'constitutional')
# The topics of the built-in rules, in the order of the "federal" rulebook.
_TOPICS: tuple[str, ...] = (
    'header', 'general', 'citations', 'civil', 'constitutional', 'criminal',
    'review', 'agencies')


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
            of rules, such as "lexis_nexis".
        courts: the kind of courts whose cases the rules fit, which is the
            stem of the file, such as "federal_appellate".

    Raises:
        FileNotFoundError: if there is no such file.

    Returns:
        The path of the file.

    """
    path = _INSTRUCTIONS / source / f'{courts}.csv'
    if not path.is_file():
        message = f'there are no rules for {courts!r} cases of {source!r}'
        raise FileNotFoundError(message)
    return path


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
# and then the federal one), "federal" for all of them, and the rules that
# find the sections of a Lexis-Nexis case.
RULEBOOKS: dict[str, type[amos.parsers.ParseAll]] = {
    **register_rulebooks(
        _GENERAL,
        _INSTRUCTIONS / _JURISDICTION,
        topics = _TOPICS,
        combined = _JURISDICTION),
    'lexis_nexis': _make_rulebook(
        'lexis_nexis',
        find_structure_file('lexis_nexis', 'federal_appellate'),
        'Finds the sections of a Lexis-Nexis case of a federal court of '
        'appeals.')}
