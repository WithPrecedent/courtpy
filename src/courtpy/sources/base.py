"""Base classes for sources of court opinions and ways to download them.

A `Source` is a kind of saved case that courtpy can read and parse, such as
the JSON files that CourtListener's API and bulk data are saved as
("court_listener") or the text files of Lexis-Nexis ("lexis_nexis"). A
`Download` is a way to collect cases into a folder, such as from
CourtListener's bulk data ("bulk") or its API ("api"), and saves them as one
source.

Both add themselves to courtpy when they are subclassed, as `amos`
techniques add themselves to the `amos` library, so a study can add its own
by defining a subclass in a module that it imports:

```python
import dataclasses
from typing import ClassVar

import courtpy


@dataclasses.dataclass
class OpinionsDownload(courtpy.Download):
    # The first line of the docstring is its help in "courtpy download".

    name: ClassVar[str] = 'opinions'

    def download(self, folder, *, courts = None, **options):
        ...
```

Then "opinions" can be the "download" of `load_court_listener` and the way
of `courtpy download opinions`. A subclass with the name of one that is
already known replaces it. A subclass that lists `abc.ABC` among its bases is
a base class for others, and is not added.

Contents:
    DOWNLOADS: the ways to download cases that courtpy knows, by name.
    SOURCES: the sources of saved cases that courtpy can read, by name.
    Download: base class for a way to download cases into a folder.
    Source: base class for a source of saved cases.
    find_download: returns a way to download cases, by name.
    find_source: returns a source of saved cases, by name.

"""

from __future__ import annotations

import abc
import argparse
import dataclasses
import pathlib
import re
from collections.abc import Callable, MutableMapping
from typing import Any, ClassVar

from ..core import cases

SOURCES: dict[str, type[Source]] = {}
DOWNLOADS: dict[str, type[Download]] = {}
_CAPITAL: re.Pattern[str] = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')


@dataclasses.dataclass
class Source(abc.ABC):
    """Base class for a source of saved cases.

    A subclass writes `read`, which reads one saved case into a `cases.Case`,
    and sets `pattern`, which finds its saved cases in a folder. It is added
    to `SOURCES` when it is defined, under its `name`.

    Attributes:
        name: the name of the source, such as "court_listener". Defaults to
            the snake case name of the class.
        pattern: the file pattern of its saved cases, such as "*.json".
        structure: the rulebook that finds the sections of its cases, if
            they need finding (such as "lexis_nexis"), or `None`.

    """

    name: ClassVar[str] = ''
    pattern: ClassVar[str] = '*'
    structure: ClassVar[str | None] = None

    """ Initialization Methods """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Adds the subclass to `SOURCES`, unless it is a base class.

        Args:
            **kwargs: passed to the `__init_subclass__` of the parent class.

        """
        super().__init_subclass__(**kwargs)
        if abc.ABC in cls.__bases__:
            return
        cls.name = _name_of(cls)
        SOURCES[cls.name] = cls

    """ Required Methods """

    @abc.abstractmethod
    def read(self, path: pathlib.Path) -> cases.Case:
        """Reads one saved case for parsing.

        Args:
            path: the path of the saved case.

        Returns:
            The case, with `source` set to the source's `name`.

        """

    """ Public Methods """

    def find_files(self, folder: pathlib.Path | str) -> list[pathlib.Path]:
        """Returns the saved cases in a folder and its subfolders.

        Args:
            folder: the folder.

        Returns:
            The paths of the files that match `pattern`, sorted. Files in
                hidden folders (such as ".courtpy", where downloads keep
                their place) are left out.

        """
        folder = pathlib.Path(folder)
        return sorted(
            p for p in folder.rglob(self.pattern)
            if p.is_file() and not any(
                part.startswith('.') for part in p.relative_to(folder).parts))

    def finish(self, row: MutableMapping[str, Any]) -> None:  # noqa: B027
        """Adds columns to a parsed case after the rules are applied.

        The base class adds nothing; a subclass can override it.

        Args:
            row: the parsed case, as a `dict` from column to value, which is
                changed in place.

        """


@dataclasses.dataclass
class Download(abc.ABC):
    """Base class for a way to download cases into a folder.

    A subclass writes `download`, which saves the cases of some courts and
    dates in a folder as the source named by `source`, and can write
    `add_arguments`, which adds its own options to "courtpy download". It is
    added to `DOWNLOADS` when it is defined, under its `name` and each of its
    `aliases`.

    Settings from a settings file can be text (such as "true" or "500"), so
    `download` converts the options that it takes (see `utilities.to_bool`,
    `utilities.to_date`, and `utilities.to_integer`). It should ignore
    options that it does not take, which belong to other ways to download.

    Args:
        locate: a function that finds a folder or file named in settings,
            such as the "bulk_folder" of the bulk data. Defaults to
            `pathlib.Path`. A loader passes one that looks in the project's
            input folder too.

    Attributes:
        name: the name of the way to download, such as "bulk". Defaults to
            the snake case name of the class.
        aliases: other names that settings can use for it.
        source: the name of the `Source` that its cases are saved as.

    """

    locate: Callable[[Any], pathlib.Path] = pathlib.Path

    name: ClassVar[str] = ''
    aliases: ClassVar[tuple[str, ...]] = ()
    source: ClassVar[str] = 'court_listener'

    """ Initialization Methods """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Adds the subclass to `DOWNLOADS`, unless it is a base class.

        Args:
            **kwargs: passed to the `__init_subclass__` of the parent class.

        """
        super().__init_subclass__(**kwargs)
        if abc.ABC in cls.__bases__:
            return
        cls.name = _name_of(cls)
        for name in (cls.name, *cls.aliases):
            DOWNLOADS[name] = cls

    """ Class Methods """

    @classmethod  # noqa: B027
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Adds the options of this way to download to "courtpy download".

        Each option's destination (such as "bulk_date" for "--bulk-date") is
        passed to `download` as a keyword argument. The base class adds
        none.

        Args:
            parser: the parser of "courtpy download {name}", which already
                has "--courts", "--start", "--end", "--folder",
                "--max-cases", and "--overwrite".

        """

    @classmethod
    def describe(cls) -> str:
        """Returns what this way to download does, in one line.

        Returns:
            The first line of the class's docstring.

        """
        return (cls.__doc__ or '').strip().split('\n')[0]

    """ Required Methods """

    @abc.abstractmethod
    def download(
        self,
        folder: pathlib.Path,
        *,
        courts: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        max_cases: int | None = None,
        overwrite: bool = False,
        **options: Any) -> list[pathlib.Path]:
        """Saves the cases of `courts` filed between two dates in `folder`.

        Args:
            folder: the folder to save the cases in.
            courts: CourtListener court ids, with groups already expanded
                (see `utilities.expand_courts`). Defaults to `None` (none
                named), which a subclass may fill in or refuse.
            start_date: earliest date filed, as YYYY-MM-DD. Defaults to
                `None` (no earliest date).
            end_date: latest date filed, as YYYY-MM-DD. Defaults to `None`
                (no latest date).
            max_cases: most cases to save. Defaults to `None` (every case).
            overwrite: whether to replace cases that were already saved.
                Defaults to `False`.
            **options: the options of this way to download (such as
                "bulk_date"), which may be text, and those of other ways,
                which are ignored.

        Returns:
            The paths of the cases saved.

        """


""" Public Functions """


def find_download(name: str) -> type[Download]:
    """Returns a way to download cases, by name.

    Args:
        name: the name or an alias of a `Download`, in any case and with any
            spaces around it.

    Raises:
        ValueError: if no way to download has that name.

    Returns:
        The `Download` subclass.

    """
    key = str(name).strip().lower()
    if key not in DOWNLOADS:
        names = ', '.join(f'"{n}"' for n in _primary_names())
        message = f'download must be {names}, or "none", not {name!r}'
        raise ValueError(message)
    return DOWNLOADS[key]


def find_source(name: str) -> Source:
    """Returns a source of saved cases, by name.

    Args:
        name: the name of a `Source`, such as "court_listener".

    Raises:
        ValueError: if no source has that name.

    Returns:
        An instance of the `Source` subclass.

    """
    if name not in SOURCES:
        message = f'source must be one of {sorted(SOURCES)}, not {name!r}'
        raise ValueError(message)
    return SOURCES[name]()


""" Private Functions """


def _name_of(cls: type[Source | Download]) -> str:
    """Returns the name of a source or way to download.

    Args:
        cls: the subclass.

    Returns:
        The `name` set in the class's own body, or else the snake case name
            of the class (such as "state_court" for `StateCourt`).

    """
    named = cls.__dict__.get('name')
    if named:
        return str(named)
    return _CAPITAL.sub('_', cls.__name__).lower()


def _primary_names() -> list[str]:
    """Returns the names of the ways to download, without their aliases.

    Returns:
        The names, sorted.

    """
    return sorted({cls.name for cls in DOWNLOADS.values()})
