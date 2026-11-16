"""Tests the jcs module."""

from __future__ import annotations

import io
import pathlib
import zipfile

import amos
import pandas as pd
import pytest
from conftest import Site

import courtpy
from courtpy import jcs, politics

PAGE = 'https://epstein.wustl.edu/jcs'
ARCHIVE = 'https://epstein.wustl.edu/s/JCS2024.zip'
JUDGES = pd.DataFrame({
    '': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    'name': [
        'Lynch, Mary Ann', 'Smith, Milton D., Jr.', 'Smith, N. Roy',
        'Fiélds, Ray Lanier, III', 'Fields, Ray Lanier, III', 'Woods, Dana',
        'Kerner, Otto, Jr.', 'Kerner, Otto', 'Lynhc, Mary', 'Nobody, Ann'],
    'circuit': [1, 9, 9, 5, 11, 1, 7, 7, 1, 1],
    'jcs': [-0.4, 0.5, 0.6, -0.1, -0.1, 0.2, -0.3, -0.3, -0.4, 0.0]})
JUSTICES = pd.DataFrame({
    '': [1, 2, 3],
    'term': [2020, 2021, 2022],
    'justiceName': ['ACBarrett', 'ACBarrett', 'ACBarrett'],
    'jcs': [0.43, 0.44, 0.39]})
MEDIANS = pd.DataFrame({
    '': [1, 2, 3],
    'year': [1924, 1924, 1925],
    'term': [None, None, None],
    'congress': [68, 68, 69],
    'president': [0.4, 0.44, 0.4],
    'house_median': [0.2, 0.2, 0.26],
    'senate_median': [0.22, 0.22, 0.22],
    'sc_median': [None, None, 0.1],
    'circuit_median3': [0.43, 0.43, 0.43],
    'circuit_sd3': [None, None, 0.1]})


def archive(skipped: str | None = None) -> bytes:
    """Returns an archive of scores in the layout of the 2024 release."""
    contents = {
        'coa_judges_2024': JUDGES,
        'jcs medians': MEDIANS,
        'jcs_supreme_court_2024_long': JUSTICES,
        'jcs_supreme_court_2024_wide': pd.DataFrame({'justiceName': ['ACBarrett']})}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as packed:
        for name, table in contents.items():
            if name == skipped:
                continue
            csv = table.to_csv(index = False).encode('utf-8')
            packed.writestr(f'jcs 2024/csv/{name}.csv', csv)
            packed.writestr(f'jcs 2024/stata/{name}.dta', b'not a csv')
            # The hidden files that a Mac adds have the same names.
            packed.writestr(f'__MACOSX/jcs 2024/csv/._{name}.csv', b'\x00\x05')
    return buffer.getvalue()


@pytest.fixture
def site() -> Site:
    """Returns a session that serves the page and archive of scores."""
    return Site({
        PAGE: (
            '<html><body><a href="/s/JCS.pdf">here</a> for the article. '
            '<a href="/s/JCS2024.zip">here</a> for the data.</body></html>'),
        ARCHIVE: archive()})


def test_download(site: Site, tmp_path: pathlib.Path) -> None:
    # judicial-common-space keeps the files in the "jcs" folder of the folder.
    paths = jcs.download(tmp_path, session = site)
    assert list(paths) == ['judges', 'justices', 'medians']
    assert [p.name for p in paths.values()] == ['judges.csv', 'justices.csv', 'medians.csv']
    assert {p.parent for p in paths.values()} == {tmp_path / 'jcs'}
    assert (tmp_path / 'jcs' / 'JCS2024.zip').is_file()
    # The archive is found by its link on the page.
    assert site.urls == [PAGE, ARCHIVE]
    assert pd.read_csv(paths['justices'])['justiceName'].tolist() == ['ACBarrett'] * 3
    # Files that are there are not downloaded again unless asked.
    jcs.download(tmp_path, session = site)
    assert len(site.urls) == 2
    jcs.download(tmp_path, kinds = 'judges', overwrite = True, session = site)
    assert site.urls[2:] == [PAGE, ARCHIVE]
    assert list(jcs.download(tmp_path, kinds = ['medians'], session = site)) == ['medians']
    # The default folder is outside of any project.
    assert jcs.download(session = site)['judges'].parent == courtpy.utilities.data_folder() / 'jcs'


def test_download_identifies_courtpy(site: Site, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setattr(courtpy.utilities.requests, 'Session', lambda: site)
    jcs.download(tmp_path)
    assert site.headers == {'User-Agent': courtpy.options._USER_AGENT}


def test_download_fails_clearly(site: Site, tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match = 'kinds'):
        jcs.download(tmp_path, kinds = 'presidents', session = site)
    site.pages[ARCHIVE] = archive(skipped = 'jcs medians')
    with pytest.raises(ValueError, match = 'no CSV file of medians'):
        jcs.download(tmp_path, session = site)
    site.pages[PAGE] = '<a href="/s/JCS.pdf">here</a>'
    with pytest.raises(ValueError, match = 'no link to an archive'):
        jcs.download(tmp_path / 'other', session = site)
    with pytest.raises(RuntimeError, match = '503'):
        jcs.download(tmp_path / 'third', session = Site(site.pages, status = 503))


def test_medians(site: Site, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'medians.csv'
    MEDIANS.to_csv(path, index = False)
    table = jcs.medians(path).set_index('year')
    assert list(table.columns) == [
        'jcs_president', 'jcs_house_median', 'jcs_senate_median',
        'jcs_supreme_court_median', 'jcs_circuit3_median', 'jcs_circuit3_sd']
    # A year with two rows has their means.
    assert table.loc[1924, 'jcs_president'] == pytest.approx(0.42)
    assert pd.isna(table.loc[1924, 'jcs_supreme_court_median'])
    assert table.loc[1925, 'jcs_circuit3_sd'] == 0.1
    with pytest.raises(KeyError, match = 'year'):
        jcs.medians(MEDIANS.drop(columns = 'year'))
    # Without a file, the current one is downloaded.
    monkeypatch.setattr(courtpy.utilities.requests, 'Session', lambda: site)
    assert jcs.medians().equals(jcs.medians(path))
    assert site.urls == [PAGE, ARCHIVE]


def test_build_table_adds_medians() -> None:
    table = politics.build_table(False, False, common_space = MEDIANS).set_index('year')
    assert 'jcs_house_median' in table.columns and 'president_party' in table.columns
    assert table.loc[1933, 'president_party'] == -1
    assert table.loc[1925, 'jcs_house_median'] == 0.26


def test_download_jcs(site: Site, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    assert amos.library.classify('download_jcs') == 'reference_loader'
    monkeypatch.setattr(courtpy.utilities.requests, 'Session', lambda: site)
    medians = jcs.DownloadJcs().apply(None, source = str(tmp_path))
    assert medians.data.equals(jcs.medians(tmp_path / 'jcs' / 'medians.csv'))
    justices = jcs.DownloadJcs().apply(None, source = str(tmp_path), kind = 'justices')
    assert justices.data['justiceName'].tolist() == ['ACBarrett'] * 3
    assert site.urls == [PAGE, ARCHIVE]
    jcs.DownloadJcs().apply(None, source = str(tmp_path), refresh = 'true')
    assert site.urls[2:] == [PAGE, ARCHIVE]
    with pytest.raises(ValueError, match = 'kinds'):
        jcs.DownloadJcs().apply(None, source = str(tmp_path), kind = 'presidents')
