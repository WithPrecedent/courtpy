"""Tests the base classes of sources and ways to download."""

from __future__ import annotations

import abc
import argparse
import dataclasses
import pathlib
from collections.abc import Iterator, MutableMapping
from typing import Any, ClassVar

import pytest

import courtpy
from courtpy import cli, loaders, options, parsers
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
def restore_registries() -> Iterator[None]:
    """Removes the sources and ways to download that a test adds."""
    sources, downloads = dict(base.SOURCES), dict(base.DOWNLOADS)
    yield
    base.SOURCES.clear()
    base.SOURCES.update(sources)
    base.DOWNLOADS.clear()
    base.DOWNLOADS.update(downloads)


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


def make_recorder(
    calls: list[dict[str, Any]],
    *,
    saves: str = 'court_listener') -> type[base.Download]:
    """Returns a way to download, "recorded", that records what it is asked."""

    @dataclasses.dataclass
    class Recorded(base.Download):
        """Records the downloads it is asked for."""

        source: ClassVar[str] = saves

        @classmethod
        def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
            parser.add_argument('--parties')

        def download(self, folder: pathlib.Path, **kwargs: Any) -> list[pathlib.Path]:
            kwargs['folder'] = folder
            if kwargs.get('bulk_folder'):
                kwargs['bulk_folder'] = self.locate(kwargs['bulk_folder'])
            calls.append(kwargs)
            return []

    return Recorded


def test_courtpy_registers_its_own() -> None:
    assert base.SOURCES['court_listener'] is courtpy.courtlistener.CourtListenerSource
    assert base.SOURCES['lexis_nexis'] is courtpy.lexis.LexisNexisSource
    assert base.DOWNLOADS['bulk'] is courtpy.bulk.BulkDownload
    assert base.DOWNLOADS['true'] is courtpy.bulk.BulkDownload
    assert base.DOWNLOADS['api'] is courtpy.courtlistener.ApiDownload
    assert base.find_download(' BULK ') is courtpy.bulk.BulkDownload
    assert courtpy.Source is base.Source and courtpy.Download is base.Download


def test_subclasses_register() -> None:
    assert base.SOURCES['state_court_test'] is StateCourtTest

    @dataclasses.dataclass
    class Middle(base.Source, abc.ABC):
        """A base class for other sources, which is not added."""

    @dataclasses.dataclass
    class StateDownload(base.Download):
        """Downloads a state court's cases."""

        name: ClassVar[str] = 'state'
        aliases: ClassVar[tuple[str, ...]] = ('texas',)
        source: ClassVar[str] = 'state_court_test'

        def download(self, folder: pathlib.Path, **kwargs: Any) -> list[pathlib.Path]:
            return []

    @dataclasses.dataclass
    class MiddleDownload(base.Download, abc.ABC):
        """A base class for other ways to download, which is not added."""

    assert 'middle' not in base.SOURCES
    assert 'middle_download' not in base.DOWNLOADS
    assert base.find_download('texas') is StateDownload
    assert StateDownload.describe() == "Downloads a state court's cases."
    with pytest.raises(ValueError, match = '"api", "bulk", "state", or "none"'):
        base.find_download('ftp')
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
    with pytest.raises(ValueError, match = 'saves court_listener cases'):
        LoadStateCourt().apply(None, source = state_folder, download = 'bulk')


def test_loader_passes_options(
    court_listener_folder: pathlib.Path,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    make_recorder(calls)
    monkeypatch.chdir(tmp_path)
    loader = loaders.LoadCourtListener()
    loader.apply(
        None, source = court_listener_folder, download = 'recorded',
        courts = 'first_circuit_test, ca2', start_date = '2020-01-01 00:00:00',
        max_cases = '5', overwrite = 'yes', parties = 'United States',
        bulk_folder = 'bulk_files', rulebooks = 'federal')
    call = calls[0]
    assert call['folder'] == court_listener_folder
    assert call['courts'] == ['first_circuit_test', 'ca2']
    assert call['start_date'] == '2020-01-01' and call['end_date'] is None
    assert call['max_cases'] == 5 and call['overwrite'] is True
    assert call['parties'] == 'United States'
    assert call['bulk_folder'] == pathlib.Path(loader._get_clerk().input_folder) / 'bulk_files'
    assert 'rulebooks' not in call


def test_lexis_loader_refuses_other_sources(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match = 'reads lexis_nexis cases'):
        loaders.LoadLexisNexis().apply(None, source = tmp_path, download = 'bulk')


def test_download_command(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[dict[str, Any]] = []
    make_recorder(calls, saves = 'lexis_nexis')
    monkeypatch.chdir(tmp_path)
    assert cli.main([
        '-q', 'download', 'recorded', '--courts', 'federal_appellate', '--parties', 'US',
        '--max-cases', '3']) == 0
    call = calls[0]
    assert call['folder'] == pathlib.Path('lexis_nexis')
    assert call['courts'][:2] == ['ca1', 'ca2']
    assert call['parties'] == 'US' and call['max_cases'] == 3
    assert 'command' not in call and 'quiet' not in call
    assert '0 cases saved in lexis_nexis' in capsys.readouterr().out


def test_download_command_needs_courts(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(['-q', 'download', 'bulk']) == 1
    assert 'name at least one court' in capsys.readouterr().err
