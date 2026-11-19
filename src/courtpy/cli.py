"""Command line interface for courtpy.

Run `courtpy --help` (or `courtpy {command} --help`) in a terminal for help.

| Command | Does |
| --- | --- |
| `courtpy key set` | Stores your CourtListener API key outside of any project. |
| `courtpy key show` | Shows where your key is found (with most of it hidden). |
| `courtpy key delete` | Removes your stored key. |
| `courtpy download bulk` | Extracts cases from CourtListener's bulk data (no key needed). |
| `courtpy download api` | Downloads cases with the CourtListener API (a key is needed). |
| `courtpy download {way}` | Downloads cases in a way that a study adds (see `courtpy.sources.Download`). |
| `courtpy split` | Divides Lexis-Nexis files of many cases into one file per case. |
| `courtpy parse` | Parses saved cases into a table (a CSV or parquet file). |
| `courtpy rules` | Checks a rulebook and lists the variables it makes. |
| `courtpy judges` | Makes and saves the roster of judges from the Federal Judicial Center's files. |
| `courtpy run` | Collects, parses, and analyzes cases as a settings file describes. |

Each command is a private function that takes the parsed arguments and
returns the program's exit code (0 for success). `_parser` connects each
command's name to its function.

A study built on courtpy can have a program of its own with courtpy's
commands and its own, by passing a function that adds them to `main`:

```python
def main(argv: Sequence[str] | None = None) -> int:
    return courtpy.cli.main(
        argv, prog = 'my-study', add_commands = _add_commands)


def _add_commands(commands: Any) -> None:
    scores = commands.add_parser('scores', help = 'score the judges')
    scores.add_argument('votes')
    scores.set_defaults(command = _scores)
    # The study's own rules for the judges' careers.
    commands.choices['judges'].set_defaults(rulebook = CAREERS)
```

Contents:
    main: runs a command.
    _DOWNLOAD_SHARED: the arguments of "courtpy download" that are not
        options of a way to download.

"""

from __future__ import annotations

import argparse
import getpass
import logging
import pathlib
import sys
from collections.abc import Callable, Sequence
from typing import Any

import amos
import requests

from . import __version__
from .core import datasets, options, secrets, utilities
from .references import judges

# Importing the modules of the sources adds them and their ways to download
# to `base.SOURCES` and `base.DOWNLOADS`.
from .sources import base, bulk, courtlistener, lexis  # noqa: F401
from .wrangler import coders, parsers

# The arguments of "courtpy download" that are not options of a way to
# download.
_DOWNLOAD_SHARED: frozenset[str] = frozenset({
    'command', 'method', 'quiet', 'courts', 'start', 'end', 'folder',
    'max_cases', 'overwrite'})


def main(
    argv: Sequence[str] | None = None,
    *,
    prog: str = 'courtpy',
    description: str | None = None,
    add_commands: Callable[[Any], None] | None = None) -> int:
    """Runs a courtpy command, or a command that a study adds.

    Messages about progress are shown unless "--quiet" is passed. Errors that
    a user can fix (such as a missing API key, a misspelled file, an invalid
    rule, or a failed download) are shown as one line instead of a
    traceback.

    Args:
        argv: the command's arguments. Defaults to `None`, in which case the
            arguments of the program are used.
        prog: the name of the program, for help and error messages. Defaults
            to "courtpy".
        description: what the program does, for its help. Defaults to
            `None`, which describes courtpy.
        add_commands: a function that adds commands to the program's
            subparsers (an `argparse` "subparsers" object, whose `choices`
            has courtpy's commands by name). Each command's "command" default
            is the function that runs it, which takes the parsed arguments
            and returns the exit code. Defaults to `None`, which adds none.

    Returns:
        0 if the command succeeded, and 1 if it failed.

    """
    parser = _parser(
        prog = prog, description = description, add_commands = add_commands)
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level = logging.WARNING if arguments.quiet else logging.INFO,
        format = '%(levelname)s: %(message)s')
    try:
        return int(arguments.command(arguments) or 0)
    except (
        courtlistener.CourtListenerError,
        secrets.MissingAPIKeyError,
        LookupError,
        OSError,
        ValueError,
        requests.RequestException) as error:
        print(f'{prog}: {error}', file = sys.stderr)
        return 1


""" Commands """


def _download(arguments: argparse.Namespace) -> int:
    """Downloads cases ("courtpy download {way}").

    The way to download is a `courtpy.sources.Download`, such as "bulk"
    (which extracts the cases from CourtListener's bulk data) or "api"
    (which downloads them with the API and needs a key), or one that a study
    adds.

    Args:
        arguments: the parsed arguments: "method" (the name of the way to
            download), "courts", "start", "end", "folder", "max_cases", and
            "overwrite", and the options that the way to download added
            (such as "dockets" for "api" or "bulk_date" for "bulk").

    Returns:
        0.

    """
    method = base.find_download(arguments.method)
    folder = pathlib.Path(arguments.folder or method.source)
    options = {
        k: v for k, v in vars(arguments).items() if k not in _DOWNLOAD_SHARED}
    saved = method().download(
        folder,
        courts = (
            utilities.expand_courts(arguments.courts)
            if arguments.courts else None),
        start_date = arguments.start,
        end_date = arguments.end,
        max_cases = arguments.max_cases,
        overwrite = arguments.overwrite,
        **options)
    print(f'{len(saved)} cases saved in {folder}')
    return 0


def _judges(arguments: argparse.Namespace) -> int:
    """Makes and saves the roster of judges ("courtpy judges").

    The roster is made from the Federal Judicial Center's files (see
    `judges.Roster.from_fjc`), which are downloaded first if they are not
    there, and saved where the techniques look for it unless "--output"
    names another file.

    Args:
        arguments: the parsed arguments: "update" (whether to download the
            files again), "no_jcs", "martin_quinn", "rulebook" (the rules of
            the judges' careers), and "output".

    Returns:
        0.

    """
    roster = judges.Roster.from_fjc(
        update = arguments.update,
        jcs = not arguments.no_jcs,
        martin_quinn = arguments.martin_quinn,
        rulebook = arguments.rulebook)
    path = roster.save(arguments.output)
    people = roster.data['nid'].nunique()
    print(f'A roster of {people} judges was saved to {path}')
    return 0


def _key_delete(arguments: argparse.Namespace) -> int:  # noqa: ARG001
    """Removes the stored API key ("courtpy key delete").

    The key is removed from the keyring and the secrets file. If a key is
    still found elsewhere (in an environment variable or a `.env` file, which
    courtpy does not change), where it is found is shown.

    Args:
        arguments: the parsed arguments, which this command does not use.

    Returns:
        0.

    """
    removed = secrets.delete_api_key()
    if removed:
        print('Removed the API key from ' + ' and '.join(removed))
    else:
        print('No stored API key was found.')
    found = secrets.find_api_key()
    if found is not None:
        print(
            f'A key is still found in {found[1]}, which courtpy does not '
            f'change.')
    return 0


def _key_set(arguments: argparse.Namespace) -> int:
    """Stores the API key ("courtpy key set").

    The key is asked for without being shown as it is typed, or read from
    standard input with "--stdin" (for scripts).

    Args:
        arguments: the parsed arguments: "store" (where to store the key) and
            "stdin" (whether to read it from standard input).

    Returns:
        0.

    """
    if arguments.stdin:
        key = sys.stdin.readline()
    else:
        key = getpass.getpass('CourtListener API key (it will not be shown): ')
    place = secrets.set_api_key(key, store = arguments.store)
    print(f'Stored the API key in {place}.')
    return 0


def _key_show(arguments: argparse.Namespace) -> int:  # noqa: ARG001
    """Shows where the API key is found, with most of it hidden.

    This is "courtpy key show". It also shows the path of the secrets file.

    Args:
        arguments: the parsed arguments, which this command does not use.

    Returns:
        0 if a key was found, and 1 (with an explanation of how to store one)
            if not.

    """
    found = secrets.find_api_key()
    if found is None:
        print(secrets.MissingAPIKeyError())
        return 1
    key, place = found
    print(f'API key {secrets.mask(key)} found in {place}.')
    print(f'(The secrets file is {secrets.secrets_path()}.)')
    return 0


def _parse(arguments: argparse.Namespace) -> int:
    """Parses saved cases into a table ("courtpy parse").

    Unless "--no-code" is passed, the default coders are applied (see
    `coders.code`) before the table is saved.

    Args:
        arguments: the parsed arguments: "folder", "source", "rulebooks",
            "keep_text", "limit", "workers", "no_code", and "output".

    Returns:
        0 if cases were parsed, and 1 if the folder had none.

    """
    data = parsers.parse(
        arguments.folder,
        source = arguments.source,
        rulebooks = arguments.rulebooks or options._DEFAULT_JURISDICTION,
        keep_text = arguments.keep_text,
        limit = arguments.limit,
        workers = arguments.workers)
    if data.empty:
        print(f'courtpy: no {arguments.source} cases in {arguments.folder}',
              file = sys.stderr)
        return 1
    dataset = datasets.Cases.create(
        data if arguments.no_code else coders.code(data))
    path = pathlib.Path(arguments.output)
    dataset.save(path)
    print(f'{len(dataset.data)} cases parsed into {path}')
    return 0


def _rules(arguments: argparse.Namespace) -> int:
    """Checks a rulebook and lists the variables it makes ("courtpy rules").

    An invalid rule raises a `ValueError` naming its file and row, which
    `main` shows.

    Args:
        arguments: the parsed arguments: "rulebooks" (names of built-in
            rulebooks or paths to CSV files).

    Returns:
        0.

    """
    rulebook = amos.parsers.Rulebook.create(*arguments.rulebooks)
    print(f'{len(rulebook)} rules are valid ({rulebook.name}).')
    print(f'They search: {", ".join(rulebook.columns)}')
    print(f'They make {len(rulebook.names)} columns:')
    for name in rulebook.names:
        print(f'  {name}')
    return 0


def _run(arguments: argparse.Namespace) -> int:
    """Collects, parses, and analyzes cases as a settings file describes.

    This is "courtpy run". The project's report is shown, and its results are
    exported if "--export" is passed (see `amos.Project.export`).

    Args:
        arguments: the parsed arguments: "settings" (the path to a settings
            file) and "export".

    Returns:
        0.

    """
    project = amos.Project.create(arguments.settings)
    print(project.report.contents if project.report else project.result)
    if arguments.export:
        folder = project.export()
        print(f'Results exported to {folder}')
    return 0


def _split(arguments: argparse.Namespace) -> int:
    """Divides Lexis-Nexis files of many cases ("courtpy split").

    Args:
        arguments: the parsed arguments: "files" (text files, or folders whose
            ".txt" files are used) and "folder" (where to save the cases).

    Returns:
        0.

    """
    files = [pathlib.Path(f) for f in arguments.files]
    expanded = [
        p for f in files for p in (sorted(f.glob('*.txt'))
        if f.is_dir() else [f])]
    saved = lexis.split(expanded, arguments.folder)
    print(f'{len(saved)} cases saved in {arguments.folder}')
    return 0


""" Private Functions """


def _parser(
    *,
    prog: str = 'courtpy',
    description: str | None = None,
    add_commands: Callable[[Any], None] | None = None) -> (
        argparse.ArgumentParser):
    """Returns the parser of the command line arguments.

    Each command is a subparser whose "command" default is the function that
    runs it, which `main` calls with the parsed arguments.

    Args:
        prog: the name of the program. Defaults to "courtpy".
        description: what the program does. Defaults to `None`, which
            describes courtpy.
        add_commands: a function that adds commands to the subparsers, after
            courtpy's. Defaults to `None`.

    Returns:
        The parser, with the options shared by every command ("--version"
            and "--quiet") and a subparser for each command.

    """
    parser = argparse.ArgumentParser(
        prog = prog,
        description = (
            description or 'Collect, parse, and analyze court opinions.'))
    parser.add_argument('--version', action = 'version', version = __version__)
    parser.add_argument(
        '-q', '--quiet', action = 'store_true', help = 'show only warnings')
    commands = parser.add_subparsers(title = 'commands', required = True)

    key = commands.add_parser('key', help = 'manage the CourtListener API key')
    key_commands = key.add_subparsers(title = 'key commands', required = True)
    key_set = key_commands.add_parser('set', help = 'store the API key')
    key_set.add_argument(
        '--store', choices = ['auto', 'keyring', 'file'], default = 'auto',
        help = 'where to store it (default: the keyring, if there is one)')
    key_set.add_argument(
        '--stdin', action = 'store_true',
        help = 'read the key from standard input instead of asking')
    key_set.set_defaults(command = _key_set)
    key_commands.add_parser(
        'show', help = 'show where the key is found').set_defaults(
            command = _key_show)
    key_commands.add_parser(
        'delete', help = 'remove the stored key').set_defaults(
            command = _key_delete)

    download = commands.add_parser(
        'download', help = 'download cases (see "download {way} --help")')
    ways = download.add_subparsers(
        title = 'ways to download', dest = 'method', required = True)
    shared = argparse.ArgumentParser(add_help = False)
    shared.add_argument(
        '--courts', nargs = '+',
        help = 'court ids (such as ca1) or groups (such as federal_appellate)')
    shared.add_argument('--start', help = 'earliest date filed (YYYY-MM-DD)')
    shared.add_argument('--end', help = 'latest date filed (YYYY-MM-DD)')
    shared.add_argument(
        '--folder',
        help = 'folder to save the cases in (default: the name of the '
               'source, such as courtlistener)')
    shared.add_argument(
        '--max-cases', type = int, help = 'most cases to save')
    shared.add_argument(
        '--overwrite', action = 'store_true',
        help = 'download cases that were already saved')
    for name in sorted({c.name for c in base.DOWNLOADS.values()}):
        method = base.DOWNLOADS[name]
        way = ways.add_parser(
            name, parents = [shared], help = method.describe(),
            description = method.describe())
        method.add_arguments(way)
        way.set_defaults(command = _download)

    split = commands.add_parser(
        'split', help = 'divide Lexis-Nexis files of many cases')
    split.add_argument('files', nargs = '+', help = 'files or folders')
    split.add_argument(
        '--folder', default = 'lexis_nexis',
        help = 'folder to save the cases in (default: lexis_nexis)')
    split.set_defaults(command = _split)

    parse = commands.add_parser(
        'parse', help = 'parse saved cases into a table')
    parse.add_argument('folder', help = 'folder of saved cases')
    parse.add_argument(
        '--source', choices = sorted(base.SOURCES),
        default = 'courtlistener')
    parse.add_argument(
        '--rulebooks', nargs = '+',
        help = (
            'built-in rulebooks (such as civil) or CSV files, applied after '
            "the source's header rules and general (default: federal)"))
    parse.add_argument(
        '--output', default = 'cases.csv',
        help = (
            'file to save the table to, with the whole dataset beside it '
            'in a .joblib file (default: cases.csv)'))
    parse.add_argument(
        '--keep-text', action = 'store_true', help = "keep the text of the cases' sections")
    parse.add_argument('--limit', type = int, help = 'most cases to parse')
    parse.add_argument(
        '--workers', type = int, default = 1, help = 'processes to parse with')
    parse.add_argument(
        '--no-code', action = 'store_true',
        help = 'do not code parties, case types, and outcomes')
    parse.set_defaults(command = _parse)

    check = commands.add_parser(
        'rules', help = 'check a rulebook and list its variables')
    check.add_argument(
        'rulebooks', nargs = '+',
        help = (
            'built-in rulebooks (such as federal, civil, or lexis_nexis) or '
            'CSV files'))
    check.set_defaults(command = _rules)

    run = commands.add_parser(
        'run', help = 'collect, parse, and analyze cases from a settings file')
    run.add_argument('settings', help = 'settings file (ini, toml, json, yaml)')
    run.add_argument(
        '--export', action = 'store_true', help = 'export the results')
    run.set_defaults(command = _run)

    roster = commands.add_parser(
        'judges',
        help = "make the roster of judges from the Federal Judicial Center's "
               'files')
    roster.add_argument(
        '--update', action = 'store_true',
        help = "download the Federal Judicial Center's files again")
    roster.add_argument(
        '--no-jcs', action = 'store_true',
        help = 'leave out the Judicial Common Space scores')
    roster.add_argument(
        '--martin-quinn', action = 'store_true',
        help = "add the justices' Martin-Quinn scores")
    roster.add_argument(
        '--rulebook', default = 'judges',
        help = "rules that code the judges' careers: a CSV file or a "
               'rulebook of fjc-biographies (default: judges)')
    roster.add_argument(
        '--output',
        help = 'file to save the roster to (default: where the techniques '
               'look for it)')
    roster.set_defaults(command = _judges)
    if add_commands is not None:
        add_commands(commands)
    return parser


if __name__ == '__main__':
    sys.exit(main())
