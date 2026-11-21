"""Downloads court opinions from CourtListener and reads them.

CourtListener (https://www.courtlistener.com) is a free legal research site
run by the Free Law Project. `CourtListener` downloads its opinions in two
ways (its "method"):

* "bulk" (the default) extracts them from the bulk data files, which need no
  key and have no limits, but are very large and are updated every three
  months.
* "api" downloads them with the REST API, which needs an API key (see
  `courtpy.secrets`). It is best for small or very recent sets of cases,
  because CourtListener limits how many requests an account can make (a free
  account can make 5 a minute, 50 an hour, and 125 a day, as of 2026). The
  client waits when asked to, saves its place, and resumes where it stopped
  when it is run again.

Both save each case as a JSON file named for its CourtListener cluster id, in
a folder named for its court (such as "courtlistener/ca1/4567890.json"),
which `read_case` turns into a `Case` for parsing.

The bulk data is published every three months (on the last day of March,
June, September, and December), in a public bucket:
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

They are read in that order, keeping the cases of the courts and dates asked
for, and each case is saved in the same form as the API's, so the same parser
reads both. Every case is saved with its whole docket (all of its fields but
those in `options._DOCKET_SKIPPED`), so the dockets file is read twice: first
to find which dockets belong to the courts, and again, once the cases are
known, to keep the dockets of those cases alone. Reading the opinions file
takes hours, so it is worth extracting every court and year you may need at
once.

The files are read with `amos.loaders.read_chunks`, which decompresses and
parses them on every core and keeps only the rows asked for. By default, they
are downloaded first (to a folder outside of any project, see
`courtpy.utilities.data_folder`) with `amos.loaders.download_file` and kept,
so that they can be used again and an interrupted download resumes. With
`stream = True`, they are read straight from the bucket instead, which needs
no disk space but starts over if the connection fails.

Contents:
    DOWNLOAD_METHODS: the ways that `CourtListener.download` can download.
    CourtListener: downloads cases from CourtListener's bulk data or API.
    CourtListenerSource: reads cases saved by `CourtListener`.
    CourtListenerError: raised when the API returns an error.
    RateLimitError: raised when the API asks for a longer pause than allowed.
    add_opinions: adds opinions to a saved case.
    case_path: returns the path of a saved case.
    citation_strings: returns citations as text.
    is_complete: returns whether a case was saved with its opinions.
    opinion_role: classifies an opinion as majority, concurrence, or dissent.
    opinion_text: returns the plain text of an opinion.
    read_case: reads a saved case for parsing.
    save_case: saves a case.
    slim_opinion: keeps one field of an opinion's text, to save space.
    logger: the module's logger, which reports the progress of downloads,
        of reading the bulk files, and pauses asked for by CourtListener.

"""

from __future__ import annotations

import dataclasses
import email.utils
import json
import logging
import pathlib
import re
import sys
import time
import urllib.parse
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any, ClassVar
from xml.etree import ElementTree as ET

import amos
import pandas as pd
import requests

from ..core import cases, options, secrets, utilities
from ..references import courts
from . import base

logger = logging.getLogger(__name__)
DOWNLOAD_METHODS: tuple[str, ...] = ('bulk', 'api')
_SITE: str = 'https://www.courtlistener.com'
_TEMPORARY: frozenset[int] = frozenset({500, 502, 503, 504})
_RETRIES: int = 4
_OPINION_KEPT: tuple[str, ...] = (
    'id', 'cluster_id', 'type', 'author_id', 'author_str', 'per_curiam',
    'joined_by_str', 'joined_by', 'ordering_key', 'download_url')
# "Concurrence in part" is checked before "dissent" and "concur", which it
# also contains. "unamimous" is CourtListener's own spelling of the type.
_ROLES: tuple[tuple[str, str], ...] = (
    ('concurrenceinpart', 'mixed'),
    ('in part', 'mixed'),
    ('dissent', 'dissent'),
    ('concur', 'concurrence'),
    ('combined', 'majority'),
    ('unanimous', 'majority'),
    ('unamimous', 'majority'),
    ('lead', 'majority'),
    ('plurality', 'majority'),
    ('onthemerits', 'majority'),
    ('on the merits', 'majority'),
    ('trialcourt', 'majority'),
    ('trial court', 'majority'))
_BULK_KINDS: tuple[str, ...] = (
    'courts', 'dockets', 'opinion-clusters', 'citations', 'opinions')
_BULK_BUFFER_BYTES: int = 200 * 1024 * 1024
_BULK_DATE: re.Pattern[str] = re.compile(r'(\d{4}-\d{2}-\d{2})\.csv\.bz2$')
# "source" is left out because it is a number in the dockets file but letters
# in the opinion clusters file.
_BULK_INTEGERS: frozenset[str] = frozenset({
    'id', 'cluster_id', 'docket_id', 'author_id', 'citation_count',
    'ordering_key', 'page_count', 'scdb_decision_direction',
    'scdb_votes_majority', 'scdb_votes_minority', 'assigned_to_id',
    'referred_to_id', 'idb_data_id', 'originating_court_information_id',
    'parent_docket_id', 'federal_defendant_number'})
_BULK_BOOLEANS: frozenset[str] = frozenset({
    'per_curiam', 'blocked', 'date_filed_is_approximate', 'extracted_by_ocr'})
_BULK_CLUSTER_SKIPPED: frozenset[str] = frozenset({
    'date_created', 'date_modified', 'filepath_json_harvard',
    'filepath_pdf_harvard', 'filepath_pdf_scan', 'filepath_xml_scan'})


class CourtListenerError(RuntimeError):
    """Raised when the CourtListener API returns an error."""


class RateLimitError(CourtListenerError):
    """Raised when the API asks for a longer pause than courtpy will wait.

    Its message says how long to wait and how to resume.

    Args:
        seconds: how long CourtListener asked courtpy to wait.

    """

    def __init__(self, seconds: float) -> None:  # noqa: D107
        self.seconds = seconds
        hours = seconds / 3600
        message = (
            f'CourtListener asked courtpy to wait {hours:.1f} hours before '
            f"making more requests (the account's limit was reached). Run "
            f'the same download again later: it resumes where it stopped. '
            f'The bulk data (method "bulk") has no limits.')
        super().__init__(message)


@dataclasses.dataclass
class CourtListener:
    """Downloads cases from CourtListener's bulk data or its REST API.

    `download` takes the "method" to download with: "bulk" (the default),
    which extracts the cases from the bulk data files and needs no key, or
    "api", which downloads them with the REST API (version 4).

    Every request to the API includes the API key, which is found with
    `courtpy.secrets.get_api_key` when the first request is made if it was
    not passed, so the bulk data can be used without a key. Requests to the
    API are spaced at least `min_interval` seconds apart. If CourtListener
    asks for a pause (an HTTP 429 response), the client waits as long as it
    is asked, up to `max_wait` seconds. A longer pause (such as the daily
    limit) raises a `RateLimitError`, and `download` can be run again later
    to resume.

    Args:
        api_key: a CourtListener API key. Defaults to `None`, in which case it
            is found with `courtpy.secrets.get_api_key` when it is needed.
        api_url: address of the API. Defaults to `options._API_URL`.
        bulk_url: address of the bucket of bulk data. Defaults to
            `options._BULK_URL`.
        bulk_folder: folder to keep the downloaded bulk files in. Defaults
            to `None`, in which case "bulk" in `utilities.data_folder()` is
            used.
        bulk_date: the date of the bulk files to use, as YYYY-MM-DD. Defaults
            to `None`, in which case the newest files are used (and it is set
            when they are found, see `resolve_bulk_date`).
        stream: whether to read the bulk files straight from the bucket
            instead of downloading them. Defaults to `False`.
        min_interval: fewest seconds between requests to the API. Defaults to
            `options._MIN_INTERVAL`.
        max_wait: most seconds to wait when the API asks for a pause.
            Defaults to `options._MAX_WAIT`.
        timeout: seconds to wait for a response. Defaults to
            `options._TIMEOUT`.
        session: an object with a `get` method like a `requests.Session`.
            Defaults to `None`, in which case a `requests.Session` that
            identifies courtpy is made.

    Attributes:
        requests_made: number of requests made to the API by this client.
        _courts: information about each court that has been looked up (see
            `court`), by its id, so that each court is asked for only once.
        _last_request: when the last request was made, from
            `time.monotonic`, so that the next one can wait until
            `min_interval` seconds have passed. It is 0 before the first
            request.

    """

    api_key: str | None = dataclasses.field(default = None, repr = False)
    api_url: str = options._API_URL
    bulk_url: str = options._BULK_URL
    bulk_folder: pathlib.Path | str | None = None
    bulk_date: str | None = None
    stream: bool = False
    min_interval: float = options._MIN_INTERVAL
    max_wait: float = options._MAX_WAIT
    timeout: float = options._TIMEOUT
    session: Any = dataclasses.field(default = None, repr = False)
    requests_made: int = dataclasses.field(default = 0, init = False)
    _last_request: float = dataclasses.field(
        default = 0.0, init = False, repr = False)
    _courts: dict[str, dict[str, Any]] = dataclasses.field(
        default_factory = dict, init = False, repr = False)

    """ Initialization Methods """

    def __post_init__(self) -> None:
        """Prepares the session.

        If no `session` was passed, a `requests.Session` that identifies
        courtpy is made. The API key is not looked for until the first
        request to the API (see `get`), and it is sent with requests to the
        API alone, never to the bucket of bulk data.

        """
        self.session = utilities.open_session(self.session)

    """ Public Methods """

    def bulk_dates(self, kind: str = 'opinions') -> list[str]:
        """Returns the dates of the bulk files of one kind in the bucket.

        Args:
            kind: "courts", "dockets", "opinion-clusters", "citations", or
                "opinions". Defaults to "opinions".

        Returns:
            The dates, from oldest to newest.

        """
        dates = []
        for key in self._list_bucket(f'{options._BULK_PREFIX}{kind}-'):
            match = _BULK_DATE.search(key)
            # Skips files whose kind only starts with `kind` (such as
            # "opinions-cited" for "opinions").
            if match and key == (
                f'{options._BULK_PREFIX}{kind}-{match.group(1)}.csv.bz2'):
                dates.append(match.group(1))
        return sorted(set(dates))

    def court(self, court: str) -> dict[str, Any]:
        """Returns information about a court.

        Args:
            court: a CourtListener court id, such as "ca1".

        Returns:
            The court's "id", "full_name", "short_name", "citation_string",
                and "jurisdiction" (such as "F" for federal appellate courts).

        """
        if court not in self._courts:
            fields = 'id,full_name,short_name,citation_string,jurisdiction'
            self._courts[court] = self.get(
                f'courts/{court}/', {'fields': fields})
        return self._courts[court]

    def download(
        self,
        courts: str | Iterable[str],
        start_date: str | None = None,
        end_date: str | None = None,
        folder: pathlib.Path | str = 'courtlistener',
        *,
        method: str = 'bulk',
        max_cases: int | None = None,
        dockets: bool = False,
        refresh: bool = False) -> list[pathlib.Path]:
        """Downloads the cases of `courts` filed between two dates.

        With "bulk", the bulk files are read in turn (see the module's
        documentation), and the cases that were already saved with their
        opinions are skipped. Every case is saved with its docket.

        With "api", each page of cases (opinion clusters) takes one request,
        and their opinions take one more (or more, if they have many
        opinions). Cases that were already saved (with their opinions) are
        skipped, and the place in each court's list of cases is saved, so
        running a download again resumes it. Running a finished download
        again takes one request for each court and saves any cases added to
        CourtListener since.

        Args:
            courts: CourtListener court ids (such as "ca1") or names of groups
                of them (such as "federal_appellate").
            start_date: earliest date filed, as YYYY-MM-DD. Defaults to `None`
                (no earliest date).
            end_date: latest date filed, as YYYY-MM-DD. Defaults to `None` (no
                latest date).
            folder: folder to save the cases in. Defaults to "courtlistener".
            method: "bulk" or "api" (see `DOWNLOAD_METHODS`), in any case.
                Defaults to "bulk".
            max_cases: most cases to save: in all with "bulk", and in each
                court with "api". Defaults to `None` (every case).
            dockets: with "api", whether to also download each case's docket
                (every field but those in `options._DOCKET_SKIPPED`, such as
                its docket number, dates, and the court appealed from). This
                takes one more request for each case. Defaults to `False`.
                The bulk data always includes the docket.
            refresh: whether to download cases that were already saved.
                Defaults to `False`.

        Raises:
            ValueError: if `method` is not one of `DOWNLOAD_METHODS`, or if no
                courts are named.
            RateLimitError: if CourtListener asks for a pause longer than
                `max_wait`. What was downloaded is kept.

        Returns:
            The paths of the cases saved (or updated) in this run.

        """
        chosen = str(method).strip().lower()
        if chosen not in DOWNLOAD_METHODS:
            names = ' or '.join(f'"{m}"' for m in DOWNLOAD_METHODS)
            message = f'method must be {names}, not {method!r}'
            raise ValueError(message)
        wanted = utilities.expand_courts(courts)
        folder = pathlib.Path(folder)
        if chosen == 'bulk':
            return self._download_from_bulk_data(
                wanted, start_date, end_date, folder,
                max_cases = max_cases, refresh = refresh)
        saved: list[pathlib.Path] = []
        for court in wanted:
            saved.extend(self._download_court(
                court, start_date, end_date, folder,
                max_cases = max_cases, dockets = dockets,
                refresh = refresh))
        logger.info(
            'saved %d cases in %s with %d requests', len(saved), folder,
            self.requests_made)
        return saved

    def download_case(
        self,
        cluster_id: int | str,
        folder: pathlib.Path | str = 'courtlistener') -> pathlib.Path:
        """Downloads one case by its CourtListener cluster id.

        This takes four requests: the case, its opinions, its docket (which
        names its court), and its court (unless another case from the same
        court was downloaded by this client).

        Args:
            cluster_id: the id of the opinion cluster (the number in the
                case's CourtListener address, after "/opinion/").
            folder: folder to save the case in. Defaults to "courtlistener".

        Returns:
            The path of the saved case.

        """
        cluster = self.get(f'clusters/{cluster_id}/')
        opinions = self._opinions_of([int(cluster['id'])])
        return self._save(
            cluster, opinions.get(int(cluster['id']), []), pathlib.Path(folder),
            court = None, docket = True)

    def fetch_bulk_file(self, kind: str) -> pathlib.Path:
        """Downloads one bulk file, resuming a download that was interrupted.

        The file is downloaded with `amos.loaders.download_file`, which
        writes it beside its path (with ".part" added) until it is whole, so
        a file in the bulk folder is always complete.

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
        name = self._bulk_name(kind)
        folder = self._bulk_folder_path()
        path = folder / name
        if not path.is_file():
            logger.info('downloading %s to %s', name, folder)
        return amos.loaders.download_file(
            self._bulk_file_url(kind),
            path,
            timeout = self.timeout,
            session = self.session,
            resume = True)

    def get(
        self,
        path: str,
        params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Returns the JSON response of one request to the API.

        Args:
            path: a path in the API (such as "clusters/") or a full address
                (such as the "next" page of a response).
            params: query parameters. Defaults to `None`.

        Raises:
            CourtListenerError: if the API returns an error, rejects the key,
                or cannot be reached after several tries.
            MissingAPIKeyError: if no key was passed and none can be found
                (see `courtpy.secrets.get_api_key`).
            RateLimitError: if the API asks for a pause longer than
                `max_wait`.

        Returns:
            The decoded JSON.

        """
        url = path if path.startswith('http') else urllib.parse.urljoin(
            self.api_url, path)
        headers = self._api_headers()
        failures = 0
        while True:
            self._space_requests()
            try:
                response = self.session.get(
                    url, params = params, headers = headers,
                    timeout = self.timeout)
            except requests.RequestException as error:
                failures += 1
                if failures > _RETRIES:
                    message = f'CourtListener could not be reached: {error}'
                    raise CourtListenerError(message) from error
                time.sleep(5 * 2 ** failures)
                continue
            finally:
                self.requests_made += 1
                self._last_request = time.monotonic()
            status = response.status_code
            if status == 429:
                wait = _retry_after(response)
                if wait > self.max_wait:
                    raise RateLimitError(wait)
                logger.info(
                    'CourtListener asked for a pause: waiting %.0f seconds',
                    wait)
                time.sleep(wait)
                continue
            if status in _TEMPORARY and failures < _RETRIES:
                failures += 1
                time.sleep(5 * 2 ** failures)
                continue
            if status in (401, 403):
                message = (
                    f'CourtListener rejected the request ({status}). Check '
                    f'the API key with "courtpy key show". Details: '
                    f'{_detail(response)}'
                )
                raise CourtListenerError(message)
            if status >= 400:
                message = (
                    f'CourtListener returned {status}: {_detail(response)}')
                raise CourtListenerError(message)
            return dict(response.json())

    def pages(
        self,
        path: str,
        params: Mapping[str, Any] | None = None) -> Iterator[
            tuple[list[dict[str, Any]], str | None]]:
        """Yields the results of each page of a list, and the next address.

        Args:
            path: a path in the API (such as "clusters/") or the address of a
                page.
            params: query parameters for the first page. Defaults to `None`.

        Yields:
            tuple[list[dict[str, Any]], str | None]: the results on each page
                and the address of the next page (or `None` after the last
                page).

        """
        url: str | None = path
        query = params
        while url:
            data = self.get(url, query)
            next_url = data.get('next')
            yield list(data.get('results', [])), next_url
            url, query = next_url, None

    def read_bulk_chunks(
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
        Otherwise, it is downloaded first (or found in the bulk folder) with
        `fetch_bulk_file`.

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
        source = (
            self._bulk_file_url(kind) if self.stream
            else self.fetch_bulk_file(kind))
        yield from amos.loaders.read_chunks(
            source,
            columns = columns,
            keep = keep,
            double_quote = False,
            escape_char = '\\',
            session = self.session,
            timeout = self.timeout)

    def read_bulk_rows(
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
            keep: the values to keep of each of some columns (see
                `read_bulk_chunks`). Defaults to `None`, which keeps every
                row.

        Yields:
            dict[str, str]: each row, mapping column names to text. Missing
                values are empty `str`s.

        """
        chunks = self.read_bulk_chunks(kind, columns = columns, keep = keep)
        for chunk in chunks:
            for row in chunk.to_dict('records'):
                yield {str(key): value for key, value in row.items()}

    def resolve_bulk_date(self) -> str:
        """Returns `bulk_date`, finding the newest complete set if needed.

        Raises:
            LookupError: if no date has every kind of file that courtpy needs.

        Returns:
            The date of the bulk files to use, as YYYY-MM-DD.

        """
        if self.bulk_date is None:
            common: set[str] | None = None
            for kind in _BULK_KINDS:
                dates = set(self.bulk_dates(kind))
                common = dates if common is None else common & dates
            if not common:
                message = 'no date in the bulk data has every file needed'
                raise LookupError(message)
            self.bulk_date = max(common)
        return self.bulk_date

    """ Private Methods """

    def _api_headers(self) -> dict[str, str]:
        """Returns the headers of a request to the API.

        The API key is found with `courtpy.secrets.get_api_key` the first
        time, if none was passed.

        Raises:
            MissingAPIKeyError: if no key was passed and none can be found.

        Returns:
            Headers that include the key and ask for JSON.

        """
        if self.api_key is None:
            self.api_key = secrets.get_api_key()
        return {
            'Authorization': f'Token {self.api_key}',
            'Accept': 'application/json'}

    def _bulk_citations(self, cluster_ids: set[int]) -> dict[int, list[str]]:
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
        for row in self.read_bulk_rows('citations', keep = kept):
            cluster_id = _integer(row.get('cluster_id'))
            if cluster_id is not None:
                found.setdefault(cluster_id, []).extend(
                    citation_strings([row]))
        return found

    def _bulk_clusters(
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
            Each cluster (converted with `_convert_bulk_row`, without the
                columns in `_BULK_CLUSTER_SKIPPED`), by its id.

        """
        found: dict[int, dict[str, Any]] = {}
        if not dockets:
            return found
        kept = {'docket_id': dockets.keys()}
        for row in self.read_bulk_rows('opinion-clusters', keep = kept):
            filed = row.get('date_filed') or ''
            if (start_date and filed < start_date) or (
                end_date and filed > end_date):
                continue
            cluster = _convert_bulk_row(row)
            for column in _BULK_CLUSTER_SKIPPED:
                cluster.pop(column, None)
            found[int(cluster['id'])] = cluster
            if max_cases is not None and len(found) >= max_cases:
                break
        logger.info('found %d cases', len(found))
        return found

    def _bulk_courts(self, wanted: list[str]) -> dict[str, dict[str, Any]]:
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
            for row in self.read_bulk_rows('courts', keep = {'id': wanted})}
        missing = [c for c in wanted if c not in found]
        if missing:
            logger.warning('these courts are not in the bulk data: %s', missing)
        return found

    def _bulk_docket_courts(self, wanted: set[str]) -> dict[int, str]:
        """Returns the court of each docket of the courts in `wanted`.

        Only the court is kept, because a court has far more dockets than
        cases with opinions, and all of their fields would not fit in memory
        for large courts. `_bulk_dockets` reads the fields of the dockets
        that are needed once the cases are known.

        Args:
            wanted: CourtListener court ids.

        Returns:
            The court id of each docket of those courts, by the docket's id.

        """
        found: dict[int, str] = {}
        rows = self.read_bulk_rows(
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

    def _bulk_dockets(self, docket_ids: set[int]) -> dict[int, dict[str, Any]]:
        """Returns the dockets in `docket_ids`.

        The dockets file is read only if there are dockets to look for, and
        reading stops once they are all found.

        Args:
            docket_ids: ids of the dockets of the cases being extracted.

        Returns:
            Each docket (converted with `_convert_bulk_row`, without the
                columns in `options._DOCKET_SKIPPED`), by its id.

        """
        found: dict[int, dict[str, Any]] = {}
        if not docket_ids:
            return found
        for row in self.read_bulk_rows('dockets', keep = {'id': docket_ids}):
            docket_id = int(row['id'])
            docket = _convert_bulk_row(row)
            for column in options._DOCKET_SKIPPED:
                docket.pop(column, None)
            found[docket_id] = docket
            if len(found) == len(docket_ids):
                break
        logger.info('read %d dockets', len(found))
        return found

    def _bulk_file_url(self, kind: str) -> str:
        """Returns the address of the bulk file of one kind.

        Args:
            kind: one of `_BULK_KINDS`.

        Raises:
            ValueError: if `kind` is not one of `_BULK_KINDS`.

        Returns:
            The address of the file in the bucket.

        """
        return f'{self.bulk_url}{options._BULK_PREFIX}{self._bulk_name(kind)}'

    def _bulk_folder_path(self) -> pathlib.Path:
        """Returns the folder to keep the downloaded bulk files in.

        Returns:
            `bulk_folder`, or "bulk" in `utilities.data_folder()` if it is
                `None`.

        """
        if self.bulk_folder is None:
            return utilities.data_folder() / 'bulk'
        return pathlib.Path(self.bulk_folder)

    def _bulk_name(self, kind: str) -> str:
        """Returns the name of the bulk file of one kind.

        Args:
            kind: one of `_BULK_KINDS`.

        Raises:
            ValueError: if `kind` is not one of `_BULK_KINDS`.

        Returns:
            The file's name, such as "opinions-2026-09-30.csv.bz2", for the date
                from `resolve_bulk_date`.

        """
        if kind not in _BULK_KINDS:
            message = f'kind must be one of {list(_BULK_KINDS)}, not {kind!r}'
            raise ValueError(message)
        return f'{kind}-{self.resolve_bulk_date()}.csv.bz2'

    def _bulk_opinions(self, paths: Mapping[int, pathlib.Path]) -> None:
        """Adds the opinions of the cases in `paths` to their files.

        The opinions file is not sorted by case, so a case's opinions can be
        anywhere in it. Opinions are held in memory (with one field of text
        each, see `slim_opinion`) until their text reaches
        `_BULK_BUFFER_BYTES`, and then written to their cases, which keeps
        memory use bounded without rewriting a case's file for every opinion.

        Args:
            paths: the path of each saved case, by its cluster id.

        """
        buffer: dict[int, list[dict[str, Any]]] = {}
        size = 0
        kept = {'cluster_id': paths.keys()}
        for row in self.read_bulk_rows('opinions', keep = kept):
            cluster_id = int(row['cluster_id'])
            opinion = slim_opinion(_convert_bulk_row(row))
            buffer.setdefault(cluster_id, []).append(opinion)
            size += sum(len(v) for v in opinion.values() if isinstance(v, str))
            if size >= _BULK_BUFFER_BYTES:
                _write_buffered_opinions(buffer, paths)
                size = 0
        _write_buffered_opinions(buffer, paths)

    def _download_from_bulk_data(
        self,
        courts: list[str],
        start_date: str | None,
        end_date: str | None,
        folder: pathlib.Path,
        *,
        max_cases: int | None,
        refresh: bool) -> list[pathlib.Path]:
        """Saves the cases of `courts` from the bulk data (see `download`).

        Args:
            courts: CourtListener court ids, with groups already expanded.
            start_date: earliest date filed, as YYYY-MM-DD, or `None` for no
                earliest date.
            end_date: latest date filed, as YYYY-MM-DD, or `None` for no
                latest date.
            folder: folder to save the cases in.
            max_cases: most cases to save, or `None` for every case.
            refresh: whether to replace cases that were already saved with
                their opinions.

        Returns:
            The paths of the cases saved (or updated) by this call.

        """
        date = self.resolve_bulk_date()
        logger.info('extracting cases from the bulk data of %s', date)
        court_records = self._bulk_courts(courts)
        docket_courts = self._bulk_docket_courts(set(courts))
        clusters = self._bulk_clusters(
            docket_courts, start_date, end_date, max_cases)
        dockets = self._bulk_dockets(
            {int(c['docket_id']) for c in clusters.values()})
        citations = self._bulk_citations(set(clusters))
        paths: dict[int, pathlib.Path] = {}
        for cluster_id, cluster in clusters.items():
            docket = dockets[int(cluster['docket_id'])]
            court = docket_courts[int(cluster['docket_id'])]
            path = case_path(folder, court, cluster_id)
            if not refresh and is_complete(path):
                continue
            save_case(path, {
                'source': 'courtlistener',
                'bulk_date': date,
                'court': court_records.get(court, {'id': court}),
                'cluster': cluster,
                'docket': docket,
                'citations': citations.get(cluster_id, []),
                'opinions': []})
            paths[cluster_id] = path
        logger.info('saved %d cases; now adding their opinions', len(paths))
        if paths:
            self._bulk_opinions(paths)
        return list(paths.values())

    def _download_court(
        self,
        court: str,
        start_date: str | None,
        end_date: str | None,
        folder: pathlib.Path,
        *,
        max_cases: int | None,
        dockets: bool,
        refresh: bool) -> list[pathlib.Path]:
        """Downloads the cases of one court with the API (see `download`).

        The court's cases (opinion clusters) are listed one page at a time, in
        the order they were added to CourtListener. For each page, the
        opinions of the cases that are not already saved are requested
        together, and each case is saved. After each page, the address of the
        next page (and of the page just read) is saved in a state file in the
        ".courtpy" folder of `folder`, named for the court and dates, so that
        the download can be resumed. Information about the court is saved
        there too, so that it is asked for only once.

        Args:
            court: a CourtListener court id, such as "ca1".
            start_date: earliest date filed, as YYYY-MM-DD, or `None` for no
                earliest date.
            end_date: latest date filed, as YYYY-MM-DD, or `None` for no latest
                date.
            folder: folder to save the cases in.
            max_cases: most cases to save in this run, or `None` for every
                case. A page that would go past it is cut short and read again
                the next time, so that the cases left out are not skipped.
            dockets: whether to also download each case's docket.
            refresh: whether to start from the first page and download cases
                that were already saved.

        Returns:
            The paths of the cases saved in this run.

        """
        state_path = folder / '.courtpy' / (
            f'api_{court}_{start_date or "start"}_{end_date or "end"}.json')
        state = _load_json(state_path) or {}
        params: dict[str, Any] = {'docket__court': court, 'order_by': 'id'}
        if start_date:
            params['date_filed__gte'] = start_date
        if end_date:
            params['date_filed__lte'] = end_date
        # The court is saved so that resuming a download does not ask again.
        court_path = folder / '.courtpy' / f'court_{court}.json'
        information = _load_json(court_path)
        if information is None:
            information = self.court(court)
            _save_json(court_path, information)
        self._courts[court] = information
        saved: list[pathlib.Path] = []
        # Every address is complete (with its filters), so any page can be
        # saved and requested again to resume. Cases are listed in the order
        # they were added to CourtListener, so after the last page has been
        # read, reading it again finds any cases added since.
        first = urllib.parse.urljoin(self.api_url, 'clusters/')
        url = (
            None if refresh else state.get('next') or state.get('last')
        ) or f'{first}?{urllib.parse.urlencode(params)}'
        while url:
            data = self.get(url)
            clusters = list(data.get('results', []))
            next_url = data.get('next')
            needed = [
                c for c in clusters if refresh or not is_complete(
                    case_path(folder, court, c['id']))]
            remaining = None if max_cases is None else max_cases - len(saved)
            trimmed = remaining is not None and len(needed) > remaining
            if trimmed:
                needed = needed[:remaining]
            if needed:
                opinions = self._opinions_of(
                    [int(c['id']) for c in needed], court = court)
                for cluster in needed:
                    saved.append(self._save(
                        cluster, opinions.get(int(cluster['id']), []), folder,
                        court = information, docket = dockets))
            # A trimmed page is read again next time, so that the cases left
            # out are not skipped.
            state['next'] = url if trimmed else next_url
            state['last'] = url
            _save_json(state_path, state)
            logger.info(
                '%s: %d cases saved (%d requests so far)', court, len(saved),
                self.requests_made)
            if trimmed or (max_cases is not None and len(saved) >= max_cases):
                break
            url = next_url
        return saved

    def _list_bucket(self, prefix: str) -> list[str]:
        """Returns the keys in the bucket of bulk data that start with `prefix`.

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
                self.bulk_url, params = params, timeout = self.timeout)
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

    def _opinions_of(
        self,
        cluster_ids: Sequence[int],
        court: str | None = None) -> dict[int, list[dict[str, Any]]]:
        """Returns the opinions of the clusters in `cluster_ids`.

        The opinions of a page of clusters are requested together, by the
        range of their ids (and their court, to keep the range small).

        Args:
            cluster_ids: ids of opinion clusters.
            court: the court of the clusters. Defaults to `None`.

        Raises:
            CourtListenerError: if the API returns opinions of other clusters
                (which means that it did not apply the filter).

        Returns:
            The opinions of each cluster, by its id, with only one field of
                text each (see `options._TEXT_FIELDS`).

        """
        low, high = min(cluster_ids), max(cluster_ids)
        params: dict[str, Any] = {
            'cluster__id__range': f'{low},{high}',
            'order_by': 'id',
            'fields': ','.join((*options._OPINION_FIELDS, 'cluster'))}
        if court:
            params['cluster__docket__court'] = court
        wanted = set(cluster_ids)
        found: dict[int, list[dict[str, Any]]] = {i: [] for i in cluster_ids}
        for results, _ in self.pages('opinions/', params):
            for opinion in results:
                cluster_id = _cluster_id(opinion)
                if cluster_id is None or not low <= cluster_id <= high:
                    message = (
                        'CourtListener returned an opinion of a case that was '
                        'not asked for, so the "cluster__id__range" filter may '
                        'have changed. Please report this at '
                        'https://github.com/WithPrecedent/courtpy/issues'
                    )
                    raise CourtListenerError(message)
                if cluster_id in wanted:
                    found[cluster_id].append(slim_opinion(opinion))
        return found

    def _space_requests(self) -> None:
        """Waits until `min_interval` seconds have passed since the last one.

        Nothing is done before the first request (when `_last_request` is 0)
        or if enough time has passed already.

        """
        if self._last_request:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)

    def _save(
        self,
        cluster: Mapping[str, Any],
        opinions: Sequence[Mapping[str, Any]],
        folder: pathlib.Path,
        *,
        court: Mapping[str, Any] | None,
        docket: bool) -> pathlib.Path:
        """Saves a cluster and its opinions (and docket, if asked) as a case.

        The case is saved in the folder of its court, which is the court's id
        from `court` or, if that is `None`, from the docket. A case whose court
        cannot be found is saved in a folder named "unknown". The cluster's
        list of opinion addresses ("sub_opinions") is not kept, because the
        opinions themselves are. Every field of the docket is kept but those
        in `options._DOCKET_SKIPPED`.

        Args:
            cluster: the opinion cluster, from the API.
            opinions: its opinions, each with one field of text (see
                `slim_opinion`).
            folder: the folder of saved cases.
            court: information about the case's court (see `court`), or `None`
                if it is not known. If it is `None` and the docket is
                downloaded, the court is looked up from the docket's
                "court_id".
            docket: whether to download the case's docket (one more request).

        Returns:
            The path of the saved case.

        """
        docket_record = None
        docket_id = cluster.get('docket_id') or _id_from_url(
            cluster.get('docket'))
        if docket and docket_id:
            docket_record = {
                k: v for k, v in self.get(f'dockets/{docket_id}/').items()
                if k not in options._DOCKET_SKIPPED}
        court_id = (
            (court or {}).get('id') or (docket_record or {}).get('court_id'))
        if court is None and docket_record and docket_record.get('court_id'):
            court = self.court(str(docket_record['court_id']))
        record = {
            'source': 'courtlistener',
            'court': dict(court or {'id': court_id}),
            'cluster': {
                k: v for k, v in cluster.items() if k != 'sub_opinions'},
            'docket': docket_record,
            'citations': citation_strings(cluster.get('citations', [])),
            'opinions': list(opinions)}
        path = case_path(folder, str(court_id or 'unknown'), cluster['id'])
        save_case(path, record)
        return path


@dataclasses.dataclass
class CourtListenerSource(base.Source):
    """Reads cases saved by `CourtListener`, from the bulk data or the API.

    Each case is a JSON file (see `read_case`), whose sections come from its
    data, so no rules are needed to find them. The "courtlistener_header"
    rules find the parties and judges in them.

    """

    name: ClassVar[str] = 'courtlistener'
    pattern: ClassVar[str] = '*.json'
    header: ClassVar[str] = 'courtlistener_header'

    """ Required Methods """

    def read(self, path: pathlib.Path) -> cases.Case:
        """Reads a saved case for parsing (see `read_case`).

        Args:
            path: the path of the saved case.

        Returns:
            The case.

        """
        return read_case(path)


""" Public Functions """


def add_opinions(
    path: pathlib.Path,
    opinions: Iterable[Mapping[str, Any]]) -> None:
    """Adds opinions to a saved case, replacing any with the same id.

    Args:
        path: path of the saved case.
        opinions: opinions to add.

    """
    record = json.loads(path.read_text(encoding = 'utf-8'))
    existing = {o.get('id'): o for o in record.get('opinions', [])}
    for opinion in opinions:
        existing[opinion.get('id')] = dict(opinion)
    record['opinions'] = list(existing.values())
    save_case(path, record)


def case_path(
    folder: pathlib.Path | str,
    court: str,
    cluster_id: int | str) -> pathlib.Path:
    """Returns the path of a saved case.

    Args:
        folder: the folder of saved cases.
        court: the case's CourtListener court id.
        cluster_id: the case's CourtListener cluster id.

    Returns:
        "{folder}/{court}/{cluster_id}.json".

    """
    return pathlib.Path(folder) / court / f'{cluster_id}.json'


def citation_strings(citations: Iterable[Any]) -> list[str]:
    """Returns citations as text, such as "123 F.3d 456".

    Args:
        citations: citations from CourtListener: `dict`s with "volume",
            "reporter", and "page", or text.

    Returns:
        The citations as text.

    """
    found = []
    for citation in citations or []:
        if isinstance(citation, Mapping):
            parts = (citation.get(k) for k in ('volume', 'reporter', 'page'))
            text = ' '.join(str(p) for p in parts if p not in (None, ''))
        else:
            text = str(citation)
        if text.strip():
            found.append(text.strip())
    return found


def is_complete(path: pathlib.Path) -> bool:
    """Returns whether a case was saved with at least one opinion.

    Args:
        path: path of a saved case.

    Returns:
        Whether the file exists, can be read, and has an opinion.

    """
    if not path.is_file():
        return False
    try:
        record = json.loads(path.read_text(encoding = 'utf-8'))
    except (OSError, ValueError):
        return False
    return bool(record.get('opinions'))


def opinion_role(kind: str | None) -> str:
    """Classifies an opinion by its CourtListener type.

    Args:
        kind: the opinion's "type", such as "010combined", "020lead",
            "030concurrence", "035concurrenceinpart", or "040dissent".

    Returns:
        "majority" (combined, lead, unanimous, or plurality opinions, and
            opinions without a type), "concurrence", "dissent", "mixed" (an
            opinion concurring in part and dissenting in part), or "other"
            (such as an addendum).

    """
    text = (kind or '').lower()
    if not text:
        return 'majority'
    for fragment, role in _ROLES:
        if fragment in text:
            return role
    return 'other'


def opinion_text(opinion: Mapping[str, Any]) -> str:
    """Returns the plain text of an opinion.

    Args:
        opinion: an opinion from CourtListener.

    Returns:
        The text of the first field in `options._TEXT_FIELDS` that is not
            blank, converted from HTML or XML, or an empty `str`.

    """
    for field in options._TEXT_FIELDS:
        value = opinion.get(field)
        if isinstance(value, str) and value.strip():
            return amos.mungers.html_to_text(value)
    return ''


def read_case(path: pathlib.Path | str) -> cases.Case:
    """Reads a saved CourtListener case for parsing.

    The sections of text have the same names as the sections that rules find
    in Lexis-Nexis cases (such as "party", "history", "counsel", and
    "judges"), so that the same rules work for both. "court_num" and
    "court_name" are courtpy's number and name for the case's court, found
    by CourtListener's id for it in the table of courts of
    `options._DEFAULT_JURISDICTION` (see
    `courtpy.courts.court_numbers_by_courtlistener_name`), and
    "lower_court_num" and "lower_court_name" are those of the court appealed
    from, by the docket's id for it. Each is `None` if the table does not
    have the court (the header rules then look for the court appealed from
    in the history).

    Args:
        path: path of a case saved by `CourtListener`.

    Returns:
        The case.

    """
    path = pathlib.Path(path)
    record = json.loads(path.read_text(encoding = 'utf-8'))
    cluster = record.get('cluster') or {}
    docket = record.get('docket') or {}
    court = record.get('court') or {}
    opinions = sorted(
        record.get('opinions') or [],
        key = lambda o: (
            o.get('ordering_key') is None, o.get('ordering_key') or 0,
            str(o.get('type') or ''), o.get('id') or 0))
    roles = [opinion_role(o.get('type')) for o in opinions]

    def authors(*kinds: str) -> str:
        """Returns the authors of the case's opinions with some roles.

        Args:
            *kinds: roles of opinions (see `opinion_role`), such as
                "majority" or "dissent".

        Returns:
            The "author_str" of each opinion with one of those roles, one per
                line, leaving out blank ones.

        """
        return '\n'.join(
            str(o.get('author_str') or '').strip()
            for o, role in zip(opinions, roles, strict = True)
            if role in kinds and str(o.get('author_str') or '').strip())

    majority = [
        o for o, role in zip(opinions, roles, strict = True)
        if role == 'majority']
    texts = [opinion_text(o) for o in opinions]
    sections = {
        'party': _first(
            cluster.get('case_name_full'), docket.get('case_name_full'),
            cluster.get('case_name')),
        'court': _first(court.get('full_name'), court.get('id')),
        'docket_number': _first(docket.get('docket_number')),
        'citation': '; '.join(record.get('citations') or []),
        'history': '\n'.join(_texts(
            cluster.get('procedural_history'), cluster.get('history'),
            docket.get('appeal_from_str'))),
        'counsel': _first(cluster.get('attorneys')),
        'disposition': _first(cluster.get('disposition')),
        'judges': _first(cluster.get('judges'), docket.get('panel_str')),
        'opinion_by': authors('majority'),
        'concurring_lines': authors('concurrence', 'mixed'),
        'dissenting_lines': authors('dissent', 'mixed'),
        'posture': _first(cluster.get('posture')),
        'syllabus': _first(cluster.get('syllabus')),
        'opinion': '\n\n'.join(t for t in texts if t)}
    sections = {
        k: amos.mungers.html_to_text(v) if '<' in v else v
        for k, v in sections.items() if v}
    date_filed = _first(cluster.get('date_filed'))
    status = _first(cluster.get('precedential_status'))
    court_id = court.get('id') or docket.get('court_id')
    lower_id = _court_id_from(
        docket.get('appeal_from_id') or docket.get('appeal_from'))
    numbers = courts.court_numbers_by_courtlistener_name(
        options._DEFAULT_JURISDICTION)
    names = courts.court_names_by_courtlistener_name(
        options._DEFAULT_JURISDICTION)
    metadata: dict[str, Any] = {
        'source': 'courtlistener',
        'cluster_id': cluster.get('id'),
        'docket_id': cluster.get('docket_id') or docket.get('id') or (
            _id_from_url(cluster.get('docket'))),
        'court': court_id,
        'court_num': numbers.get(str(court_id or '').lower()),
        'court_name': names.get(str(court_id or '').lower()),
        'lower_court_num': numbers.get(lower_id or ''),
        'lower_court_name': names.get(lower_id or ''),
        'case_name': _first(cluster.get('case_name')),
        'docket_number': sections.get('docket_number'),
        'citation': sections.get('citation'),
        'disposition': sections.get('disposition'),
        'judges': sections.get('judges'),
        'date_filed': date_filed or None,
        'date_argued': _first(docket.get('date_argued')) or None,
        'year': int(date_filed[:4]) if date_filed[:4].isdigit() else None,
        'precedential_status': status or None,
        'published': status.lower() == 'published' if status else None,
        'per_curiam': any(_true(o.get('per_curiam')) for o in majority),
        'opinions': len(opinions),
        'author_id': next(
            (o.get('author_id') for o in majority if o.get('author_id')), None),
        'panel_ids': [
            i for i in (_id_from_url(p) for p in cluster.get('panel') or [])
            if i is not None],
        'citation_count': cluster.get('citation_count'),
        'nature_of_suit': _first(
            cluster.get('nature_of_suit'), docket.get('nature_of_suit'))
            or None,
        'url': _url(cluster)}
    # Only cases of the Supreme Court have an id in the Supreme Court
    # Database, so other tables of cases get no column for it.
    if _first(cluster.get('scdb_id')):
        metadata['scdb_id'] = _first(cluster.get('scdb_id'))
    return cases.Case(
        id = str(cluster.get('id') or path.stem),
        source = 'courtlistener',
        sections = sections,
        metadata = metadata,
        path = path)


def save_case(path: pathlib.Path, record: Mapping[str, Any]) -> None:
    """Saves a case as a JSON file, replacing any file at `path` safely.

    Args:
        path: path to save the case to. Its folder is created if needed.
        record: the case: "source", "court", "cluster", "docket",
            "citations", and "opinions".

    """
    path.parent.mkdir(parents = True, exist_ok = True)
    temporary = path.with_suffix('.json.part')
    temporary.write_text(
        json.dumps(record, ensure_ascii = False), encoding = 'utf-8')
    temporary.replace(path)


def slim_opinion(opinion: Mapping[str, Any]) -> dict[str, Any]:
    """Returns an opinion with only one field of text, to save space.

    Args:
        opinion: an opinion from the API or the bulk data.

    Returns:
        The fields in `_OPINION_KEPT` that it has, and the first field in
            `options._TEXT_FIELDS` that is not blank.

    """
    slim = {k: opinion[k] for k in _OPINION_KEPT if k in opinion}
    if 'cluster_id' not in slim:
        slim['cluster_id'] = _cluster_id(opinion)
    for field in options._TEXT_FIELDS:
        value = opinion.get(field)
        if isinstance(value, str) and value.strip():
            slim[field] = value
            break
    return slim


""" Private Functions """


def _cluster_id(opinion: Mapping[str, Any]) -> int | None:
    """Returns the cluster id of an opinion.

    Args:
        opinion: an opinion from the API or the bulk data.

    Returns:
        Its "cluster_id" or, if that is missing, the id at the end of its
            "cluster" address (as the API gives it), or `None` if it has
            neither.

    """
    value = opinion.get('cluster_id')
    if value not in (None, ''):
        return int(value)
    return _id_from_url(opinion.get('cluster'))


def _detail(response: Any) -> str:
    """Returns the explanation in an error response, shortened.

    Args:
        response: a response from the API, like a `requests.Response`.

    Returns:
        The "detail" of its JSON (where CourtListener explains an error) or,
            if there is none, the text of the response, cut to 300
            characters.

    """
    try:
        detail = response.json().get('detail')
    except Exception:  # noqa: BLE001
        detail = None
    return str(detail or getattr(response, 'text', ''))[:300]


def _first(*values: Any) -> str:
    """Returns the first value that is not blank, as text.

    Args:
        *values: values to check, in order of preference (such as a case's
            full name and then its short name).

    Returns:
        The first value that is not `None` or blank, with spaces trimmed from
            each end, or an empty `str` if they are all blank.

    """
    for value in values:
        if value not in (None, '') and str(value).strip():
            return str(value).strip()
    return ''


def _convert_bulk_row(row: Mapping[str, str]) -> dict[str, Any]:
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
        elif key in _BULK_INTEGERS:
            converted[key] = _integer(value)
        elif key in _BULK_BOOLEANS:
            converted[key] = value == 't'
        else:
            converted[key] = value
    return converted


def _court_id_from(value: Any) -> str | None:
    """Returns CourtListener's id for a court that a docket refers to.

    Bulk dockets name the court appealed from by its id ("appeal_from_id",
    such as "mad"), and the API by its address ("appeal_from", such as
    "https://www.courtlistener.com/api/rest/v4/courts/mad/").

    Args:
        value: a court's id, its address, a `dict` with its "id", or `None`.

    Returns:
        The id in lower case, or `None` if `value` is blank.

    """
    if isinstance(value, Mapping):
        value = value.get('id')
    if value in (None, ''):
        return None
    text = str(value).strip().rstrip('/')
    return text.rsplit('/', 1)[-1].lower() or None


def _id_from_url(url: Any) -> int | None:
    """Returns the id at the end of an API address.

    The API refers to related objects by their addresses, such as
    "https://www.courtlistener.com/api/rest/v4/people/101/".

    Args:
        url: an address that ends in a number (with or without a final
            slash), an id itself, or `None`.

    Returns:
        The id, or `None` if `url` is blank or does not end in a number.

    """
    if url in (None, ''):
        return None
    if isinstance(url, int):
        return url
    match = re.search(r'(\d+)/?$', str(url))
    return int(match.group(1)) if match else None


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


def _load_json(path: pathlib.Path) -> dict[str, Any] | None:
    """Returns the contents of a JSON file.

    Args:
        path: path of the file, such as a download's state file.

    Returns:
        The contents, or `None` if there is no file.

    """
    if not path.is_file():
        return None
    return dict(json.loads(path.read_text(encoding = 'utf-8')))


def _retry_after(response: Any) -> float:
    """Returns how many seconds a 429 response asks the client to wait.

    Args:
        response: the response, like a `requests.Response`.

    Returns:
        The seconds in the "Retry-After" header (a number of seconds or a
            date) or in the message ("Expected available in N seconds"), or
            60 if neither says.

    """
    headers = getattr(response, 'headers', {})
    header = str(headers.get('Retry-After', '')).strip()
    if header:
        try:
            return max(float(header), 0.0)
        except ValueError:
            moment = email.utils.parsedate_to_datetime(header)
            if moment is not None:
                return max(moment.timestamp() - time.time(), 0.0)
    match = re.search(r'available in (\d+)', _detail(response))
    return float(match.group(1)) if match else 60.0


def _save_json(path: pathlib.Path, contents: Mapping[str, Any]) -> None:
    """Saves `contents` as a JSON file, creating its folder if needed.

    Args:
        path: path to save the file to.
        contents: what to save. It must be something that `json` can write.

    """
    path.parent.mkdir(parents = True, exist_ok = True)
    path.write_text(json.dumps(contents, indent = 2), encoding = 'utf-8')


def _texts(*values: Any) -> list[str]:
    """Returns the values that are not blank, as text.

    Args:
        *values: values to keep, if they are not blank (such as a case's
            procedural history and the court it was appealed from).

    Returns:
        Each value that is not `None` or blank, with spaces trimmed from each
            end, in order.

    """
    return [
        str(v).strip() for v in values
        if v not in (None, '') and str(v).strip()]


def _true(value: Any) -> bool:
    """Returns whether a value from the API or bulk data is true.

    The API gives booleans, but the bulk data (written by PostgreSQL) gives
    "t" and "f".

    Args:
        value: a boolean, or text such as "t", "true", or "1" (in any case).

    Returns:
        Whether `value` is true.

    """
    if isinstance(value, str):
        return value.strip().lower() in {'t', 'true', '1'}
    return bool(value)


def _url(cluster: Mapping[str, Any]) -> str | None:
    """Returns the address of a case on CourtListener.

    Args:
        cluster: the case's opinion cluster.

    Returns:
        Its "absolute_url" on CourtListener's website or, if it has none (as
            in the bulk data), an address made from its id and "slug", or
            `None` if it has no id either.

    """
    if cluster.get('absolute_url'):
        return f'{_SITE}{cluster["absolute_url"]}'
    if cluster.get('id'):
        slug = cluster.get('slug') or 'case'
        return f'{_SITE}/opinion/{cluster["id"]}/{slug}/'
    return None


def _write_buffered_opinions(
    buffer: dict[int, list[dict[str, Any]]],
    paths: Mapping[int, pathlib.Path]) -> None:
    """Writes buffered opinions to their cases and empties the buffer.

    Args:
        buffer: opinions that have not been written yet, by the cluster id of
            their case. It is emptied.
        paths: the path of each saved case, by its cluster id.

    """
    for cluster_id, opinions in buffer.items():
        add_opinions(paths[cluster_id], opinions)
    buffer.clear()
