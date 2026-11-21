"""Tests the utilities module."""

from __future__ import annotations

import datetime
import pathlib
import zipfile

import nagata
import pandas as pd
import pytest
from conftest import Site

import courtpy
from courtpy import utilities


@pytest.mark.parametrize(('text', 'expected'), [
    ('March 3, 2009, Argued', '2009-03-03'),
    ('Decided: Sept. 5 2010', '2010-09-05'),
    ('filed 2020-01-31', '2020-01-31'),
    ('February 30, 2010', None),
    ('no date here', None),
    (None, None)])
def test_parse_date(text: str | None, expected: str | None) -> None:
    assert utilities.parse_date(text) == expected


def test_to_bool() -> None:
    assert utilities.to_bool('TRUE') and utilities.to_bool('yes') and utilities.to_bool(1)
    assert not utilities.to_bool('FALSE') and not utilities.to_bool('') and not utilities.to_bool(None)
    with pytest.raises(ValueError, match = 'not TRUE or FALSE'):
        utilities.to_bool('perhaps')


def test_listify_and_normalize() -> None:
    assert utilities.listify('a, b,,c ') == ['a', 'b', 'c']
    assert utilities.listify(None) == []
    assert utilities.listify(['x', ' y']) == ['x', 'y']
    assert utilities.listify(7) == ['7']
    assert utilities.normalize(' a\n\tb  c ') == 'a b c'
    assert utilities.normalize(None) == ''


def test_expand_courts() -> None:
    courts = utilities.expand_courts('federal_appellate, scotus, ca1')
    assert courts[:2] == ['ca1', 'ca2'] and courts[-1] == 'scotus' and len(courts) == 14
    geographic = utilities.expand_courts('federal_geographic_circuits')
    assert len(geographic) == 12 and 'cadc' in geographic and 'cafc' not in geographic
    with pytest.raises(ValueError, match = 'name at least one court'):
        utilities.expand_courts('')


def test_folders_follow_environment(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(courtpy.options._ENV_CONFIG, str(tmp_path / 'c'))
    monkeypatch.setenv(courtpy.options._ENV_DATA, str(tmp_path / 'd'))
    assert utilities.config_folder() == tmp_path / 'c'
    assert utilities.data_folder() == tmp_path / 'd'
    monkeypatch.delenv(courtpy.options._ENV_CONFIG)
    assert utilities.config_folder().name == 'courtpy'
    # Otherwise, the data folder is "courts" in the amos workspace's data.
    monkeypatch.delenv(courtpy.options._ENV_DATA)
    monkeypatch.setenv('AMOS_WORKSPACE', str(tmp_path / 'w'))
    assert utilities.data_folder() == tmp_path / 'w' / 'data' / 'courts'


def test_open_session(monkeypatch: pytest.MonkeyPatch) -> None:
    # Without a session, one that identifies courtpy is made.
    site = Site({})
    monkeypatch.setattr(utilities.requests, 'Session', lambda: site)
    assert utilities.open_session() is site and utilities.open_session(site) is site
    assert site.headers == {'User-Agent': courtpy.options._USER_AGENT}


def test_read_csv(tmp_path: pathlib.Path) -> None:
    table = pd.DataFrame({'name': ['Peña', 'Lynch'], 'nid': [1, 2]})
    for encoding in ('utf-8', 'utf-8-sig', 'cp1252'):
        path = tmp_path / f'{encoding}.csv'
        table.to_csv(path, index = False, encoding = encoding)
        assert utilities.read_csv(path).equals(table)
    assert list(utilities.read_csv(path, dtype = str)['nid']) == ['1', '2']
    # A zip archive of one file is read as that file.
    with zipfile.ZipFile(tmp_path / 'table.csv.zip', 'w') as archive:
        archive.writestr('table.csv', table.to_csv(index = False).encode('cp1252'))
    assert utilities.read_csv(tmp_path / 'table.csv.zip').equals(table)


def test_locate(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    clerk = nagata.FileManager(root_folder = tmp_path, input_folder = 'data')
    (tmp_path / 'here.csv').write_text('a\n1\n', encoding = 'utf-8')
    # A file in the current folder is used, and otherwise the input folder.
    assert utilities.locate('here.csv', clerk) == pathlib.Path('here.csv')
    assert utilities.locate('there.csv', clerk) == pathlib.Path(clerk.input_folder) / 'there.csv'
    assert utilities.locate(tmp_path / 'there.csv', clerk) == tmp_path / 'there.csv'
    assert utilities.locate('there.csv') == pathlib.Path('there.csv')


@pytest.mark.parametrize(('value', 'expected'), [
    (None, True), (False, True), ('', True), (' None ', True), ('FALSE', True), ('no', True),
    ('0', True), ('bulk', False), ('code_outcome', False), (True, False)])
def test_is_none_setting(value: object, expected: bool) -> None:
    assert utilities.is_none_setting(value) is expected


def test_to_date_and_to_integer() -> None:
    assert utilities.to_date('2019-01-01') == '2019-01-01'
    assert utilities.to_date(datetime.datetime(2019, 1, 1, 5)) == '2019-01-01'
    assert utilities.to_date('') is None and utilities.to_date(None) is None
    assert utilities.to_integer('500') == 500 and utilities.to_integer(7) == 7
    assert utilities.to_integer('') is None
    with pytest.raises(ValueError):
        utilities.to_integer('many')
