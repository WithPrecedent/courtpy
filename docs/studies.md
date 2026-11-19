# Building a Study

A study built on courtpy is a small Python package with its own settings,
rules, and techniques. courtpy collects, parses, and codes the cases, and
[amos](https://WithPrecedent.github.io/amos) runs the study's workflow. This
guide shows the parts a study usually has and where each one plugs into
courtpy.

## The layout

```text
my_study/
  pyproject.toml          # depends on courtpy; names the program
  studies/
    my_study.toml         # the settings of the workflow
  src/my_study/
    __init__.py           # registers the rules and techniques
    __main__.py           # the command line program
    instructions/
      careers.csv         # rules for the judges' careers (optional)
      review.csv          # the study's own rules for opinions
    measures.py           # the study's own techniques
    sources.py            # its own sources or ways to download (optional)
  tests/
```

## Rules of your own

Put the study's rules in CSV files in the layout that the
[rules guide](rules.md) describes, one file per topic. Then make each file a
rulebook when the package is imported, in `__init__.py`:

```python
import pathlib

import courtpy

INSTRUCTIONS = pathlib.Path(__file__).parent / 'instructions'
RULEBOOKS = courtpy.rules.register_rulebooks(INSTRUCTIONS)
```

Each file is now a rulebook named for its stem (such as "review"), which the
settings can name with courtpy's own:

```toml
[load_court_listener_parameters]
rulebooks = "federal, review"
```

Each one is also a technique (such as `parse_review`) that searches the
columns of text that a loader keeps with `keep_text = true`.

`register_rulebooks` takes more than one folder. Each topic applies the file
of the same name in each folder, in order, which is how courtpy applies its
`general` rules and then its `federal` rules. A `prefix` keeps the rulebooks
of two jurisdictions apart (such as "texas_civil"), and `combined` makes one
rulebook that applies them all:

```python
courtpy.rules.register_rulebooks(
    INSTRUCTIONS / 'general', INSTRUCTIONS / 'texas',
    prefix = 'texas', combined = 'texas')
```

Check a rulebook from the terminal before using it:

```bash
courtpy rules review
```

## Techniques of your own

A study's techniques are `amos` techniques: subclasses of an `amos` genre
(such as `amos.Munger` or `amos.Shaper`) with a `munge`, `shape`, or `apply`
method. Defining the class adds it to the library, so the settings can name
it as soon as the package is imported. See the [catalog](catalog.md) for
courtpy's techniques, which a study's settings can name in the same way.

courtpy's case tables keep several values in one cell as text with "; "
between them (such as "LYNCH; HOWARD; THOMPSON"), so they can be saved as CSV
files. `courtpy.cases` has the helpers that study code usually needs for
them:

| Helper | Does |
| --- | --- |
| `split_cell` | Returns the values of a cell as a list (a list stays a list, and a missing value is an empty list). |
| `column_as_flags` | Returns a column as plain booleans, with missing values (or a missing column) as false, and "TRUE" or "yes" from a CSV file as true. |
| `flags_as_numbers` | Returns a column of flags as 1.0, 0.0, and NaN, for means and models. |
| `select_whole_cases` | Returns which rows a query selects, keeping all the rows of a case (such as each judge's vote) or none of them. |
| `require_columns` | Raises a `KeyError` that names the missing columns, with a hint of how to make them. |

## Sources of your own

courtpy reads saved cases with a source (`courtpy.Source`) and collects them
with a way to download (`courtpy.Download`). Like techniques, both add
themselves to courtpy when they are defined, so a study can add its own in a
module that its `__init__.py` imports.

A way to download saves cases in a folder. Its `download` method takes the
folder, the courts (with groups already expanded), the dates, "max_cases",
and "overwrite", and any options of its own, which come from the loader's
parameters (as text, from a settings file) or from its command line options:

```python
import argparse
import dataclasses
import pathlib
from typing import Any, ClassVar

import courtpy

from .bulk import OpinionData  # the study's own subclass of courtpy.BulkData


@dataclasses.dataclass
class OpinionsDownload(courtpy.Download):
    """Extracts cases from the bulk files that hold opinions."""

    name: ClassVar[str] = 'opinions'

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument('--parties', help = 'a pattern of case names')

    def download(
        self,
        folder: pathlib.Path,
        *,
        courts: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        max_cases: int | None = None,
        overwrite: bool = False,
        parties: Any = None,
        bulk_folder: Any = None,
        **options: Any) -> list[pathlib.Path]:
        data = OpinionData(
            folder = self.locate(bulk_folder) if bulk_folder else None)
        return data.extract(
            courts or ['ca1', 'ca2'], start_date, end_date, folder,
            max_cases = max_cases, overwrite = overwrite, parties = parties)
```

Now `load_court_listener` takes `download = "opinions"` (and `parties`),
and `my-study download opinions --parties "United States"` runs it. `locate`
finds a folder named in the settings as the loader finds its source. A
`name` that courtpy already uses (such as "bulk") replaces courtpy's way.

A new kind of saved case needs a source, which reads one file into a
`courtpy.Case`, and a loader, which needs only the source's name:

```python
@dataclasses.dataclass
class TexasCourt(courtpy.Source):
    """Reads the opinions of Texas courts, saved as text files."""

    pattern: ClassVar[str] = '*.txt'

    def read(self, path: pathlib.Path) -> courtpy.Case:
        return courtpy.Case(
            id = path.stem, source = self.name,
            sections = {'opinion': path.read_text(encoding = 'utf-8')},
            metadata = {'source': self.name}, path = path)


@dataclasses.dataclass
class LoadTexasCourt(courtpy.SourceLoader):
    """Collects, parses, and codes the opinions of Texas courts."""

    reads: ClassVar[str] = 'texas_court'
    default_source: ClassVar[str | None] = 'texas_court'
```

The source is named "texas_court" (the snake case name of its class, unless
it sets `name`), and the loader is the technique `load_texas_court`, which
takes the parameters of `load_court_listener`. A way to download for it sets
`source = 'texas_court'`. A source can also set `structure` (a rulebook that
finds the sections of each case, as Lexis-Nexis needs) and `finish` (which
adds columns to each parsed case). The [catalog](catalog.md) lists the
sources and ways to download that courtpy has.

## Settings

The settings describe the workflow, as in any `amos` project. A study of
votes on the courts of appeals might be:

```toml
[general]
seed = 43

[files]
input_folder = "data"
interim_folder = "data"
output_folder = "results"

[my_study_project]
my_study_workers = "wrangler, analyst"

[wrangler]
techniques = "load_court_listener, code_panels, cases_to_votes"

[load_court_listener_parameters]
source = "court_listener"
download = "bulk"
courts = "federal_circuits"
start_date = "2010-01-01"
rulebooks = "federal, review"
save = "cases.parquet"
reuse = true

[cases_to_votes_parameters]
label = "vote_reversal"
groups = "case_id"
```

Run it with `courtpy run studies/my_study.toml`, or with the study's own
program (below). The [Advanced User Guide](advanced.md#loaders) lists every
parameter of courtpy's loaders.

## A program of your own

`courtpy.cli.main` takes the study's commands, so the study's program has
courtpy's commands and its own. In `__main__.py`:

```python
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import Any

from courtpy import cli

from . import INSTRUCTIONS, measures


def main(argv: Sequence[str] | None = None) -> int:
    return cli.main(
        argv, prog = 'my-study', add_commands = _add_commands)


def _add_commands(commands: Any) -> None:
    scores = commands.add_parser('scores', help = 'score the judges')
    scores.add_argument('votes', help = 'a saved table of votes')
    scores.set_defaults(command = _scores)
    # The roster of judges codes their careers with the study's rules.
    commands.choices['judges'].set_defaults(
        rulebook = str(INSTRUCTIONS / 'careers.csv'))


def _scores(arguments: argparse.Namespace) -> int:
    measures.score(arguments.votes)
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

Name the program in `pyproject.toml`:

```toml
[project.scripts]
my-study = "my_study.__main__:main"
```

Then `my-study judges` makes the roster of judges with the study's rules,
`my-study run studies/my_study.toml` runs the study, and `my-study scores`
runs the study's own command. Errors that a user can fix (a missing file, a
missing column, a failed download) are shown as one line that starts with
the program's name.

## Data that studies share

courtpy keeps large downloads (the bulk data, the roster of judges, and the
reference tables) in "courts" in the data folder of the `amos` workspace,
outside of any one study, so every study uses the same files. Set
`COURTPY_DATA_DIR` to keep them elsewhere (see
[Folders](advanced.md#folders)).
