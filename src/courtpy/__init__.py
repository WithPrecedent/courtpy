"""Accessible tools for collecting, parsing, and analyzing court opinions

Contents:
    BulkData: extracts cases from CourtListener's bulk data.
    Case: the text and information of one case, ready to be parsed.
    CaseLoader: base class for techniques that load court cases.
    CourtListener: downloads cases with the CourtListener API.
    Download: base class for a way to download cases, which a study can
        subclass to add its own.
    Parser: parses cases with rulebooks.
    Project: an `amos` project, which runs a study from its settings.
    ReferenceLoader: base class for techniques that load reference data.
    Source: base class for a source of saved cases, which a study can
        subclass to add its own.
    SourceLoader: base class for techniques that download cases from a
        source and parse them.
    code: applies coders to a table of parsed cases.
    load_cases: loads a table of parsed cases.
    parse: parses a folder of saved cases into a table.
    save_cases: saves a table of parsed cases.

"""

from __future__ import annotations

__version__ = '0.3.2'

__author__: str = 'Corey Rayburn Yung'

__all__: list[str] = [
    'BulkData',
    'Case',
    'CaseLoader',
    'CourtListener',
    'Download',
    'Parser',
    'Project',
    'ReferenceLoader',
    'Source',
    'SourceLoader',
    'bulk',
    'cases',
    'code',
    'coders',
    'courtlistener',
    'fjc_idb',
    'jcs',
    'judges',
    'lexis',
    'load_cases',
    'loaders',
    'options',
    'parse',
    'parsers',
    'politics',
    'rules',
    'save_cases',
    'scdb',
    'secrets',
    'sources',
    'utilities']

import sys

# A study is an `amos.Project`, which courtpy offers under the same name.
from amos import Project

# Importing the modules of the wrangler and of the reference data adds their
# techniques to the `amos` library, so they can be named in settings as soon
# as courtpy is imported.
from .core import cases, options, secrets, utilities
from .core.cases import Case, load_cases, save_cases
from .references import fjc_idb, jcs, judges, politics, scdb
from .sources import bulk, courtlistener, lexis
from .sources.base import Download, Source
from .sources.bulk import BulkData
from .sources.courtlistener import CourtListener
from .wrangler import coders, loaders, parsers, rules
from .wrangler.coders import code
from .wrangler.loaders import CaseLoader, ReferenceLoader, SourceLoader
from .wrangler.parsers import Parser, parse

# Each module can be imported from `courtpy` itself (such as `courtpy.judges`),
# wherever it is in the folders of its part, as `amos` does with its steps.
for _module in (
        cases, options, secrets, utilities, bulk, courtlistener, lexis,
        coders, loaders, parsers, rules, fjc_idb, jcs, judges, politics,
        scdb):
    _short = _module.__name__.rpartition('.')[2]
    sys.modules.setdefault(f'{__name__}.{_short}', _module)
