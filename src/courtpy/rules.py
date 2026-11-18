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

Each rulebook here is a subclass of `amos.parsers.ParseAll` that sets its
`rules`, so it has a name that `courtpy.parse`, the "rulebooks" of a case
loader, other rulebooks, and the "rules" of `parse_all` can use (such as
"federal" or "civil"). Each is also a technique of its own (such as
`parse_civil`), which searches the columns of text of a dataset (such as
"opinion", which a case loader keeps with "keep_text").

Rules that make several values in one cell (`names` and `matches` rules, such
as "panel_judges" and "citations_case") separate them with "; ", and the
agencies of `categories` rules are separated by ", ". The `split_values`
technique (`coders.SplitValues`) turns such text into lists or columns.

Contents:
    ParseAgencies: finds the federal agencies that a case names.
    ParseCitations: finds the citations of an opinion.
    ParseCivil: finds the civil issues of an opinion.
    ParseConstitutional: finds the constitutional issues of an opinion.
    ParseCriminal: finds the criminal issues of an opinion.
    ParseFederal: finds every variable of the federal rules.
    ParseGeneral: finds the decision, procedure, and standards of review.
    ParseHeader: finds the parties, court, disposition, and judges.
    ParseLexisNexis: finds the sections of a Lexis-Nexis case.
    ParseTorts: finds the torts and other private-law issues of an opinion.
    find_rule_files: returns the files of rules of a topic in a jurisdiction.
    find_structure_file: returns the file of rules that finds the sections
        of a source's cases.
    _GENERAL: the folder of the rules that fit every jurisdiction.
    _INSTRUCTIONS: courtpy's "instructions" folder.
    _JURISDICTION: the jurisdiction of the cases that courtpy reads.

"""

from __future__ import annotations

import dataclasses
import pathlib
from typing import Any, ClassVar

import amos

from . import utilities

_INSTRUCTIONS = utilities.instructions_folder()
_GENERAL = _INSTRUCTIONS / 'general'
# The folder of the rules of each jurisdiction is named for it. courtpy reads
# only federal cases so far.
_JURISDICTION = 'federal'


""" Public Functions """


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


""" Rulebooks """


@dataclasses.dataclass
class ParseHeader(amos.parsers.ParseAll):
    """Finds the parties, court, disposition, and judges of each case.

    The rules of "header.csv" read the sections of a case's header (and, when
    a case has no roles or judges there, the caption and the "Before ..."
    line at the start of its opinion). Every case is parsed with them.

    """

    rules: ClassVar[Any] = find_rule_files('header')


@dataclasses.dataclass
class ParseGeneral(amos.parsers.ParseAll):
    """Finds the decision, procedure, and standards of review of each case.

    The rules of "general.csv". Every case is parsed with them.

    """

    rules: ClassVar[Any] = find_rule_files('general')


@dataclasses.dataclass
class ParseCitations(amos.parsers.ParseAll):
    """Finds the citations of each opinion ("citations_...").

    The rules of "citations.csv".

    """

    rules: ClassVar[Any] = find_rule_files('citations')


@dataclasses.dataclass
class ParseCivil(amos.parsers.ParseAll):
    """Finds the civil issues of each opinion ("civil_...").

    The rules of "civil.csv".

    """

    rules: ClassVar[Any] = find_rule_files('civil')


@dataclasses.dataclass
class ParseConstitutional(amos.parsers.ParseAll):
    """Finds the constitutional issues of each opinion ("constitutional_...").

    The rules of "constitutional.csv".

    """

    rules: ClassVar[Any] = find_rule_files('constitutional')


@dataclasses.dataclass
class ParseCriminal(amos.parsers.ParseAll):
    """Finds the criminal issues of each opinion ("criminal_...").

    The rules of "criminal.csv".

    """

    rules: ClassVar[Any] = find_rule_files('criminal')


@dataclasses.dataclass
class ParseTorts(amos.parsers.ParseAll):
    """Finds the torts and other private-law issues of each opinion.

    The rules of "torts.csv" ("torts_...").

    """

    rules: ClassVar[Any] = find_rule_files('torts')


@dataclasses.dataclass
class ParseAgencies(amos.parsers.ParseAll):
    """Finds the federal agencies that each case names ("agencies").

    The rules of "agencies.csv" search the caption, the history, and the
    opinion.

    """

    rules: ClassVar[Any] = find_rule_files('agencies')


@dataclasses.dataclass
class ParseFederal(amos.parsers.ParseAll):
    """Finds every variable of the federal rules.

    The rules of every topic, in this order: header, general, citations,
    civil, constitutional, criminal, torts, and agencies. It is the rulebook
    that `courtpy.parse` uses unless others are named.

    """

    rules: ClassVar[Any] = [
        ParseHeader, ParseGeneral, ParseCitations, ParseCivil,
        ParseConstitutional, ParseCriminal, ParseTorts, ParseAgencies]


@dataclasses.dataclass
class ParseLexisNexis(amos.parsers.ParseAll):
    """Finds the sections of a Lexis-Nexis case.

    The rules of "lexis_nexis/federal_appellate.csv" divide the "text" of a
    case from a federal court of appeals into its header and opinions and
    find each part of the header (the parties, court, docket number, dates,
    history, counsel, disposition, citation, judges, and author).
    CourtListener cases do not need it, because CourtListener stores those
    parts separately.

    """

    rules: ClassVar[Any] = find_structure_file(
        'lexis_nexis', 'federal_appellate')
