"""Default settings for courtpy.

These are module-level constants so that a project built on `courtpy` can
change them before they are used (for example,
`courtpy.options._MIN_INTERVAL = 2.0` to slow down requests to the
CourtListener API).

Contents:
    _API_URL: base address of the CourtListener REST API (version 4).
    _BULK_PREFIX: folder of the CourtListener bulk data in its bucket.
    _BULK_URL: address of the public bucket with CourtListener's bulk data.
    _CHUNK_SIZE: number of saved cases given to a process at a time when
        parsing with several processes.
    _COURT_GROUPS: names for groups of CourtListener court ids.
    _COURTS: the number and folder name of each federal court, by a pattern
        of the Federal Judicial Center's name for it.
    _DATA_FOLDER: the data folder when courtpy runs from its repository.
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
    _PRESIDENTS: the party of the president in each year.
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
    _TRIAL_COURTS: the name of each federal district court, by a pattern
        of how an opinion names it.
    _USER_AGENT: how courtpy identifies itself to servers.

"""

from __future__ import annotations

import pathlib

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
# The number and folder name of each federal court, by a pattern of the
# name that the Federal Judicial Center gives it, which is matched ignoring
# case. Kept from the earlier version of courtpy; not yet used.
_COURTS: dict[str, tuple[int, str]] = {
    'Supreme Court of the United States': (99, 'supreme_court'),
    r'U\.S\. Circuit Court for the Districts of California': (
        9, 'circuit_districts_of_california'),
    r'U\.S\. Circuit Court for the Fifth Circuit': (5, 'fifth_circuit'),
    r'U\.S\. Circuit Court for the First Circuit': (1, 'first_circuit'),
    r'U\.S\. Circuit Court for the Fourth Circuit': (4, 'fourth_circuit'),
    r'U\.S\. Circuit Court for the Second Circuit': (2, 'second_circuit'),
    r'U\.S\. Circuit Court for the Sixth Circuit': (6, 'sixth_circuit'),
    r'U\.S\. Circuit Court for the Third Circuit': (3, 'third_circuit'),
    r'U\.S\. Circuit Courts for the Eighth Circuit': (8, 'eighth_circuit'),
    r'U\.S\. Circuit Courts for the Fifth Circuit': (5, 'fifth_circuit'),
    r'U\.S\. Circuit Courts for the First Circuit': (1, 'first_circuit'),
    r'U\.S\. Circuit Courts for the Fourth Circuit': (4, 'fourth_circuit'),
    r'U\.S\. Circuit Courts for the Ninth Circuit': (9, 'ninth_circuit'),
    r'U\.S\. Circuit Courts for the Second Circuit': (2, 'second_circuit'),
    r'U\.S\. Circuit Courts for the Seventh Circuit': (7, 'seventh_circuit'),
    r'U\.S\. Circuit Courts for the Sixth Circuit': (6, 'sixth_circuit'),
    r'U\.S\. Circuit Courts for the Third Circuit': (3, 'third_circuit'),
    r'U\.S\. Court of Appeals for the District of Columbia Circuit': (
        12, 'dc_circuit'),
    r'U\.S\. Court of Appeals for the Eighth Circuit': (8, 'eighth_circuit'),
    r'U\.S\. Court of Appeals for the Eleventh Circuit': (
        11, 'eleventh_circuit'),
    r'U\.S\. Court of Appeals for the Federal Circuit': (13, 'federal_circuit'),
    r'U\.S\. Court of Appeals for the Fifth Circuit': (5, 'fifth_circuit'),
    r'U\.S\. Court of Appeals for the First Circuit': (1, 'first_circuit'),
    r'U\.S\. Court of Appeals for the Fourth Circuit': (4, 'fourth_circuit'),
    r'U\.S\. Court of Appeals for the Ninth Circuit': (9, 'ninth_circuit'),
    r'U\.S\. Court of Appeals for the Second Circuit': (2, 'second_circuit'),
    r'U\.S\. Court of Appeals for the Seventh Circuit': (7, 'seventh_circuit'),
    r'U\.S\. Court of Appeals for the Sixth Circuit': (6, 'sixth_circuit'),
    r'U\.S\. Court of Appeals for the Tenth Circuit': (10, 'tenth_circuit'),
    r'U\.S\. Court of Appeals for the Third Circuit': (3, 'third_circuit'),
    r'U\.S\. Court of Customs and Patent Appeals': (
        13, 'court_of_customs_and_patent_appeals'),
    r'U\.S\. Court of Customs Appeals \(later U\.S\. Court of Customs and Patent Appeals\)': (
        13, 'court_of_customs_appeals'),
    r'U\.S\. Court of International Trade': (
        101, 'court_of_international_trade'),
    r'U\.S\. Customs Court': (102, 'customs_court'),
    r'U\.S\. District Court for the Albemarle, Cape Fear & Pamptico Districts of North Carolina': (
        1001, 'albemarle_cape_fear_pamptico_districts_of_north_carolina'),
    r'U\.S\. District Court for the Central District of California': (
        1002, 'central_district_of_california'),
    r'U\.S\. District Court for the Central District of Illinois': (
        1003, 'central_district_of_illinois'),
    r'U\.S\. District Court for the District of Alabama': (
        1004, 'district_of_alabama'),
    r'U\.S\. District Court for the District of Alaska': (
        1005, 'district_of_alaska'),
    r'U\.S\. District Court for the District of Arizona': (
        1006, 'district_of_arizona'),
    r'U\.S\. District Court for the District of Arkansas': (
        1007, 'district_of_arkansas'),
    r'U\.S\. District Court for the District of California': (
        1008, 'district_of_california'),
    r'U\.S\. District Court for the District of Colorado': (
        1009, 'district_of_colorado'),
    r'U\.S\. District Court for the District of Columbia': (
        1010, 'district_of_columbia'),
    r'U\.S\. District Court for the District of Columbia \(Supreme Court of the District of Columbia\)': (
        1011, 'supreme_court_of_the_district_of_columbia'),
    r'U\.S\. District Court for the District of Connecticut': (
        1012, 'district_of_connecticut'),
    r'U\.S\. District Court for the District of Delaware': (
        1013, 'district_of_delaware'),
    r'U\.S\. District Court for the District of Florida': (
        1014, 'district_of_florida'),
    r'U\.S\. District Court for the District of Georgia': (
        1015, 'district_of_georgia'),
    r'U\.S\. District Court for the District of Hawaii': (
        1016, 'district_of_hawaii'),
    r'U\.S\. District Court for the District of Idaho': (
        1017, 'district_of_idaho'),
    r'U\.S\. District Court for the District of Illinois': (
        1018, 'district_of_illinois'),
    r'U\.S\. District Court for the District of Indiana': (
        1019, 'district_of_indiana'),
    r'U\.S\. District Court for the District of Iowa': (
        1020, 'district_of_iowa'),
    r'U\.S\. District Court for the District of Kansas': (
        1021, 'district_of_kansas'),
    r'U\.S\. District Court for the District of Kentucky': (
        1022, 'district_of_kentucky'),
    r'U\.S\. District Court for the District of Louisiana': (
        1023, 'district_of_louisiana'),
    r'U\.S\. District Court for the District of Maine': (
        1024, 'district_of_maine'),
    r'U\.S\. District Court for the District of Maryland': (
        1025, 'district_of_maryland'),
    r'U\.S\. District Court for the District of Massachusetts': (
        1026, 'district_of_massachusetts'),
    r'U\.S\. District Court for the District of Michigan': (
        1027, 'district_of_michigan'),
    r'U\.S\. District Court for the District of Minnesota': (
        1028, 'district_of_minnesota'),
    r'U\.S\. District Court for the District of Mississippi': (
        1029, 'district_of_mississippi'),
    r'U\.S\. District Court for the District of Missouri': (
        1030, 'district_of_missouri'),
    r'U\.S\. District Court for the District of Montana': (
        1031, 'district_of_montana'),
    r'U\.S\. District Court for the District of Nebraska': (
        1032, 'district_of_nebraska'),
    r'U\.S\. District Court for the District of Nevada': (
        1033, 'district_of_nevada'),
    r'U\.S\. District Court for the District of New Hampshire': (
        1034, 'district_of_new_hampshire'),
    r'U\.S\. District Court for the District of New Jersey': (
        1035, 'district_of_new_jersey'),
    r'U\.S\. District Court for the District of New Mexico': (
        1036, 'district_of_new_mexico'),
    r'U\.S\. District Court for the District of New York': (
        1037, 'district_of_new_york'),
    r'U\.S\. District Court for the District of North Carolina': (
        1038, 'district_of_north_carolina'),
    r'U\.S\. District Court for the District of North Dakota': (
        1039, 'district_of_north_dakota'),
    r'U\.S\. District Court for the District of Ohio': (
        1040, 'district_of_ohio'),
    r'U\.S\. District Court for the District of Oregon': (
        1041, 'district_of_oregon'),
    r'U\.S\. District Court for the District of Orleans': (
        1042, 'district_of_orleans'),
    r'U\.S\. District Court for the District of Pennsylvania': (
        1043, 'district_of_pennsylvania'),
    r'U\.S\. District Court for the District of Puerto Rico': (
        1044, 'district_of_puerto_rico'),
    r'U\.S\. District Court for the District of Rhode Island': (
        1045, 'district_of_rhode_island'),
    r'U\.S\. District Court for the District of South Carolina': (
        1046, 'district_of_south_carolina'),
    r'U\.S\. District Court for the District of South Dakota': (
        1047, 'district_of_south_dakota'),
    r'U\.S\. District Court for the District of Tennessee': (
        1048, 'district_of_tennessee'),
    r'U\.S\. District Court for the District of Texas': (
        1049, 'district_of_texas'),
    r'U\.S\. District Court for the District of Utah': (
        1050, 'district_of_utah'),
    r'U\.S\. District Court for the District of Vermont': (
        1051, 'district_of_vermont'),
    r'U\.S\. District Court for the District of Virginia': (
        1052, 'district_of_virginia'),
    r'U\.S\. District Court for the District of Washington': (
        1053, 'district_of_washington'),
    r'U\.S\. District Court for the District of West Virginia': (
        1054, 'district_of_west_virginia'),
    r'U\.S\. District Court for the District of Wisconsin': (
        1055, 'district_of_wisconsin'),
    r'U\.S\. District Court for the District of Wyoming': (
        1056, 'district_of_wyoming'),
    r'U\.S\. District Court for the Eastern District of Arkansas': (
        1057, 'eastern_district_of_arkansas'),
    r'U\.S\. District Court for the Eastern District of California': (
        1058, 'eastern_district_of_california'),
    r'U\.S\. District Court for the Eastern District of Illinois': (
        1059, 'eastern_district_of_illinois'),
    r'U\.S\. District Court for the Eastern District of Kentucky': (
        1060, 'eastern_district_of_kentucky'),
    r'U\.S\. District Court for the Eastern District of Louisiana': (
        1061, 'eastern_district_of_louisiana'),
    r'U\.S\. District Court for the Eastern District of Michigan': (
        1062, 'eastern_district_of_michigan'),
    r'U\.S\. District Court for the Eastern District of Missouri': (
        1063, 'eastern_district_of_missouri'),
    r'U\.S\. District Court for the Eastern District of New Jersey': (
        1064, 'eastern_district_of_new_jersey'),
    r'U\.S\. District Court for the Eastern District of New York': (
        1065, 'eastern_district_of_new_york'),
    r'U\.S\. District Court for the Eastern District of North Carolina': (
        1066, 'eastern_district_of_north_carolina'),
    r'U\.S\. District Court for the Eastern District of Oklahoma': (
        1067, 'eastern_district_of_oklahoma'),
    r'U\.S\. District Court for the Eastern District of Pennsylvania': (
        1068, 'eastern_district_of_pennsylvania'),
    r'U\.S\. District Court for the Eastern District of South Carolina': (
        1069, 'eastern_district_of_south_carolina'),
    r'U\.S\. District Court for the Eastern District of Tennessee': (
        1070, 'eastern_district_of_tennessee'),
    r'U\.S\. District Court for the Eastern District of Texas': (
        1071, 'eastern_district_of_texas'),
    r'U\.S\. District Court for the Eastern District of Virginia': (
        1072, 'eastern_district_of_virginia'),
    r'U\.S\. District Court for the Eastern District of Washington': (
        1073, 'eastern_district_of_washington'),
    r'U\.S\. District Court for the Eastern District of Wisconsin': (
        1074, 'eastern_district_of_wisconsin'),
    r'U\.S\. District Court for the Edenton, New Bern & Wilmington Districts of North Carolina': (
        1075, 'edenton_new_bern_wilmington_districts_of_north_carolina'),
    r'U\.S\. District Court for the Middle District of Alabama': (
        1076, 'middle_district_of_alabama'),
    r'U\.S\. District Court for the Middle District of Florida': (
        1077, 'middle_district_of_florida'),
    r'U\.S\. District Court for the Middle District of Georgia': (
        1078, 'middle_district_of_georgia'),
    r'U\.S\. District Court for the Middle District of Louisiana': (
        1079, 'middle_district_of_louisiana'),
    r'U\.S\. District Court for the Middle District of North Carolina': (
        1080, 'middle_district_of_north_carolina'),
    r'U\.S\. District Court for the Middle District of Pennsylvania': (
        1081, 'middle_district_of_pennsylvania'),
    r'U\.S\. District Court for the Middle District of Tennessee': (
        1082, 'middle_district_of_tennessee'),
    r'U\.S\. District Court for the Northern District of Alabama': (
        1083, 'northern_district_of_alabama'),
    r'U\.S\. District Court for the Northern District of California': (
        1084, 'northern_district_of_california'),
    r'U\.S\. District Court for the Northern District of Florida': (
        1085, 'northern_district_of_florida'),
    r'U\.S\. District Court for the Northern District of Georgia': (
        1086, 'northern_district_of_georgia'),
    r'U\.S\. District Court for the Northern District of Illinois': (
        1087, 'northern_district_of_illinois'),
    r'U\.S\. District Court for the Northern District of Indiana': (
        1088, 'northern_district_of_indiana'),
    r'U\.S\. District Court for the Northern District of Iowa': (
        1089, 'northern_district_of_iowa'),
    r'U\.S\. District Court for the Northern District of Mississippi': (
        1090, 'northern_district_of_mississippi'),
    r'U\.S\. District Court for the Northern District of New York': (
        1091, 'northern_district_of_new_york'),
    r'U\.S\. District Court for the Northern District of Ohio': (
        1092, 'northern_district_of_ohio'),
    r'U\.S\. District Court for the Northern District of Oklahoma': (
        1093, 'northern_district_of_oklahoma'),
    r'U\.S\. District Court for the Northern District of Texas': (
        1094, 'northern_district_of_texas'),
    r'U\.S\. District Court for the Northern District of West Virginia': (
        1095, 'northern_district_of_west_virginia'),
    r'U\.S\. District Court for the Southern District of Alabama': (
        1096, 'southern_district_of_alabama'),
    r'U\.S\. District Court for the Southern District of California': (
        1097, 'southern_district_of_california'),
    r'U\.S\. District Court for the Southern District of Florida': (
        1098, 'southern_district_of_florida'),
    r'U\.S\. District Court for the Southern District of Georgia': (
        1099, 'southern_district_of_georgia'),
    r'U\.S\. District Court for the Southern District of Illinois': (
        1100, 'southern_district_of_illinois'),
    r'U\.S\. District Court for the Southern District of Indiana': (
        1101, 'southern_district_of_indiana'),
    r'U\.S\. District Court for the Southern District of Iowa': (
        1102, 'southern_district_of_iowa'),
    r'U\.S\. District Court for the Southern District of Mississippi': (
        1103, 'southern_district_of_mississippi'),
    r'U\.S\. District Court for the Southern District of New York': (
        1104, 'southern_district_of_new_york'),
    r'U\.S\. District Court for the Southern District of Ohio': (
        1105, 'southern_district_of_ohio'),
    r'U\.S\. District Court for the Southern District of Texas': (
        1106, 'southern_district_of_texas'),
    r'U\.S\. District Court for the Southern District of West Virginia': (
        1107, 'southern_district_of_west_virginia'),
    r'U\.S\. District Court for the Western District of Arkansas': (
        1108, 'western_district_of_arkansas'),
    r'U\.S\. District Court for the Western District of Kentucky': (
        1109, 'western_district_of_kentucky'),
    r'U\.S\. District Court for the Western District of Louisiana': (
        1110, 'western_district_of_louisiana'),
    r'U\.S\. District Court for the Western District of Michigan': (
        1111, 'western_district_of_michigan'),
    r'U\.S\. District Court for the Western District of Missouri': (
        1112, 'western_district_of_missouri'),
    r'U\.S\. District Court for the Western District of New Jersey': (
        1113, 'western_district_of_new_jersey'),
    r'U\.S\. District Court for the Western District of New York': (
        1114, 'western_district_of_new_york'),
    r'U\.S\. District Court for the Western District of North Carolina': (
        1115, 'western_district_of_north_carolina'),
    r'U\.S\. District Court for the Western District of Oklahoma': (
        1116, 'western_district_of_oklahoma'),
    r'U\.S\. District Court for the Western District of Pennsylvania': (
        1117, 'western_district_of_pennsylvania'),
    r'U\.S\. District Court for the Western District of South Carolina': (
        1118, 'western_district_of_south_carolina'),
    r'U\.S\. District Court for the Western District of Tennessee': (
        1119, 'western_district_of_tennessee'),
    r'U\.S\. District Court for the Western District of Texas': (
        1120, 'western_district_of_texas'),
    r'U\.S\. District Court for the Western District of Virginia': (
        1121, 'western_district_of_virginia'),
    r'U\.S\. District Court for the Western District of Washington': (
        1122, 'western_district_of_washington'),
    r'U\.S\. District Court for the Western District of Wisconsin': (
        1123, 'western_district_of_wisconsin'),
    'Circuit Court of the District of Columbia': (
        103, 'circuit_court_of_the_district_of_columbia'),
    'Court of Claims': (104, 'court_of_claims')}
# "data/courts" two folders above the repository (beside the folder of code
# projects), where fjc-idb and other projects keep their court data too.
_DATA_FOLDER: pathlib.Path = (
    pathlib.Path(__file__).parents[4] / "data" / "courts")
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
    "date_created", "date_modified", "date_last_index", "filepath_local",
    "filepath_ia", "filepath_ia_json", "ia_upload_failure_count",
    "ia_needs_upload", "ia_date_first_change", "view_count"})
_ENV_API_KEY: str = 'COURTLISTENER_API_KEY'
_ENV_CONFIG: str = 'COURTPY_CONFIG_DIR'
_ENV_DATA: str = 'COURTPY_DATA_DIR'
# The Integrated Database numbers the regional circuits as the courts do, and
# the D.C. Circuit 0. The Federal Circuit ("cafc") is not in it.
_IDB_CIRCUITS: dict[str, str] = {
    "cadc": "0", "ca1": "1", "ca2": "2", "ca3": "3", "ca4": "4", "ca5": "5",
    "ca6": "6", "ca7": "7", "ca8": "8", "ca9": "9", "ca10": "10",
    "ca11": "11"}
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
# The party of the president in each year: -1 for Democratic and 1 for
# Republican. A president who takes office in a year (in January) is the
# president of that year. Add a year to `courtpy.politics.presidents` by
# adding it here.
_PRESIDENTS: dict[int, int] = {
    1933: -1, 1934: -1, 1935: -1, 1936: -1, 1937: -1, 1938: -1, 1939: -1,
    1940: -1, 1941: -1, 1942: -1, 1943: -1, 1944: -1, 1945: -1, 1946: -1,
    1947: -1, 1948: -1, 1949: -1, 1950: -1, 1951: -1, 1952: -1, 1953: 1,
    1954: 1, 1955: 1, 1956: 1, 1957: 1, 1958: 1, 1959: 1, 1960: 1, 1961: -1,
    1962: -1, 1963: -1, 1964: -1, 1965: -1, 1966: -1, 1967: -1, 1968: -1,
    1969: 1, 1970: 1, 1971: 1, 1972: 1, 1973: 1, 1974: 1, 1975: 1, 1976: 1,
    1977: -1, 1978: -1, 1979: -1, 1980: -1, 1981: 1, 1982: 1, 1983: 1, 1984: 1,
    1985: 1, 1986: 1, 1987: 1, 1988: 1, 1989: 1, 1990: 1, 1991: 1, 1992: 1,
    1993: -1, 1994: -1, 1995: -1, 1996: -1, 1997: -1, 1998: -1, 1999: -1,
    2000: -1, 2001: 1, 2002: 1, 2003: 1, 2004: 1, 2005: 1, 2006: 1, 2007: 1,
    2008: 1, 2009: -1, 2010: -1, 2011: -1, 2012: -1, 2013: -1, 2014: -1,
    2015: -1, 2016: -1, 2017: 1, 2018: 1, 2019: 1, 2020: 1, 2021: -1, 2022: -1,
    2023: -1, 2024: -1, 2025: 1, 2026: 1, 2027: 1, 2028: 1}
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
# The name of each federal district court, by a pattern of how an opinion
# names it (its name or its abbreviation in a citation, such as
# "C.D. CAL."), which is matched ignoring case. Kept from the earlier
# version of courtpy; not yet used.
_TRIAL_COURTS: dict[str, str] = {
    'CENTRAL DISTRICT OF CALIFORNIA': 'CENTRAL DISTRICT OF CALIFORNIA',
    'CENTRAL DISTRICT OF ILLINOIS': 'CENTRAL DISTRICT OF ILLINOIS',
    'EASTERN DISTRICT OF ARKANSAS': 'EASTERN DISTRICT OF ARKANSAS',
    'EASTERN DISTRICT OF CALIFORNIA': 'EASTERN DISTRICT OF CALIFORNIA',
    'EASTERN DISTRICT OF KENTUCKY': 'EASTERN DISTRICT OF KENTUCKY',
    'EASTERN DISTRICT OF LOUISIANA': 'EASTERN DISTRICT OF LOUISIANA',
    'EASTERN DISTRICT OF MICHIGAN': 'EASTERN DISTRICT OF MICHIGAN',
    'EASTERN DISTRICT OF MISSOURI': 'EASTERN DISTRICT OF MISSOURI',
    'EASTERN DISTRICT OF NEW YORK': 'EASTERN DISTRICT OF NEW YORK',
    'EASTERN DISTRICT OF NORTH CAROLINA': 'EASTERN DISTRICT OF NORTH CAROLINA',
    'EASTERN DISTRICT OF OKLAHOMA': 'EASTERN DISTRICT OF OKLAHOMA',
    'EASTERN DISTRICT OF PENNSYLVANIA': 'EASTERN DISTRICT OF PENNSYLVANIA',
    'EASTERN DISTRICT OF TENNESSEE': 'EASTERN DISTRICT OF TENNESSEE',
    'EASTERN DISTRICT OF TEXAS': 'EASTERN DISTRICT OF TEXAS',
    'EASTERN DISTRICT OF VIRGINIA': 'EASTERN DISTRICT OF VIRGINIA',
    'EASTERN DISTRICT OF WASHINGTON': 'EASTERN DISTRICT OF WASHINGTON',
    'EASTERN DISTRICT OF WISCONSIN': 'EASTERN DISTRICT OF WISCONSIN',
    'MIDDLE DISTRICT OF ALABAMA': 'MIDDLE DISTRICT OF ALABAMA',
    'MIDDLE DISTRICT OF FLORIDA': 'MIDDLE DISTRICT OF FLORIDA',
    'MIDDLE DISTRICT OF GEORGIA': 'MIDDLE DISTRICT OF GEORGIA',
    'MIDDLE DISTRICT OF LOUISIANA': 'MIDDLE DISTRICT OF LOUISIANA',
    'MIDDLE DISTRICT OF NORTH CAROLINA': 'MIDDLE DISTRICT OF NORTH CAROLINA',
    'MIDDLE DISTRICT OF PENNSYLVANIA': 'MIDDLE DISTRICT OF PENNSYLVANIA',
    'MIDDLE DISTRICT OF TENNESSEE': 'MIDDLE DISTRICT OF TENNESSEE',
    'NORTHERN DISTRICT OF ALABAMA': 'NORTHERN DISTRICT OF ALABAMA',
    'NORTHERN DISTRICT OF CALIFORNIA': 'NORTHERN DISTRICT OF CALIFORNIA',
    'NORTHERN DISTRICT OF FLORIDA': 'NORTHERN DISTRICT OF FLORIDA',
    'NORTHERN DISTRICT OF GEORGIA': 'NORTHERN DISTRICT OF GEORGIA',
    'NORTHERN DISTRICT OF ILLINOIS': 'NORTHERN DISTRICT OF ILLINOIS',
    'NORTHERN DISTRICT OF INDIANA': 'NORTHERN DISTRICT OF INDIANA',
    'NORTHERN DISTRICT OF IOWA': 'NORTHERN DISTRICT OF IOWA',
    'NORTHERN DISTRICT OF MISSISSIPPI': 'NORTHERN DISTRICT OF MISSISSIPPI',
    'NORTHERN DISTRICT OF NEW YORK': 'NORTHERN DISTRICT OF NEW YORK',
    'NORTHERN DISTRICT OF OHIO': 'NORTHERN DISTRICT OF OHIO',
    'NORTHERN DISTRICT OF OKLAHOMA': 'NORTHERN DISTRICT OF OKLAHOMA',
    'NORTHERN DISTRICT OF TEXAS': 'NORTHERN DISTRICT OF TEXAS',
    'NORTHERN DISTRICT OF WEST VIRGINIA': 'NORTHERN DISTRICT OF WEST VIRGINIA',
    'SOUTHERN DISTRICT OF ALABAMA': 'SOUTHERN DISTRICT OF ALABAMA',
    'SOUTHERN DISTRICT OF CALIFORNIA': 'SOUTHERN DISTRICT OF CALIFORNIA',
    'SOUTHERN DISTRICT OF FLORIDA': 'SOUTHERN DISTRICT OF FLORIDA',
    'SOUTHERN DISTRICT OF GEORGIA': 'SOUTHERN DISTRICT OF GEORGIA',
    'SOUTHERN DISTRICT OF INDIANA': 'SOUTHERN DISTRICT OF INDIANA',
    'SOUTHERN DISTRICT OF IOWA': 'SOUTHERN DISTRICT OF IOWA',
    'SOUTHERN DISTRICT OF MISSISSIPPI': 'SOUTHERN DISTRICT OF MISSISSIPPI',
    'SOUTHERN DISTRICT OF NEW YORK': 'SOUTHERN DISTRICT OF NEW YORK',
    'SOUTHERN DISTRICT OF OHIO': 'SOUTHERN DISTRICT OF OHIO',
    'SOUTHERN DISTRICT OF TEXAS': 'SOUTHERN DISTRICT OF TEXAS',
    'SOUTHERN DISTRICT OF WEST VIRGINIA': 'SOUTHERN DISTRICT OF WEST VIRGINIA',
    'WESTERN DISTRICT OF ARKANSAS': 'WESTERN DISTRICT OF ARKANSAS',
    'WESTERN DISTRICT OF KENTUCKY': 'WESTERN DISTRICT OF KENTUCKY',
    'WESTERN DISTRICT OF LOUISIANA': 'WESTERN DISTRICT OF LOUISIANA',
    'WESTERN DISTRICT OF MICHIGAN': 'WESTERN DISTRICT OF MICHIGAN',
    'WESTERN DISTRICT OF MISSOURI': 'WESTERN DISTRICT OF MISSOURI',
    'WESTERN DISTRICT OF NEW YORK': 'WESTERN DISTRICT OF NEW YORK',
    'WESTERN DISTRICT OF NORTH CAROLINA': 'WESTERN DISTRICT OF NORTH CAROLINA',
    'WESTERN DISTRICT OF OKLAHOMA': 'WESTERN DISTRICT OF OKLAHOMA',
    'WESTERN DISTRICT OF PENNSYLVANIA': 'WESTERN DISTRICT OF PENNSYLVANIA',
    'WESTERN DISTRICT OF TENNESSEE': 'WESTERN DISTRICT OF TENNESSEE',
    'WESTERN DISTRICT OF TEXAS': 'WESTERN DISTRICT OF TEXAS',
    'WESTERN DISTRICT OF VIRGINIA': 'WESTERN DISTRICT OF VIRGINIA',
    'WESTERN DISTRICT OF WASHINGTON': 'WESTERN DISTRICT OF WASHINGTON',
    'WESTERN DISTRICT OF WISCONSIN': 'WESTERN DISTRICT OF WISCONSIN',
    'DISTRICT OF ALASKA': 'DISTRICT OF ALASKA',
    'DISTRICT OF ARIZONA': 'DISTRICT OF ARIZONA',
    'DISTRICT OF COLORADO': 'DISTRICT OF COLORADO',
    'DISTRICT OF CONNECTICUT': 'DISTRICT OF CONNECTICUT',
    'DISTRICT OF COLUMBIA': 'DISTRICT OF COLUMBIA',
    'DISTRICT OF DELAWARE': 'DISTRICT OF DELAWARE',
    'DISTRICT OF GUAM': 'DISTRICT OF GUAM',
    'DISTRICT OF HAWAII': 'DISTRICT OF HAWAII',
    'DISTRICT OF IDAHO': 'DISTRICT OF IDAHO',
    'DISTRICT OF KANSAS': 'DISTRICT OF KANSAS',
    'DISTRICT OF MAINE': 'DISTRICT OF MAINE',
    'DISTRICT OF MARYLAND': 'DISTRICT OF MARYLAND',
    'DISTRICT OF MASSACHUSETTS': 'DISTRICT OF MASSACHUSETTS',
    'DISTRICT OF MINNESOTA': 'DISTRICT OF MINNESOTA',
    'DISTRICT OF MONTANA': 'DISTRICT OF MONTANA',
    'DISTRICT OF NEBRASKA': 'DISTRICT OF NEBRASKA',
    'DISTRICT OF NEVADA': 'DISTRICT OF NEVADA',
    'DISTRICT OF NEW HAMPSHIRE': 'DISTRICT OF NEW HAMPSHIRE',
    'DISTRICT OF NEW JERSEY': 'DISTRICT OF NEW JERSEY',
    'DISTRICT OF NEW MEXICO': 'DISTRICT OF NEW MEXICO',
    'DISTRICT OF NORTH DAKOTA': 'DISTRICT OF NORTH DAKOTA',
    'DISTRICT OF OREGON': 'DISTRICT OF OREGON',
    'DISTRICT OF PUERTO RICO': 'DISTRICT OF PUERTO RICO',
    'DISTRICT OF RHODE ISLAND': 'DISTRICT OF RHODE ISLAND',
    'DISTRICT OF SOUTH CAROLINA': 'DISTRICT OF SOUTH CAROLINA',
    'DISTRICT OF SOUTH DAKOTA': 'DISTRICT OF SOUTH DAKOTA',
    'DISTRICT OF THE CANAL ZONE': 'DISTRICT OF THE CANAL ZONE',
    'DISTRICT OF THE NORTHERN MARIANA ISLANDS':
        'DISTRICT OF THE NORTHERN MARIANA ISLANDS',
    'DISTRICT OF THE VIRGIN ISLANDS': 'DISTRICT OF THE VIRGIN ISLANDS',
    'DISTRICT OF UTAH': 'DISTRICT OF UTAH',
    'DISTRICT OF VERMONT': 'DISTRICT OF VERMONT',
    'DISTRICT OF WYOMING': 'DISTRICT OF WYOMING',
    r'C\.D\. CAL\.': 'CENTRAL DISTRICT OF CALIFORNIA',
    r'C\.D\. ILL\.': 'CENTRAL DISTRICT OF ILLINOIS',
    r'E\.D\. ARK\.': 'EASTERN DISTRICT OF ARKANSAS',
    r'E\.D\. CAL\.': 'EASTERN DISTRICT OF CALIFORNIA',
    r'E\.D\. KY\.': 'EASTERN DISTRICT OF KENTUCKY',
    r'E\.D\. LA\.': 'EASTERN DISTRICT OF LOUISIANA',
    r'E\.D\. MICH\.': 'EASTERN DISTRICT OF MICHIGAN',
    r'E\.D\. MO\.': 'EASTERN DISTRICT OF MISSOURI',
    r'E\.D\.N\.Y\.': 'EASTERN DISTRICT OF NEW YORK',
    r'E\.D\.N\.C\.': 'EASTERN DISTRICT OF NORTH CAROLINA',
    r'E\.D\. OKLA\.': 'EASTERN DISTRICT OF OKLAHOMA',
    r'E\.D\. PA\.': 'EASTERN DISTRICT OF PENNSYLVANIA',
    r'E\.D\. TENN\.': 'EASTERN DISTRICT OF TENNESSEE',
    r'E\.D\. TEX\.': 'EASTERN DISTRICT OF TEXAS',
    r'E\.D\. VA\.': 'EASTERN DISTRICT OF VIRGINIA',
    r'E\.D\. WASH\.': 'EASTERN DISTRICT OF WASHINGTON',
    r'E\.D\. WIS\.': 'EASTERN DISTRICT OF WISCONSIN',
    r'M\.D\. ALA\.': 'MIDDLE DISTRICT OF ALABAMA',
    r'M\.D\. FLA\.': 'MIDDLE DISTRICT OF FLORIDA',
    r'M\.D\. GA\.': 'MIDDLE DISTRICT OF GEORGIA',
    r'M\.D\. LA\.': 'MIDDLE DISTRICT OF LOUISIANA',
    r'M\.D\.N\.C\.': 'MIDDLE DISTRICT OF NORTH CAROLINA',
    r'M\.D\. PA\.': 'MIDDLE DISTRICT OF PENNSYLVANIA',
    r'M\.D\. TENN\.': 'MIDDLE DISTRICT OF TENNESSEE',
    r'N\.D\. ALA\.': 'NORTHERN DISTRICT OF ALABAMA',
    r'N\.D\. CAL\.': 'NORTHERN DISTRICT OF CALIFORNIA',
    r'N\.D\. FLA\.': 'NORTHERN DISTRICT OF FLORIDA',
    r'N\.D\. GA\.': 'NORTHERN DISTRICT OF GEORGIA',
    r'N\.D\. ILL\.': 'NORTHERN DISTRICT OF ILLINOIS',
    r'N\.D\. IND\.': 'NORTHERN DISTRICT OF INDIANA',
    r'N\.D\. IOWA': 'NORTHERN DISTRICT OF IOWA',
    r'N\.D\. MISS\.': 'NORTHERN DISTRICT OF MISSISSIPPI',
    r'N\.D\.N\.Y\.': 'NORTHERN DISTRICT OF NEW YORK',
    r'N\.D\. OHIO': 'NORTHERN DISTRICT OF OHIO',
    r'N\.D\. OKLA\.': 'NORTHERN DISTRICT OF OKLAHOMA',
    r'N\.D\. TEX\.': 'NORTHERN DISTRICT OF TEXAS',
    r'N\.D\.W\. VA\.': 'NORTHERN DISTRICT OF WEST VIRGINIA',
    r'S\.D\. ALA\.': 'SOUTHERN DISTRICT OF ALABAMA',
    r'S\.D\. CAL\.': 'SOUTHERN DISTRICT OF CALIFORNIA',
    r'S\.D\. FLA\.': 'SOUTHERN DISTRICT OF FLORIDA',
    r'S\.D\. GA\.': 'SOUTHERN DISTRICT OF GEORGIA',
    r'S\.D\. IND\.': 'SOUTHERN DISTRICT OF INDIANA',
    r'S\.D\. IOWA': 'SOUTHERN DISTRICT OF IOWA',
    r'S\.D\. MISS\.': 'SOUTHERN DISTRICT OF MISSISSIPPI',
    r'S\.D\.N\.Y\.': 'SOUTHERN DISTRICT OF NEW YORK',
    r'S\.D\. OHIO': 'SOUTHERN DISTRICT OF OHIO',
    r'S\.D\. TEX\.': 'SOUTHERN DISTRICT OF TEXAS',
    r'S\.D\.W\. VA\.': 'SOUTHERN DISTRICT OF WEST VIRGINIA',
    r'W\.D\. ARK\.': 'WESTERN DISTRICT OF ARKANSAS',
    r'W\.D\. KY\.': 'WESTERN DISTRICT OF KENTUCKY',
    r'W\.D\. LA\.': 'WESTERN DISTRICT OF LOUISIANA',
    r'W\.D\. MICH\.': 'WESTERN DISTRICT OF MICHIGAN',
    r'W\.D\. MO\.': 'WESTERN DISTRICT OF MISSOURI',
    r'W\.D\.N\.Y\.': 'WESTERN DISTRICT OF NEW YORK',
    r'W\.D\.N\.C\.': 'WESTERN DISTRICT OF NORTH CAROLINA',
    r'W\.D\. OKLA\.': 'WESTERN DISTRICT OF OKLAHOMA',
    r'W\.D\. PA\.': 'WESTERN DISTRICT OF PENNSYLVANIA',
    r'W\.D\. TENN\.': 'WESTERN DISTRICT OF TENNESSEE',
    r'W\.D\. TEX\.': 'WESTERN DISTRICT OF TEXAS',
    r'W\.D\. VA\.': 'WESTERN DISTRICT OF VIRGINIA',
    r'W\.D\. WASH\.': 'WESTERN DISTRICT OF WASHINGTON',
    r'W\.D\. WIS\.': 'WESTERN DISTRICT OF WISCONSIN',
    r'D\. ALASKA': 'DISTRICT OF ALASKA',
    r'D\. ARIZ\.': 'DISTRICT OF ARIZONA',
    r'D\. COLO\.': 'DISTRICT OF COLORADO',
    r'D\. CONN\.': 'DISTRICT OF CONNECTICUT',
    r'D\.D\.C\.': 'DISTRICT OF COLUMBIA',
    r'D\. DEL\.': 'DISTRICT OF DELAWARE',
    r'D\. GUAM': 'DISTRICT OF GUAM',
    r'D\. HAW\.': 'DISTRICT OF HAWAII',
    r'D\. IDAHO': 'DISTRICT OF IDAHO',
    r'D\. KAN\.': 'DISTRICT OF KANSAS',
    r'D\. ME\.': 'DISTRICT OF MAINE',
    r'D\. MD\.': 'DISTRICT OF MARYLAND',
    r'D\. MASS\.': 'DISTRICT OF MASSACHUSETTS',
    r'D\. MINN\.': 'DISTRICT OF MINNESOTA',
    r'D\. MONT\.': 'DISTRICT OF MONTANA',
    r'D\. NEB\.': 'DISTRICT OF NEBRASKA',
    r'D\. NEV\.': 'DISTRICT OF NEVADA',
    r'D\.N\.H\.': 'DISTRICT OF NEW HAMPSHIRE',
    r'D\.N\.J\.': 'DISTRICT OF NEW JERSEY',
    r'D\.N\.M\.': 'DISTRICT OF NEW MEXICO',
    r'D\.N\.D\.': 'DISTRICT OF NORTH DAKOTA',
    r'D\. OR\.': 'DISTRICT OF OREGON',
    r'D\.P\.R\.': 'DISTRICT OF PUERTO RICO',
    r'D\.R\.I\.': 'DISTRICT OF RHODE ISLAND',
    r'D\.S\.C\.': 'DISTRICT OF SOUTH CAROLINA',
    r'D\.S\.D\.': 'DISTRICT OF SOUTH DAKOTA',
    r'D\.C\.Z\.': 'DISTRICT OF THE CANAL ZONE',
    r'D\.N\. MAR\. IS\.': 'DISTRICT OF THE NORTHERN MARIANA ISLANDS',
    r'D\.V\.I\.': 'DISTRICT OF THE VIRGIN ISLANDS',
    r'D\. UTAH': 'DISTRICT OF UTAH',
    r'D\. VT\.': 'DISTRICT OF VERMONT',
    r'D\. WYO\.': 'DISTRICT OF WYOMING'}
_USER_AGENT: str = 'courtpy (https://github.com/WithPrecedent/courtpy)'
