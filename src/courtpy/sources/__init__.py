"""The sources of court opinions that courtpy can collect and read.

Each module is one source: the CourtListener API (`courtlistener`),
CourtListener's bulk data (`bulk`), and files downloaded from Lexis-Nexis
(`lexis`). Each can also be imported from `courtpy` itself (such as
`courtpy.courtlistener`).

`base` has the classes that the sources build on, which a study can subclass
to add its own: a `Source` reads saved cases, and a `Download` collects
them. Each adds itself to `SOURCES` or `DOWNLOADS` when it is defined.

Contents:
    DOWNLOADS: the ways to download cases that courtpy knows, by name.
    SOURCES: the sources of saved cases that courtpy can read, by name.
    Download: base class for a way to download cases into a folder.
    Source: base class for a source of saved cases.
    find_download: returns a way to download cases, by name.
    find_source: returns a source of saved cases, by name.

"""

from __future__ import annotations

__all__: list[str] = [
    'DOWNLOADS',
    'SOURCES',
    'Download',
    'Source',
    'find_download',
    'find_source']

from .base import (
    DOWNLOADS,
    SOURCES,
    Download,
    Source,
    find_download,
    find_source,
)
