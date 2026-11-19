"""Default settings for courtpy.

These are module-level constants so that a project built on `courtpy` can
change them before they are used (for example,
`courtpy.options._MIN_INTERVAL = 2.0` to slow down requests to the
CourtListener API). Tables of the federal courts and the presidents are in
"instructions/federal" (see `courtpy.courts` and `courtpy.politics`).

Contents:
    _API_URL: base address of the CourtListener REST API (version 4).
    _BULK_PREFIX: folder of the CourtListener bulk data in its bucket.
    _BULK_URL: address of the public bucket with CourtListener's bulk data.
    _CHUNK_SIZE: number of saved cases given to a process at a time when
        parsing with several processes.
    _COURT_GROUPS: names for groups of CourtListener court ids.
    _DATA_SUBFOLDER: the folder of the `amos` workspace's data folder that
        holds courtpy's downloads.
    _DEFAULT_CODERS: techniques that code variables after cases are parsed.
    _DEFAULT_JURISDICTION: rulebooks used when none are named.
    _REQUIRED_RULEBOOKS: rulebooks applied to every case, before those that
        are named.
    _DOCKET_SKIPPED: fields of a CourtListener docket that are not kept with
        a saved case.
    _ENV_API_KEY: environment variable that can hold the API key.
    _ENV_CONFIG: environment variable that can name the configuration folder.
    _ENV_DATA: environment variable that can name the data folder.
    _IDB_CIRCUITS: the Federal Judicial Center's Integrated Database's code
        for the circuit of each CourtListener court of appeals.
    _IDB_FIRST_YEAR: the first year of the Integrated Database's records of
        appeals.
    _JUDGE_GRACE: years after a judge leaves a court in which an opinion may
        still name the judge.
    _KEYRING_SERVICE: name under which the API key is kept in a keyring.
    _KEYRING_USERNAME: user name under which the API key is kept.
    _LARGE_SECTIONS: sections of text that are not kept in a case table
        unless asked.
    _MAX_WAIT: most seconds to wait when the API asks for a pause.
    _MIN_INTERVAL: fewest seconds between requests to the API.
    _OPINION_FIELDS: opinion fields requested from the CourtListener API.
    _SCDB_FILES: the part of the name of each file of the Supreme Court
        Database that courtpy uses, by what `courtpy.scdb` calls each.
    _SCDB_LINK: the words of the links to those files on the page of a
        release of the Supreme Court Database.
    _SCDB_PAGE: address of the page that links to the releases of the
        Supreme Court Database.
    _SCDB_RELEASE: pattern for the address of the page of a release of the
        modern Supreme Court Database.
    _SOURCES: sources of court opinions that courtpy can read.
    _TEXT_FIELDS: CourtListener fields with the text of an opinion, in the
        order they are preferred.
    _TIMEOUT: seconds to wait for a response from a server.
    _USER_AGENT: how courtpy identifies itself to servers.

"""

from __future__ import annotations

_API_URL: str = 'https://www.courtlistener.com/api/rest/v4/'
_BULK_PREFIX: str = 'bulk-data/'
_BULK_URL: str = (
    'https://com-courtlistener-storage.s3-us-west-2.amazonaws.com/')
# Each process is given this many cases at a time. One task per case
# overwhelmed the pool with about 900,000 cases, and chunks also let progress
# be logged.
_CHUNK_SIZE: int = 1000
# Names that can be used in place of a list of CourtListener court ids.
_COURT_GROUPS: dict[str, tuple[str, ...]] = {
    'federal_appellate': (
        'ca1', 'ca2', 'ca3', 'ca4', 'ca5', 'ca6', 'ca7', 'ca8', 'ca9', 'ca10',
        'ca11', 'cadc', 'cafc'),
    'federal_circuits': (
        'ca1', 'ca2', 'ca3', 'ca4', 'ca5', 'ca6', 'ca7', 'ca8', 'ca9', 'ca10',
        'ca11', 'cadc'),
    'supreme_court': ('scotus',)}
# The folder of the `amos` workspace's data folder where courtpy keeps the
# downloads that every project shares (see `utilities.data_folder`).
_DATA_SUBFOLDER: str = 'courts'
# Coders are run in this order because each uses columns made by the ones
# before it.
_DEFAULT_CODERS: tuple[str, ...] = (
    'code_parties', 'code_case_type', 'code_outcome')
_DEFAULT_JURISDICTION: str = 'federal'
# "header" was written for Lexis-Nexis headers, but CourtListener cases need it
# too (for now) for the parties' roles, the court, the judges, and the
# disposition, which the coders use.
_REQUIRED_RULEBOOKS: tuple[str, ...] = ('header', 'general')
# Every other field of a docket is saved with its case. These are dates the
# record changed, where CourtListener and the Internet Archive store their
# copies, and how often the docket was viewed.
_DOCKET_SKIPPED: frozenset[str] = frozenset({
    'date_created', 'date_modified', 'date_last_index', 'filepath_local',
    'filepath_ia', 'filepath_ia_json', 'ia_upload_failure_count',
    'ia_needs_upload', 'ia_date_first_change', 'view_count'})
_ENV_API_KEY: str = 'COURTLISTENER_API_KEY'
_ENV_CONFIG: str = 'COURTPY_CONFIG_DIR'
_ENV_DATA: str = 'COURTPY_DATA_DIR'
# The Integrated Database numbers the regional circuits as the courts do, and
# the D.C. Circuit 0. The Federal Circuit ("cafc") is not in it.
_IDB_CIRCUITS: dict[str, str] = {
    'cadc': '0', 'ca1': '1', 'ca2': '2', 'ca3': '3', 'ca4': '4', 'ca5': '5',
    'ca6': '6', 'ca7': '7', 'ca8': '8', 'ca9': '9', 'ca10': '10',
    'ca11': '11'}
# The Federal Judicial Center's files of appeals begin with its 2008 fiscal
# (statistical) year, which ended on September 30, 2008.
_IDB_FIRST_YEAR: int = 2008
# An opinion can be issued after one of its judges has died, retired, or
# moved to another court, so a name still matches a judge for this many
# years after the judge's service on a court ended.
_JUDGE_GRACE: int = 2
_KEYRING_SERVICE: str = 'courtpy'
_KEYRING_USERNAME: str = 'courtlistener'
# Sections of text so long that they are only kept in a case table if
# "keep_text" is true. The opinion's words are still counted and searched.
_LARGE_SECTIONS: tuple[str, ...] = (
    'text', 'header', 'opinion', 'opinion_lines')
# A free CourtListener account allows 5 requests a minute, 50 an hour, and
# 125 a day (as of 2026). Waiting up to an hour rides out the first two
# limits. A longer pause (the daily limit) stops the download, which can be
# resumed later.
_MAX_WAIT: float = 3600.0
_MIN_INTERVAL: float = 1.0
_OPINION_FIELDS: tuple[str, ...] = (
    'id', 'cluster_id', 'type', 'author_id', 'author_str', 'per_curiam',
    'joined_by_str', 'ordering_key', 'download_url', 'html_with_citations',
    'plain_text')
# The Supreme Court Database's files that are organized by citation (one row
# for each case, or for each justice in each case), which are named such as
# "SCDB_2026_01_caseCentered_Citation.csv.zip". The page of a release links
# to the case centered file before the justice centered one, with the same
# words for both.
_SCDB_FILES: dict[str, str] = {
    'cases': 'caseCentered_Citation',
    'votes': 'justiceCentered_Citation'}
_SCDB_LINK: str = 'CSV Organized by Supreme Court Citation'
_SCDB_PAGE: str = 'https://scdb.la.psu.edu/data/'
_SCDB_RELEASE: str = r'/data/(\d{4})-release-(\d+)/?$'
_SOURCES: tuple[str, ...] = ('court_listener', 'lexis_nexis')
# CourtListener recommends "html_with_citations" as the most reliable text.
_TEXT_FIELDS: tuple[str, ...] = (
    'html_with_citations', 'html_columbia', 'html_lawbox', 'xml_harvard',
    'html_anon_2020', 'html', 'plain_text')
_TIMEOUT: float = 60.0
_USER_AGENT: str = 'courtpy (https://github.com/WithPrecedent/courtpy)'
