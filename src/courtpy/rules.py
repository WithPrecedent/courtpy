"""courtpy's rulebooks, which find information in the text of court opinions.

The rules are rows of CSV files (spreadsheets) in courtpy's "instructions"
folder, so they can be read and changed without knowing Python. They are
`amos` rulebooks: each row is a rule of `amos.parsers.ParseAll`, which
documents the columns and kinds of rules (and also reads files in the older
layout, with "target", "variable", "label", and "section").

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
    _FEDERAL: the folder of the federal rules.

"""

from __future__ import annotations

import dataclasses
from typing import Any, ClassVar

import amos

from . import utilities

_FEDERAL = utilities.instructions_folder() / 'federal'


@dataclasses.dataclass
class ParseHeader(amos.parsers.ParseAll):
    """Finds the parties, court, disposition, and judges of each case.

    The rules of "federal/header.csv" read the sections of a case's header
    (and, when a case has no roles or judges there, the caption and the
    "Before ..." line at the start of its opinion). Every case is parsed with
    them.

    """

    rules: ClassVar[Any] = _FEDERAL / 'header.csv'


@dataclasses.dataclass
class ParseGeneral(amos.parsers.ParseAll):
    """Finds the decision, procedure, and standards of review of each case.

    The rules of "federal/general.csv". Every case is parsed with them.

    """

    rules: ClassVar[Any] = _FEDERAL / 'general.csv'


@dataclasses.dataclass
class ParseCitations(amos.parsers.ParseAll):
    """Finds the citations of each opinion ("citations_...").

    The rules of "federal/citations.csv".

    """

    rules: ClassVar[Any] = _FEDERAL / 'citations.csv'


@dataclasses.dataclass
class ParseCivil(amos.parsers.ParseAll):
    """Finds the civil issues of each opinion ("civil_...").

    The rules of "federal/civil.csv".

    """

    rules: ClassVar[Any] = _FEDERAL / 'civil.csv'


@dataclasses.dataclass
class ParseConstitutional(amos.parsers.ParseAll):
    """Finds the constitutional issues of each opinion ("constitutional_...").

    The rules of "federal/constitutional.csv".

    """

    rules: ClassVar[Any] = _FEDERAL / 'constitutional.csv'


@dataclasses.dataclass
class ParseCriminal(amos.parsers.ParseAll):
    """Finds the criminal issues of each opinion ("criminal_...").

    The rules of "federal/criminal.csv".

    """

    rules: ClassVar[Any] = _FEDERAL / 'criminal.csv'


@dataclasses.dataclass
class ParseAgencies(amos.parsers.ParseAll):
    """Finds the federal agencies that each case names ("agencies").

    The rules of "federal/agencies.csv" search the caption, the history, and
    the opinion.

    """

    rules: ClassVar[Any] = _FEDERAL / 'agencies.csv'


@dataclasses.dataclass
class ParseFederal(amos.parsers.ParseAll):
    """Finds every variable of the federal rules.

    The rules of every file in the "federal" folder, in this order: header,
    general, citations, civil, constitutional, criminal, and agencies. It is
    the rulebook that `courtpy.parse` uses unless others are named.

    """

    rules: ClassVar[Any] = [
        ParseHeader, ParseGeneral, ParseCitations, ParseCivil,
        ParseConstitutional, ParseCriminal, ParseAgencies]


@dataclasses.dataclass
class ParseLexisNexis(amos.parsers.ParseAll):
    """Finds the sections of a Lexis-Nexis case.

    The rules of "lexis_nexis.csv" divide the "text" of a case into its
    header and opinions and find each part of the header (the parties,
    court, docket number, dates, history, counsel, disposition, citation,
    judges, and author). CourtListener cases do not need it, because
    CourtListener stores those parts separately.

    """

    rules: ClassVar[Any] = utilities.instructions_folder() / 'lexis_nexis.csv'
