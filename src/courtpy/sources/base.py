"""The base class for sources of court opinions.

A `Source` is a kind of saved case that courtpy can read and parse, such as
the JSON files that CourtListener's bulk data and API are saved as
("courtlistener") or the text files of Lexis-Nexis ("lexis_nexis").

A source adds itself to courtpy when it is subclassed, as `amos` techniques
add themselves to the `amos` library, so a study can add its own by defining
a subclass in a module that it imports:

```python
import dataclasses
from typing import ClassVar

import courtpy


@dataclasses.dataclass
class StateCourtSource(courtpy.Source):

    name: ClassVar[str] = 'state_court'
    pattern: ClassVar[str] = '*.txt'

    def read(self, path):
        ...
```

Then "state_court" can be the source of `courtpy.parse` and of a loader
that subclasses `courtpy.SourceLoader`. A subclass with the name of one that
is already known replaces it. A subclass that lists `abc.ABC` among its bases
is a base class for others, and is not added.

Contents:
    SOURCES: the sources of saved cases that courtpy can read, by name.
    Source: base class for a source of saved cases.
    find_source: returns a source of saved cases, by name.

"""

from __future__ import annotations

import abc
import dataclasses
import pathlib
import re
from collections.abc import MutableMapping
from typing import Any, ClassVar

from ..core import cases

SOURCES: dict[str, type[Source]] = {}
_CAPITAL: re.Pattern[str] = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')


@dataclasses.dataclass
class Source(abc.ABC):
    """Base class for a source of saved cases.

    A subclass writes `read`, which reads one saved case into a `cases.Case`,
    and sets `pattern`, which finds its saved cases in a folder. It is added
    to `SOURCES` when it is defined, under its `name`.

    Attributes:
        name: the name of the source, such as "courtlistener". Defaults to
            the snake case name of the class.
        pattern: the file pattern of its saved cases, such as "*.json".
        structure: the rulebook that finds the sections of its cases, if
            they need finding (such as "lexis_nexis"), or `None`.
        header: the rulebook that finds the court, the parties and their
            roles, and the judges in its cases' sections, which the parser
            applies before any other (see `courtpy.rules.make_header_rules`).
            Defaults to "header", which has only the rules that fit every
            source.

    """

    name: ClassVar[str] = ''
    pattern: ClassVar[str] = '*'
    structure: ClassVar[str | None] = None
    header: ClassVar[str] = 'header'

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


""" Public Functions """


def find_source(name: str) -> Source:
    """Returns a source of saved cases, by name.

    Args:
        name: the name of a `Source`, such as "courtlistener".

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


def _name_of(cls: type[Source]) -> str:
    """Returns the name of a source.

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
