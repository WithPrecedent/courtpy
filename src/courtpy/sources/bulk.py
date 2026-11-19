"""Extracts cases from CourtListener's bulk data.

CourtListener publishes its whole database as compressed CSV files every
three months (on the last day of March, June, September, and December), in a
public bucket that needs no API key and has no limits on requests:
https://com-courtlistener-storage.s3-us-west-2.amazonaws.com/list.html?prefix=bulk-data/

Five files hold what courtpy needs, and every one is always read, so that
each case is put in the court of its docket:

| File | Size (2026) | Holds |
| --- | --- | --- |
| courts | < 1 MB | Each court's name and jurisdiction. |
| dockets | about 5 GB | Each case's court, docket number, and dates. |
| opinion-clusters | about 2.5 GB | Each decision's parties, judges, date, and status. |
| citations | about 130 MB | Each decision's reporter citations. |
| opinions | about 55 GB | The text of each opinion. |

`BulkData.extract` reads them in that order, keeps the cases of the courts and
dates asked for, and saves each case in the same form as the API client does
(see `courtpy.courtlistener`), so the same parser reads both. Every case is
saved with its whole docket (all of its fields but those in
`options._DOCKET_SKIPPED`), so the dockets file is read twice: first to find
which dockets belong to the courts, and again, once the cases are known, to
keep the dockets of those cases alone. Reading the opinions file takes hours,
so it is worth extracting every court and year you may need at once.

The files are read with `amos.loaders.read_chunks`, which decompresses and
parses them on every core and keeps only the rows asked for. By default, they
are downloaded first (to a folder outside of any project, see
`courtpy.utilities.data_folder`) with `amos.loaders.download_file` and kept,
so that they can be used again and an interrupted download resumes. With
`stream = True`, they are read straight from the bucket instead, which needs
no disk space but starts over if the connection fails.

Contents:
    BulkData: lists, downloads, and extracts cases from the bulk data.
    BulkDownload: extracts cases from the bulk data ("download = bulk").
    logger: the module's logger, which reports the progress of downloads and
        of reading the files.

"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import pathlib
import re
import sys
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any, ClassVar
from xml.etree import ElementTree as ET

import amos
import pandas as pd

from ..core import options, utilities
from . import base, courtlistener

logger = logging.getLogger(__name__)
_KINDS: tuple[str, ...] = (
    'courts', 'dockets', 'opinion-clusters', 'citations', 'opinions')
_BUFFER_BYTES: int = 200 * 1024 * 1024
_DATE: re.Pattern[str] = re.compile(r'(\d{4}-\d{2}-\d{2})\.csv\.bz2$')
# "source" is left out because it is a number in the dockets file but letters
# in the opinion clusters file.
_INTEGERS: frozenset[str] = frozenset({
    'id', 'cluster_id', 'docket_id', 'author_id', 'citation_count',
    'ordering_key', 'page_count', 'scdb_decision_direction',
    'scdb_votes_majority', 'scdb_votes_minority', 'assigned_to_id',
    'referred_to_id', 'idb_data_id', 'originating_court_information_id',
    'parent_docket_id', 'federal_defendant_number'})
_BOOLEANS: frozenset[str] = frozenset({
    'per_curiam', 'blocked', 'date_filed_is_approximate', 'extracted_by_ocr'})
_CLUSTER_SKIPPED: frozenset[str] = frozenset({
    'date_created', 'date_modified', 'filepath_json_harvard',
    'filepath_pdf_harvard', 'filepath_pdf_scan', 'filepath_xml_scan'})


@dataclasses.dataclass
class BulkData:
    """Lists, downloads, and extracts cases from CourtListener's bulk data.

    Args:
        folder: folder to keep the downloaded bulk files in. Defaults to
            `None`, in which case "bulk" in `utilities.data_folder()` is used.
        date: the date of the files to use, as YYYY-MM-DD. Defaults to `None`,
            in which case the newest files are used.
        stream: whether to read the files straight from the bucket instead
            of downloading them. Defaults to `False`.
        base_url: address of the bucket. Defaults to `options._BULK_URL`.
        timeout: seconds to wait for a response. Defaults to
            `options._TIMEOUT`.
        session: an object with a `get` method like a
            `requests.Session`. Defaults to `None`, in which case a
            `requests.Session` that identifies courtpy is made.

    """

    folder: pathlib.Path | str | None = None
    date: str | None = None
    stream: bool = False
    base_url: str = options._BULK_URL
    timeout: float = options._TIMEOUT
    session: Any = dataclasses.field(default = None, repr = False)

    """ Initialization Methods """

    def __post_init__(self) -> None:
        """Sets the folder and session.

        If no `folder` was passed, "bulk" in `utilities.data_folder()` is used,
        and `folder` is made a `pathlib.Path`. If no `session` was passed, a
        `requests.Session` is made that identifies courtpy.

        """
        if self.folder is None:
            self.folder = utilities.data_folder() / 'bulk'
        self.folder = pathlib.Path(self.folder)
        self.session = utilities.open_session(self.session)

    """ Public Methods """

    def available(self, kind: str = 'opinions') -> list[str]:
        """Returns the dates of the files of one kind in the bucket.

        Args:
            kind: "courts", "dockets", "opinion-clusters", "citations", or
                "opinions". Defaults to "opinions".

        Returns:
            The dates, from oldest to newest.

        """
        dates = []
        for key in self._list(f'{options._BULK_PREFIX}{kind}-'):
            match = _DATE.search(key)
            # Skips files whose kind only starts with `kind` (such as
            # "opinions-cited" for "opinions").
            if match and key == (
                f'{options._BULK_PREFIX}{kind}-{match.group(1)}.csv.bz2'):
                dates.append(match.group(1))
        return sorted(set(dates))

    def extract(
        self,
        courts: str | Iterable[str],
        start_date: str | None = None,
        end_date: str | None = None,
        folder: pathlib.Path | str = 'court_listener',
        *,
        max_cases: int | None = None,
        overwrite: bool = False) -> list[pathlib.Path]:
        """Saves the cases of `courts` filed between two dates.

        Args:
            courts: CourtListener court ids (such as "ca1") or names of groups
                of them (such as "federal_appellate").
            start_date: earliest date filed, as YYYY-MM-DD. Defaults to `None`
                (no earliest date).
            end_date: latest date filed, as YYYY-MM-DD. Defaults to `None` (no
                latest date).
            folder: folder to save the cases in. Defaults to "court_listener".
            max_cases: most cases to save. Defaults to `None` (every case).
            overwrite: whether to replace cases that were already saved with
                their opinions. Defaults to `False`.

        Returns:
            The paths of the cases saved (or updated) by this call.

        """
        folder = pathlib.Path(folder)
        wanted = utilities.expand_courts(courts)
        date = self.resolve_date()
        logger.info('extracting cases from the bulk data of %s', date)
        court_records = self._courts(wanted)
        docket_courts = self._docket_courts(set(wanted))
        clusters = self._clusters(
            docket_courts, start_date, end_date, max_cases)
        dockets = self._dockets(
            {int(c['docket_id']) for c in clusters.values()})
        citations = self._citations(set(clusters))
        paths: dict[int, pathlib.Path] = {}
        for cluster_id, cluster in clusters.items():
            docket = dockets[int(cluster['docket_id'])]
            court = docket_courts[int(cluster['docket_id'])]
            path = courtlistener.case_path(folder, court, cluster_id)
            if not overwrite and courtlistener.is_complete(path):
                continue
            courtlistener.save_case(path, {
                'source': 'court_listener',
                'bulk_date': date,
                'court': court_records.get(court, {'id': court}),
                'cluster': cluster,
                'docket': docket,
                'citations': citations.get(cluster_id, []),
                'opinions': []})
            paths[cluster_id] = path
        logger.info('saved %d cases; now adding their opinions', len(paths))
        if paths:
            self._opinions(paths)
        return list(paths.values())

    def fetch(self, kind: str) -> pathlib.Path:
        """Downloads one bulk file, resuming a download that was interrupted.

        The file is downloaded with `amos.loaders.download_file`, which
        writes it beside its path (with ".part" added) until it is whole, so
        a file in `folder` is always complete.

        Args:
            kind: "courts", "dockets", "opinion-clusters", "citations", or
                "opinions".

        Raises:
            OSError: if the download stopped before the whole file arrived
                (run it again to resume).
            requests.HTTPError: if the file cannot be downloaded.

        Returns:
            The path of the downloaded file.

        """
        name = self._name(kind)
        assert isinstance(self.folder, pathlib.Path)  # noqa: S101
        path = self.folder / name
        if not path.is_file():
            logger.info('downloading %s to %s', name, self.folder)
        return amos.loaders.download_file(
            self._url(kind),
            path,
            timeout = self.timeout,
            session = self.session,
            resume = True)

    def resolve_date(self) -> str:
        """Returns `date`, finding the newest complete set of files if needed.

        Returns:
            The date of the files to use, as YYYY-MM-DD.

        Raises:
            LookupError: if no date has every kind of file that courtpy needs.

        """
        if self.date is None:
            common: set[str] | None = None
            for kind in _KINDS:
                dates = set(self.available(kind))
                common = dates if common is None else common & dates
            if not common:
                message = 'no date in the bulk data has every file needed'
                raise LookupError(message)
            self.date = max(common)
        return self.date

    def chunks(
        self,
        kind: str,
        *,
        columns: Sequence[str] | None = None,
        keep: Mapping[str, Any] | None = None) -> Iterator[pd.DataFrame]:
        """Yields chosen rows and columns of one bulk file, a chunk at a time.

        The file is read with `amos.loaders.read_chunks`, which parses and
        decompresses it on every core and finds the rows in `keep` before
        any of their text becomes Python objects. If `stream` is true, the
        file is read from the bucket as it arrives, without being saved.
        Otherwise, it is downloaded first (or found in `folder`) with
        `fetch`.

        Args:
            kind: "courts", "dockets", "opinion-clusters", "citations", or
                "opinions".
            columns: the columns to return. Defaults to `None`, which
                returns every column.
            keep: the values to keep of each of some columns, such as
                `{'court_id': ['ca1']}` (see `amos.loaders.read_chunks`).
                Defaults to `None`, which keeps every row.

        Yields:
            pd.DataFrame: the rows of each chunk that are kept, with every
                value as text. Missing values are empty `str`s.

        """
        source = self._url(kind) if self.stream else self.fetch(kind)
        yield from amos.loaders.read_chunks(
            source,
            columns = columns,
            keep = keep,
            double_quote = False,
            escape_char = '\\',
            session = self.session,
            timeout = self.timeout)

    def rows(
        self,
        kind: str,
        *,
        columns: Sequence[str] | None = None,
        keep: Mapping[str, Any] | None = None) -> Iterator[dict[str, str]]:
        """Yields chosen rows of one bulk file.

        Args:
            kind: "courts", "dockets", "opinion-clusters", "citations", or
                "opinions".
            columns: the columns to return. Defaults to `None`, which
                returns every column.
            keep: the values to keep of each of some columns (see `chunks`).
                Defaults to `None`, which keeps every row.

        Yields:
            dict[str, str]: each row, mapping column names to text. Missing
                values are empty `str`s.

        """
        for chunk in self.chunks(kind, columns = columns, keep = keep):
            for row in chunk.to_dict('records'):
                yield {str(key): value for key, value in row.items()}

    """ Private Methods """

    def _citations(self, cluster_ids: set[int]) -> dict[int, list[str]]:
        """Returns the citations of the clusters in `cluster_ids`.

        The citations file is read only if there are clusters to look for.

        Args:
            cluster_ids: ids of the opinion clusters (cases) being extracted.

        Returns:
            The citations of each cluster, as text such as "950 F.3d 12", by
                its id. Clusters without citations are left out.

        """
        found: dict[int, list[str]] = {}
        if not cluster_ids:
            return found
        kept = {'cluster_id': cluster_ids}
        for row in self.rows('citations', keep = kept):
            cluster_id = _integer(row.get('cluster_id'))
            if cluster_id is not None:
                found.setdefault(cluster_id, []).extend(
                    courtlistener.citation_strings([row]))
        return found

    def _clusters(
        self,
        dockets: Mapping[int, Any],
        start_date: str | None,
        end_date: str | None,
        max_cases: int | None) -> dict[int, dict[str, Any]]:
        """Returns the clusters of `dockets` filed between two dates.

        The clusters file is read only if there are dockets to look for, and
        reading stops once `max_cases` clusters are found. Dates are compared
        as text, which works because they are written as YYYY-MM-DD.

        Args:
            dockets: the dockets of the courts being extracted, by their ids
                (only the ids are used).
            start_date: earliest date filed, as YYYY-MM-DD, or `None` for no
                earliest date.
            end_date: latest date filed, as YYYY-MM-DD, or `None` for no latest
                date.
            max_cases: most clusters to find, or `None` for every cluster.

        Returns:
            Each cluster (converted with `_convert`, without the columns in
                `_CLUSTER_SKIPPED`), by its id.

        """
        found: dict[int, dict[str, Any]] = {}
        if not dockets:
            return found
        kept = {'docket_id': dockets.keys()}
        for row in self.rows('opinion-clusters', keep = kept):
            filed = row.get('date_filed') or ''
            if (start_date and filed < start_date) or (
                end_date and filed > end_date):
                continue
            cluster = _convert(row)
            for column in _CLUSTER_SKIPPED:
                cluster.pop(column, None)
            found[int(cluster['id'])] = cluster
            if max_cases is not None and len(found) >= max_cases:
                break
        logger.info('found %d cases', len(found))
        return found

    def _courts(self, wanted: list[str]) -> dict[str, dict[str, Any]]:
        """Returns information about the courts in `wanted`.

        A warning is logged for any court in `wanted` that is not in the
        courts file (usually a misspelled court id).

        Args:
            wanted: CourtListener court ids.

        Returns:
            The "id", "full_name", "short_name", "citation_string", and
                "jurisdiction" of each court that was found, by its id.

        """
        kept = (
            'id', 'full_name', 'short_name', 'citation_string', 'jurisdiction')
        found = {
            row['id']: {k: row.get(k) for k in kept}
            for row in self.rows('courts', keep = {'id': wanted})}
        missing = [c for c in wanted if c not in found]
        if missing:
            logger.warning('these courts are not in the bulk data: %s', missing)
        return found

    def _docket_courts(self, wanted: set[str]) -> dict[int, str]:
        """Returns the court of each docket of the courts in `wanted`.

        Only the court is kept, because a court has far more dockets than
        cases with opinions, and all of their fields would not fit in memory
        for large courts. `_dockets` reads the fields of the dockets that are
        needed once the cases are known.

        Args:
            wanted: CourtListener court ids.

        Returns:
            The court id of each docket of those courts, by the docket's id.

        """
        found: dict[int, str] = {}
        rows = self.rows(
            'dockets', columns = ['id', 'court_id'],
            keep = {'court_id': wanted})
        for row in rows:
            court = row['court_id']
            docket_id = _integer(row['id'])
            if docket_id is not None:
                # One `str` is shared by every docket of a court.
                found[docket_id] = sys.intern(court)
        logger.info('found %d dockets', len(found))
        return found

    def _dockets(self, docket_ids: set[int]) -> dict[int, dict[str, Any]]:
        """Returns the dockets in `docket_ids`.

        The dockets file is read only if there are dockets to look for, and
        reading stops once they are all found.

        Args:
            docket_ids: ids of the dockets of the cases being extracted.

        Returns:
            Each docket (converted with `_convert`, without the columns in
                `options._DOCKET_SKIPPED`), by its id.

        """
        found: dict[int, dict[str, Any]] = {}
        if not docket_ids:
            return found
        for row in self.rows('dockets', keep = {'id': docket_ids}):
            docket_id = int(row['id'])
            docket = _convert(row)
            for column in options._DOCKET_SKIPPED:
                docket.pop(column, None)
            found[docket_id] = docket
            if len(found) == len(docket_ids):
                break
        logger.info('read %d dockets', len(found))
        return found

    def _list(self, prefix: str) -> list[str]:
        """Returns the keys in the bucket that start with `prefix`.

        The bucket is listed with Amazon S3's "ListObjectsV2" request, which
        returns at most 1,000 keys at a time as XML, with a token for the next
        part of the list when there are more.

        Args:
            prefix: the start of the keys (file paths) to list, such as
                "bulk-data/opinions-".

        Raises:
            requests.HTTPError: if the bucket cannot be listed.

        Returns:
            The keys, in the order the bucket lists them.

        """
        keys: list[str] = []
        token = None
        while True:
            params = {'list-type': '2', 'prefix': prefix}
            if token:
                params['continuation-token'] = token
            response = self.session.get(
                self.base_url, params = params, timeout = self.timeout)
            response.raise_for_status()
            # The listing comes from the bucket's own server.
            root = ET.fromstring(response.content)  # noqa: S314
            namespace = (
                root.tag.split('}')[0] + '}' if root.tag.startswith('{')
                else '')
            keys.extend(
                element.text or ''
                for element in root.iter(f'{namespace}Key'))
            truncated = root.findtext(f'{namespace}IsTruncated') == 'true'
            token = root.findtext(f'{namespace}NextContinuationToken')
            if not truncated or not token:
                return keys

    def _name(self, kind: str) -> str:
        """Returns the name of the bulk file of one kind.

        Args:
            kind: one of `_KINDS`.

        Raises:
            ValueError: if `kind` is not one of `_KINDS`.

        Returns:
            The file's name, such as "opinions-2026-09-30.csv.bz2", for the date
                from `resolve_date`.

        """
        if kind not in _KINDS:
            message = f'kind must be one of {list(_KINDS)}, not {kind!r}'
            raise ValueError(message)
        return f'{kind}-{self.resolve_date()}.csv.bz2'

    def _opinions(self, paths: Mapping[int, pathlib.Path]) -> None:
        """Adds the opinions of the cases in `paths` to their files.

        The opinions file is not sorted by case, so a case's opinions can be
        anywhere in it. Opinions are held in memory (with one field of text
        each, see `courtlistener.slim_opinion`) until their text reaches
        `_BUFFER_BYTES`, and then written to their cases, which keeps memory
        use bounded without rewriting a case's file for every opinion.

        Args:
            paths: the path of each saved case, by its cluster id.

        """
        buffer: dict[int, list[dict[str, Any]]] = {}
        size = 0
        for row in self.rows('opinions', keep = {'cluster_id': paths.keys()}):
            cluster_id = int(row['cluster_id'])
            opinion = courtlistener.slim_opinion(_convert(row))
            buffer.setdefault(cluster_id, []).append(opinion)
            size += sum(len(v) for v in opinion.values() if isinstance(v, str))
            if size >= _BUFFER_BYTES:
                _flush(buffer, paths)
                size = 0
        _flush(buffer, paths)

    def _url(self, kind: str) -> str:
        """Returns the address of the bulk file of one kind.

        Args:
            kind: one of `_KINDS`.

        Raises:
            ValueError: if `kind` is not one of `_KINDS`.

        Returns:
            The address of the file in the bucket.

        """
        return f'{self.base_url}{options._BULK_PREFIX}{self._name(kind)}'


@dataclasses.dataclass
class BulkDownload(base.Download):
    """Extracts cases from CourtListener's bulk data (no key needed).

    It is `BulkData.extract`. "download = true" in settings also means it.

    """

    name: ClassVar[str] = 'bulk'
    aliases: ClassVar[tuple[str, ...]] = ('true', 'yes', '1')

    """ Class Methods """

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Adds "--bulk-folder", "--bulk-date", and "--stream".

        Args:
            parser: the parser of "courtpy download bulk".

        """
        parser.add_argument(
            '--bulk-folder', help = 'folder to keep the bulk files in')
        parser.add_argument(
            '--bulk-date', help = 'date of the files (default: newest)')
        parser.add_argument(
            '--stream', action = 'store_true',
            help = 'read the files without saving them')

    """ Required Methods """

    def download(
        self,
        folder: pathlib.Path,
        *,
        courts: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        max_cases: int | None = None,
        overwrite: bool = False,
        bulk_folder: Any = None,
        bulk_date: Any = None,
        stream: Any = False,
        **options: Any) -> list[pathlib.Path]:
        """Extracts the cases of `courts` filed between two dates.

        Args:
            folder: the folder to save the cases in.
            courts: CourtListener court ids. Defaults to `None`, which raises
                an error.
            start_date: earliest date filed, as YYYY-MM-DD. Defaults to
                `None`.
            end_date: latest date filed, as YYYY-MM-DD. Defaults to `None`.
            max_cases: most cases to save. Defaults to `None` (every case).
            overwrite: whether to replace cases that were already saved.
                Defaults to `False`.
            bulk_folder: the folder to keep the bulk files in, found with
                `locate`. Defaults to `None`, in which case "bulk" in
                `utilities.data_folder()` is used.
            bulk_date: the date of the files to use. Defaults to `None` (the
                newest).
            stream: whether to read the files without saving them. Defaults
                to `False`.
            **options: options of other ways to download, which are ignored.

        Raises:
            ValueError: if no courts are named.

        Returns:
            The paths of the cases saved (or updated).

        """
        data = BulkData(
            folder = self.locate(bulk_folder) if bulk_folder else None,
            date = utilities.to_date(bulk_date),
            stream = utilities.to_bool(stream))
        return data.extract(
            courts = courts or [], start_date = start_date,
            end_date = end_date, folder = folder, max_cases = max_cases,
            overwrite = overwrite)


""" Private Functions """


def _convert(row: Mapping[str, str]) -> dict[str, Any]:
    """Returns a row of a bulk file with numbers, booleans, and missing values.

    Args:
        row: the row, with every value as text.

    Returns:
        The row, with ids and counts as `int`s, "t" and "f" as `bool`s, and
            empty text as `None`.

    """
    converted: dict[str, Any] = {}
    for key, value in row.items():
        if value == '':
            converted[key] = None
        elif key in _INTEGERS:
            converted[key] = _integer(value)
        elif key in _BOOLEANS:
            converted[key] = value == 't'
        else:
            converted[key] = value
    return converted


def _flush(
    buffer: dict[int, list[dict[str, Any]]],
    paths: Mapping[int, pathlib.Path]) -> None:
    """Writes buffered opinions to their cases and empties the buffer.

    Args:
        buffer: opinions that have not been written yet, by the cluster id of
            their case. It is emptied.
        paths: the path of each saved case, by its cluster id.

    """
    for cluster_id, opinions in buffer.items():
        courtlistener.add_opinions(paths[cluster_id], opinions)
    buffer.clear()


def _integer(value: Any) -> int | None:
    """Returns `value` as an `int`, if it is a whole number.

    Args:
        value: a value from a bulk file, usually text such as "4567890".

    Returns:
        The number, or `None` if `value` is missing or is not a whole number.

    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
