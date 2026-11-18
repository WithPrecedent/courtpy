"""Turns saved court opinions into a table, one row for each case.

Parsing has three stages:

1. A reader for the source (CourtListener or Lexis-Nexis) makes a `Case`
   with sections of text (such as "party", "judges", and "opinion") and
   information that needs no parsing (such as CourtListener's date filed).
2. For Lexis-Nexis, the "lexis_nexis" rules find the sections of the header
   (see `courtpy.lexis`). CourtListener's sections come from its data.
3. Rules find variables in the sections. The "header" rules (the parties'
   roles, the court, the disposition, and the judges) and the "general"
   rules (the decision, procedure, and standards of review) are always
   applied, and then the rulebooks that are named (by default, the
   "federal" rules, which add citations, civil, constitutional, criminal,
   and tort issues, and agencies; "citations", "civil", "constitutional",
   "criminal", "torts", and "agencies" can be named alone). Each rulebook
   has the rules of its "general" file and then those of its "federal"
   file, if there is one (see `courtpy.rules`).

The rulebooks are those of `amos` (`amos.parsers.Rulebook`, and courtpy's own
in `courtpy.rules`), which search a table of the sections of many cases at
once, a row for each case and a column for each section.

Every section except those whose names end in "_lines" is collapsed onto one
line between stages 2 and 3, so that phrases broken across lines are found.

Contents:
    SOURCES: the sources that courtpy can read.
    Parser: parses cases with rulebooks.
    Source: how to read and parse one source of opinions.
    find_files: returns the saved cases of a source in a folder.
    parse: parses a folder of saved cases into a table.
    logger: the module's logger, which reports parsing progress and cases
        that could not be parsed.

"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import logging
import pathlib
from collections.abc import (
    Callable,
    Iterable,
    Iterator,
    MutableMapping,
    Sequence,
)
from typing import Any

import amos
import numpy as np
import pandas as pd

# Importing `rules` adds courtpy's rulebooks to the `amos` library, so that
# rulebooks can be named (such as "federal").
from . import (
    cases,
    courtlistener,
    lexis,
    options,
    rules,  # noqa: F401
    utilities,
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen = True)
class Source:
    """How to read and parse one source of opinions.

    Args:
        name: the name of the source, such as "court_listener".
        pattern: the file pattern of its saved cases, such as "*.json".
        read: a function that reads a saved case into a `Case`.
        structure: the rulebook that finds the sections of its cases, if they
            need finding. Defaults to `None`.
        finish: a function that adds columns to a parsed case (a `dict`)
            after the rules are applied. Defaults to `None`.

    """

    name: str
    pattern: str
    read: Callable[[pathlib.Path], cases.Case]
    structure: str | None = None
    finish: Callable[[MutableMapping[str, Any]], Any] | None = None


SOURCES: dict[str, Source] = {
    'court_listener': Source(
        name = 'court_listener',
        pattern = '*.json',
        read = courtlistener.read_case),
    'lexis_nexis': Source(
        name = 'lexis_nexis',
        pattern = '*.txt',
        read = lexis.read_case,
        structure = 'lexis_nexis',
        finish = lexis.finish)}


@dataclasses.dataclass
class Parser:
    """Parses cases with rulebooks.

    Args:
        rulebook: the rules of the jurisdiction, applied to every case.
        structures: the rules that find the sections of each source's cases,
            by the name of the source. Defaults to an empty `dict`, in which
            case they are loaded when first needed.
        keep_text: whether to keep the text of the opinions (and of the
            Lexis-Nexis header) in the table. Defaults to `False`.

    """

    rulebook: amos.parsers.Rulebook
    structures: dict[str, amos.parsers.Rulebook] = dataclasses.field(
        default_factory = dict)
    keep_text: bool = False

    """ Class Methods """

    @classmethod
    def create(
        cls,
        rulebooks: str | pathlib.Path | Sequence[str | pathlib.Path] = (
            options._DEFAULT_JURISDICTION),
        *,
        keep_text: bool = False) -> Parser:
        """Returns a parser with the rules in `rulebooks`.

        The rules of `options._REQUIRED_RULEBOOKS` are always applied first,
        whether or not they are named.

        Args:
            rulebooks: names of rulebooks (such as "federal" or "civil") or
                paths to CSV files or folders of them, applied in order.
                Defaults to `options._DEFAULT_JURISDICTION`.
            keep_text: whether to keep the text of the opinions in the table.
                Defaults to `False`.

        Raises:
            FileNotFoundError: if a rulebook is not the name of one, a CSV
                file, or a folder with CSV files.
            ValueError: if a file is missing a column or a row is not a valid
                rule. The message names the file and row.

        Returns:
            The parser.

        """
        if isinstance(rulebooks, str):
            rulebooks = utilities.listify(rulebooks)
        elif isinstance(rulebooks, pathlib.Path):
            rulebooks = [rulebooks]
        rulebook = amos.parsers.Rulebook.create(
            *options._REQUIRED_RULEBOOKS, *rulebooks)
        return cls(rulebook = rulebook, keep_text = keep_text)

    """ Public Methods """

    def parse(self, case: cases.Case) -> dict[str, Any]:
        """Returns one row of the table for `case`.

        Args:
            case: the case to parse.

        Returns:
            The case's variables, by the names of their columns, with `None`
                for those that are missing (see `parse_cases`).

        """
        row = self.parse_cases([case]).iloc[0].to_dict()
        return {
            str(k): None if _is_missing(v) else v for k, v in row.items()}

    def parse_cases(self, found: Sequence[cases.Case]) -> pd.DataFrame:
        """Returns a table of `found`, with a row for each case.

        The cases of each source are parsed together, with every rule
        searching every case at once.

        Args:
            found: the cases to parse.

        Returns:
            The table, with a row for each case, in order, labeled 0, 1, 2,
                and so on. Information from a case's `metadata` comes first
                and is used instead of any variable of the same name that the
                rules find (unless it is missing).

        """
        groups: dict[str, list[int]] = {}
        for position, case in enumerate(found):
            groups.setdefault(case.source, []).append(position)
        tables = [
            self._parse_source([found[p] for p in positions]).set_axis(
                positions)
            for positions in groups.values()]
        if not tables:
            return pd.DataFrame()
        return pd.concat(tables).sort_index() if len(tables) > 1 else tables[0]

    def parse_file(
        self,
        path: pathlib.Path,
        source: str) -> tuple[str, dict[str, Any]]:
        """Reads and parses one saved case.

        Args:
            path: path of the saved case.
            source: the name of its source, such as "court_listener".

        Returns:
            The case's id and its row of the table.

        """
        case = SOURCES[source].read(path)
        return case.id, self.parse(case)

    """ Private Methods """

    def _parse_source(self, group: Sequence[cases.Case]) -> pd.DataFrame:
        """Returns a table of cases that all come from one source.

        Args:
            group: the cases.

        Returns:
            The table, with a row for each case, labeled 0, 1, 2, and so on.

        """
        source = SOURCES.get(group[0].source)
        sections = pd.DataFrame(
            [case.sections for case in group],
            index = pd.RangeIndex(len(group))).astype('str')
        found = pd.DataFrame(index = sections.index)
        if source is not None and source.structure:
            sections, found = _apply(self._structure(source.structure), sections)
        for column in sections.columns:
            if not str(column).endswith('_lines'):
                sections[column] = sections[column].str.replace(
                    r'\s+', ' ', regex = True).str.strip()
        sections, made = _apply(self.rulebook, sections)
        found = pd.concat(
            [found.drop(columns = made.columns, errors = 'ignore'), made],
            axis = 1)
        table = pd.DataFrame(
            [case.metadata for case in group], index = sections.index)
        shared = [c for c in found.columns if c in table.columns]
        for column in shared:
            table[column] = table[column].combine_first(found[column])
        table = pd.concat([table, found.drop(columns = shared)], axis = 1)
        if source is not None and source.finish is not None:
            rows = [
                {str(k): None if _is_missing(v) else v for k, v in row.items()}
                for row in table.to_dict('records')]
            for row in rows:
                source.finish(row)
            table = pd.DataFrame(rows, index = table.index)
        table = _derive(table, sections)
        table = table.drop(columns = [
            c for c in table.columns
            if c in options._LARGE_SECTIONS or str(c).endswith('_lines')])
        if self.keep_text:
            for name in ('header', 'opinion'):
                table[name] = sections.get(name)
        return table

    def _structure(self, name: str) -> amos.parsers.Rulebook:
        """Returns the rulebook that finds the sections of a source's cases.

        The rulebook is loaded the first time it is needed and kept in
        `structures`, so its CSV files are read only once.

        Args:
            name: the name of a rulebook or the path to a CSV file (a
                `Source`'s `structure`, such as "lexis_nexis").

        Returns:
            The rulebook.

        """
        if name not in self.structures:
            self.structures[name] = amos.parsers.Rulebook.create(name)
        return self.structures[name]


def find_files(
    folder: pathlib.Path | str,
    source: str = 'court_listener') -> list[pathlib.Path]:
    """Returns the saved cases of a source in a folder and its subfolders.

    Args:
        folder: the folder.
        source: the name of the source. Defaults to "court_listener".

    Raises:
        ValueError: if `source` is not in `SOURCES`.

    Returns:
        The paths, sorted. Files in hidden folders (such as ".courtpy", where
            downloads keep their place) are left out.

    """
    if source not in SOURCES:
        message = f'source must be one of {list(SOURCES)}, not {source!r}'
        raise ValueError(message)
    folder = pathlib.Path(folder)
    return sorted(
        p for p in folder.rglob(SOURCES[source].pattern)
        if p.is_file() and not any(
            part.startswith('.') for part in p.relative_to(folder).parts))


def parse(
    files: pathlib.Path | str | Iterable[pathlib.Path | str],
    source: str = 'court_listener',
    rulebooks: str | pathlib.Path | Sequence[str | pathlib.Path] = (
        options._DEFAULT_JURISDICTION),
    *,
    keep_text: bool = False,
    limit: int | None = None,
    workers: int = 1) -> pd.DataFrame:
    """Parses saved cases into a table, one row for each case.

    Columns with several values in a case (such as "panel_judges" and
    "citations_case") are text, with "; " between the values. The
    `split_values` technique (`coders.SplitValues`) turns them into lists or
    into a column for each value.

    Args:
        files: a folder of saved cases (searched with its subfolders), or the
            paths of saved cases.
        source: where the cases came from: "court_listener" (the default) or
            "lexis_nexis".
        rulebooks: names of rulebooks (such as "federal") or paths to CSV
            files or folders of them. Defaults to
            `options._DEFAULT_JURISDICTION`.
        keep_text: whether to keep the text of the opinions in the table.
            Defaults to `False`.
        limit: most cases to parse, for trying out rules. Defaults to `None`
            (every case).
        workers: number of processes to parse with. Defaults to 1.

    Raises:
        ValueError: if `source` is not in `SOURCES`.

    Returns:
        The table, labeled by each case's id ("case_id"). A case that cannot
            be read is left out, with a warning.

    """
    if source not in SOURCES:
        message = f'source must be one of {list(SOURCES)}, not {source!r}'
        raise ValueError(message)
    if isinstance(files, str | pathlib.Path):
        paths = find_files(files, source)
    else:
        paths = [pathlib.Path(p) for p in files]
    if limit is not None:
        paths = paths[:limit]
    parser = Parser.create(rulebooks, keep_text = keep_text)
    labels: list[str] = []
    tables: list[pd.DataFrame] = []
    failures = 0
    outcomes: list[Any] = []
    for chunk_outcomes, table in _parse_all(parser, paths, source, workers):
        outcomes.extend(chunk_outcomes)
        tables.append(table)
    taken: set[str] = set()
    for path, outcome in zip(paths, outcomes, strict = True):
        if isinstance(outcome, BaseException):
            failures += 1
            logger.warning('%s could not be parsed: %s', path, outcome)
            continue
        unique, number = outcome, 1
        while unique in taken:
            number += 1
            unique = f'{outcome}_{number}'
        taken.add(unique)
        labels.append(unique)
    logger.info(
        'parsed %d cases (%d could not be parsed)', len(labels), failures)
    tables = [t for t in tables if not t.empty]
    data = pd.concat(tables, ignore_index = True) if tables else pd.DataFrame()
    data.index = pd.Index(labels, name = 'case_id')
    return cases.tidy(data)


""" Private Functions """


def _apply(
    rulebook: amos.parsers.Rulebook,
    sections: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Applies a rulebook to a table of sections of text.

    A section that the rules search but no case has is added as missing
    text, so that its rules find nothing rather than raising an error.

    Args:
        rulebook: the rules.
        sections: the sections of each case, a column for each.

    Returns:
        The sections with every column that the rules made or changed, and
            a table of the columns that the rules made.

    """
    missing = [c for c in rulebook.columns if c not in sections.columns]
    if missing:
        blank = pd.DataFrame(
            {c: pd.Series(None, index = sections.index, dtype = 'str')
             for c in missing})
        sections = pd.concat([sections, blank], axis = 1)
    result = rulebook.apply(sections)
    names = set(rulebook.names)
    made = [
        c for c in result.columns if c not in sections.columns or c in names]
    return result, result[made]


def _count(table: pd.DataFrame, column: str) -> pd.Series:
    """Returns the number of values in each row of a column of `table`.

    Args:
        table: parsed cases.
        column: a column with several values in each row: lists, or text
            with `cases._SEPARATOR` between them.

    Returns:
        The number of values in each row (0 if the column is missing).

    """
    if column not in table.columns:
        return pd.Series(0, index = table.index, dtype = 'int64')
    return table[column].map(
        lambda v: len(v) if isinstance(v, list | tuple)
        else 0 if _is_missing(v) or not str(v)
        else len(str(v).split(cases._SEPARATOR))).astype('int64')


def _derive(table: pd.DataFrame, sections: pd.DataFrame) -> pd.DataFrame:
    """Adds columns that summarize others to a table of parsed cases.

    The columns are "author" (the first of "authors", unless the case's
    metadata already gave one), "panel_size" (the number of judges named, or
    of CourtListener's panel ids if there are more of them), "concurrences"
    and "dissents" (the number of judges who concurred or dissented), and
    "word_count" (the number of words in the opinions). They are added all
    at once, since inserting columns one at a time into a table of hundreds
    of columns fragments it.

    Args:
        table: parsed cases.
        sections: their sections of text, after the rules were applied.

    Returns:
        The table, with the new columns.

    """
    if 'authors' in table.columns:
        first = table['authors'].map(
            lambda v: None if _is_missing(v) or not str(v)
            else str(v).split(cases._SEPARATOR)[0])
    else:
        first = pd.Series(None, index = table.index, dtype = object)
    if 'author' in table.columns:
        first = table['author'].combine_first(first)
    if 'opinion' in sections.columns:
        words = sections['opinion'].str.count(r'\S+').fillna(0).astype('int64')
    else:
        words = pd.Series(0, index = table.index, dtype = 'int64')
    derived = pd.DataFrame({
        'author': first,
        'panel_size': np.maximum(
            _count(table, 'panel_judges'), _count(table, 'panel_ids')),
        'concurrences': _count(table, 'concurring'),
        'dissents': _count(table, 'dissenting'),
        'word_count': words}, index = table.index)
    kept = table.drop(columns = [c for c in derived if c in table.columns])
    return pd.concat([kept, derived], axis = 1)


def _is_missing(value: Any) -> bool:
    """Returns whether a value of a table is missing.

    Args:
        value: a value, which may be a list.

    Returns:
        Whether it is `None` or another missing value (such as `NaN`). A
            list is never missing.

    """
    return not isinstance(value, list | tuple | dict) and bool(pd.isna(value))


def _parse_all(
    parser: Parser,
    paths: Sequence[pathlib.Path],
    source: str,
    workers: int) -> list[tuple[list[Any], pd.DataFrame]]:
    """Parses each saved case, in one process or several.

    The cases are split into chunks of `options._CHUNK_SIZE`, and progress is
    logged after each chunk. With one worker (or one chunk), the chunks are
    parsed in this process. Otherwise, each chunk is a task for a pool of
    `workers` processes, since a task for each case overwhelms the pool when
    there are hundreds of thousands of them.

    Args:
        parser: the parser to use. It is copied to each process with each
            chunk.
        paths: the paths of the saved cases.
        source: the name of their source, such as "court_listener".
        workers: number of processes to parse with.

    Returns:
        The outcomes and table of each chunk, in order (see `_parse_chunk`).

    """
    size = max(options._CHUNK_SIZE, 1)
    chunks = [paths[start:start + size] for start in range(0, len(paths), size)]
    results: list[tuple[list[Any], pd.DataFrame]] = []
    done = 0
    for outcomes, table in _parse_chunks(parser, chunks, source, workers):
        results.append((outcomes, table))
        done += len(outcomes)
        logger.info('%d of %d cases parsed', done, len(paths))
    return results


def _parse_chunk(
    parser: Parser,
    paths: Sequence[pathlib.Path],
    source: str) -> tuple[list[Any], pd.DataFrame]:
    """Reads a chunk of saved cases and parses them together.

    A case that cannot be read does not stop the others: the error takes the
    place of the case's outcome. If parsing the cases fails, that error takes
    the place of every case's outcome.

    Args:
        parser: the parser to use.
        paths: the paths of the saved cases.
        source: the name of their source, such as "court_listener".

    Returns:
        For each path, in order, the case's id or the error that reading or
            parsing it raised, and a table with a row for each case that was
            parsed, in order.

    """
    outcomes: list[Any] = []
    read: list[cases.Case] = []
    for path in paths:
        try:
            case = SOURCES[source].read(path)
        except Exception as error:  # noqa: BLE001
            outcomes.append(error)
            continue
        read.append(case)
        outcomes.append(case.id)
    try:
        table = parser.parse_cases(read)
    except Exception as error:  # noqa: BLE001
        failed = [o if isinstance(o, BaseException) else error for o in outcomes]
        return failed, pd.DataFrame()
    return outcomes, table


def _parse_chunks(
    parser: Parser,
    chunks: Sequence[Sequence[pathlib.Path]],
    source: str,
    workers: int) -> Iterator[tuple[list[Any], pd.DataFrame]]:
    """Parses chunks of saved cases, in one process or several.

    If a process fails on a chunk as a whole (for instance, because it
    stopped), that error takes the place of each of the chunk's outcomes.

    Args:
        parser: the parser to use. It is copied to each process with each
            chunk.
        chunks: the paths of the saved cases, in chunks.
        source: the name of their source, such as "court_listener".
        workers: number of processes to parse with.

    Yields:
        tuple[list[Any], pd.DataFrame]: the outcomes and table of each chunk
            (see `_parse_chunk`), in order.

    """
    if workers <= 1 or len(chunks) <= 1:
        for chunk in chunks:
            yield _parse_chunk(parser, chunk, source)
        return
    with concurrent.futures.ProcessPoolExecutor(max_workers = workers) as pool:
        futures = [
            pool.submit(_parse_chunk, parser, chunk, source)
            for chunk in chunks]
        for chunk, future in zip(chunks, futures, strict = True):
            try:
                yield future.result()
            except Exception as error:  # noqa: BLE001
                yield [error] * len(chunk), pd.DataFrame()
