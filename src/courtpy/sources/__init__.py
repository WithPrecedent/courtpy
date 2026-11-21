"""The sources of court opinions that courtpy can collect and read.

Each module is one source: CourtListener's bulk data and API
(`courtlistener`) and files downloaded from Lexis-Nexis (`lexis`). Each can
also be imported from `courtpy` itself (such as `courtpy.courtlistener`).

`base` has `Source`, which the sources build on and a study can subclass to
read its own saved cases. Each source adds itself to `SOURCES` when it is
defined.

Contents:
    SOURCES: the sources of saved cases that courtpy can read, by name.
    Source: base class for a source of saved cases.
    find_source: returns a source of saved cases, by name.

"""

from __future__ import annotations

__all__: list[str] = ['SOURCES', 'Source', 'find_source']

from .base import SOURCES, Source, find_source
