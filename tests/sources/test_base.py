"""Tests the base class of sources."""

from __future__ import annotations

import abc
import dataclasses
import pathlib
from collections.abc import Iterator, MutableMapping
from typing import Any, ClassVar

import pytest

import courtpy
from courtpy import cli, options, parsers
from courtpy.sources import base


@dataclasses.dataclass
class StateCourtTest(base.Source):
    """Reads a made-up state court's cases, saved as text files.

    It is defined at the top of the module so that processes that parse
    with it can import it.

    """

    pattern: ClassVar[str] = '*.txt'

    def read(self, path: pathlib.Path) -> courtpy.Case:
        text = path.read_text(encoding = 'utf-8')
        return courtpy.Case(
            id = path.stem, source = self.name, sections = {'opinion': text},
            metadata = {'source': self.name}, path = path)

    def finish(self, row: MutableMapping[str, Any]) -> None:
        row['state'] = 'Texas'


@pytest.fixture(autouse = True)
def restore_sources() -> Iterator[None]:
    """Removes the sources that a test adds."""
    sources = dict(base.SOURCES)
    yield
    base.SOURCES.clear()
    base.SOURCES.update(sources)


@pytest.fixture
def state_folder(tmp_path: pathlib.Path) -> pathlib.Path:
    """Returns a folder with two of the made-up state court's cases."""
    folder = tmp_path / 'state'
    folder.mkdir()
    (folder / 'a.txt').write_text('We affirm the judgment.', encoding = 'utf-8')
    (folder / 'b.txt').write_text('We reverse.', encoding = 'utf-8')
    hidden = folder / '.courtpy'
    hidden.mkdir()
    (hidden / 'place.txt').write_text('not a case', encoding = 'utf-8')
    return folder


def test_courtpy_registers_its_own() -> None:
    assert base.SOURCES['courtlistener'] is courtpy.courtlistener.CourtListenerSource
    assert base.SOURCES['lexis_nexis'] is courtpy.lexis.LexisNexisSource
    assert courtpy.Source is base.Source


def test_sources_name_their_header_rules() -> None:
    assert base.SOURCES['courtlistener'].header == 'courtlistener_header'
    assert base.SOURCES['lexis_nexis'].header == 'lexis_nexis_header'
    # A source with no header rules of its own has those that fit every one.
    assert StateCourtTest.header == base.Source.header == 'header'


def test_subclasses_register() -> None:
    assert base.SOURCES['state_court_test'] is StateCourtTest

    @dataclasses.dataclass
    class Middle(base.Source, abc.ABC):
        """A base class for other sources, which is not added."""

    assert 'middle' not in base.SOURCES
    with pytest.raises(ValueError, match = 'source must be one of'):
        base.find_source('ftp')


def test_find_files(state_folder: pathlib.Path) -> None:
    found = base.find_source('state_court_test').find_files(state_folder)
    assert [p.name for p in found] == ['a.txt', 'b.txt']
    assert parsers.find_files(state_folder, 'state_court_test') == found


@pytest.mark.parametrize('workers', [1, 2])
def test_parse_a_source_of_your_own(
    state_folder: pathlib.Path,
    workers: int,
    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(options, '_CHUNK_SIZE', 1)
    table = courtpy.parse(state_folder, source = 'state_court_test', workers = workers)
    assert list(table.index) == ['a', 'b']
    assert (table['state'] == 'Texas').all()


def test_parse_paths_and_one_file(state_folder: pathlib.Path) -> None:
    paths = [state_folder / 'b.txt', state_folder / 'a.txt']
    table = courtpy.parse(paths, source = 'state_court_test')
    assert list(table.index) == ['b', 'a']
    parser = courtpy.Parser.create()
    case_id, row = parser.parse_file(state_folder / 'a.txt', 'state_court_test')
    assert case_id == 'a' and row['state'] == 'Texas'


def test_loader_of_your_own(state_folder: pathlib.Path) -> None:
    @dataclasses.dataclass
    class LoadStateCourt(courtpy.SourceLoader):
        """Loads the made-up state court's cases."""

        reads: ClassVar[str] = 'state_court_test'

    dataset = LoadStateCourt().apply(None, source = state_folder, coders = 'none')
    assert len(dataset.data) == 2


def test_download_command_needs_courts(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(['-q', 'download']) == 1
    assert 'name at least one court' in capsys.readouterr().err
