"""Accessible tools for collecting, parsing, and analyzing court opinions

Contents:
    BulkData: extracts cases from CourtListener's bulk data.
    Case: the text and information of one case, ready to be parsed.
    CaseLoader: base class for techniques that load court cases.
    CaseTypes: a dataset with one row for each case type.
    Cases: a dataset with one row for each case.
    CourtData: base class for courtpy's datasets.
    CourtListener: downloads cases with the CourtListener API.
    Courts: a dataset with one row for each court.
    Dockets: a dataset with one row for each docket number of each case.
    Download: base class for a way to download cases, which a study can
        subclass to add its own.
    Judges: a dataset with one row for each judge.
    Parser: parses cases with rulebooks.
    PartyTypes: a dataset with one row for each party type.
    Project: an `amos` project, which runs a study from its settings.
    ReferenceLoader: base class for techniques that load reference data.
    Source: base class for a source of saved cases, which a study can
        subclass to add its own.
    SourceLoader: base class for techniques that download cases from a
        source and parse them.
    Votes: a dataset with one row for each judge on each case.
    code: applies coders to a table of parsed cases.
    parse: parses a folder of saved cases into a table.

"""

from __future__ import annotations

__version__ = '0.5.1'

__author__: str = 'Corey Rayburn Yung'

__all__: list[str] = [
    'BulkData',
    'Case',
    'CaseLoader',
    'CaseTypes',
    'Cases',
    'CourtData',
    'CourtListener',
    'Courts',
    'Dockets',
    'Download',
    'Judges',
    'Parser',
    'PartyTypes',
    'Project',
    'ReferenceLoader',
    'Source',
    'SourceLoader',
    'Votes',
    'audits',
    'bulk',
    'cases',
    'code',
    'coders',
    'courtlistener',
    'courts',
    'datasets',
    'fjc_idb',
    'inferers',
    'jcs',
    'judges',
    'lexis',
    'loaders',
    'options',
    'parse',
    'parsers',
    'plots',
    'politics',
    'rules',
    'scdb',
    'scores',
    'secrets',
    'shapers',
    'sources',
    'utilities']

import sys

# A study is an `amos.Project`, which courtpy offers under the same name.
from amos import Project

# Importing the modules of the wrangler and of the reference data adds their
# techniques to the `amos` library, so they can be named in settings as soon
# as courtpy is imported.
from .artist import plots
from .core import cases, datasets, options, secrets, utilities
from .core.cases import Case
from .core.datasets import (
    CaseTypes,
    Cases,
    CourtData,
    Courts,
    Dockets,
    Judges,
    PartyTypes,
    Votes,
)
from .critic import audits, inferers
from .references import courts, fjc_idb, jcs, judges, politics, scdb, scores
from .sources import bulk, courtlistener, lexis
from .sources.base import Download, Source
from .sources.bulk import BulkData
from .sources.courtlistener import CourtListener
from .wrangler import coders, loaders, parsers, rules, shapers
from .wrangler.coders import code
from .wrangler.loaders import CaseLoader, ReferenceLoader, SourceLoader
from .wrangler.parsers import Parser, parse

# Each module can be imported from `courtpy` itself (such as `courtpy.judges`),
# wherever it is in the folders of its part, as `amos` does with its steps.
for _module in (
        cases, datasets, options, secrets, utilities, bulk, courtlistener,
        lexis, coders, loaders, parsers, rules, shapers, courts, fjc_idb, jcs,
        judges, politics, scdb, scores, plots, audits, inferers):
    _short = _module.__name__.rpartition('.')[2]
    sys.modules.setdefault(f'{__name__}.{_short}', _module)
