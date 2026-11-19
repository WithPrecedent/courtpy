"""Tests the politics module."""

from __future__ import annotations

import pathlib

import amos
import pandas as pd
import pytest
from conftest import Site

import courtpy
from courtpy import politics

MQ_PAGE = 'https://mqscores.wustl.edu/measures.php'
MQ_JUSTICES = 'https://mqscores.wustl.edu/media/2024/justices.csv'
VOTEVIEW = 'https://voteview.com/static/data/out/members/HSall_members.csv'
# The links of the page of Martin-Quinn scores, which are to a folder named
# for the year of the release.
MQ_LINKS = (
    '<html><body><h3>2024 JUSTICE DATA FILES</h3>'
    '<a href="media/2024/justices.csv">justices.csv</a>'
    '<a href="media/2024/justices.dta">justices.dta</a>'
    '<h3>2024 COURT DATA FILES</h3>'
    '<a href="media/2024/court.csv">court.csv</a>'
    '<a href="media/2023/2023_MQscores.zip">2023 MQ Scores Data</a></body></html>')


@pytest.fixture
def scores() -> pd.DataFrame:
    """Returns scores of justices like the Martin-Quinn "justices" file."""
    return pd.DataFrame({
        'term': [2020, 2021, 2020, 2020],
        'justice': [117, 117, 111, 108],
        'justiceName': ['ACBarrett', 'ACBarrett', 'JGRoberts', 'CThomas'],
        'post_mn': [0.961, 1.004, 0.3, 3.0],
        'post_sd': [0.309, 0.259, 0.2, 0.4],
        'post_med': [0.954, 1.002, 0.3, 3.0],
        'post_025': [0.394, 0.518, 0.0, 2.2],
        'post_975': [1.601, 1.514, 0.6, 3.8]})


@pytest.fixture
def members() -> pd.DataFrame:
    """Returns members of Congress like the Voteview file of their ideology."""
    return pd.DataFrame({
        'congress': [97, 97, 97, 97, 97, 97, 98, 98, 98],
        'chamber': ['President', 'Senate', 'Senate', 'Senate', 'House', 'House', 'Senate', 'House', 'House'],
        'nominate_dim1': [0.9, -0.4, 0.1, 0.3, -0.2, 0.4, 0.2, -0.5, -0.1],
        'nominate_dim2': [0.0, 0.5, 0.5, 0.5, 0.1, 0.1, 0.3, 0.2, 0.2]})


@pytest.fixture
def site(scores: pd.DataFrame, members: pd.DataFrame) -> Site:
    """Returns a session that serves the sources' pages and files."""
    return Site({
        MQ_PAGE: MQ_LINKS,
        MQ_JUSTICES: scores.to_csv(index = False),
        VOTEVIEW: members.to_csv(index = False)})


def test_techniques_are_in_the_library() -> None:
    for name in ('add_executive', 'add_legislature', 'add_high_court'):
        assert amos.library.classify(name) == 'merger'
    assert issubclass(politics.AddExecutive, politics.ByDate)


def test_presidents() -> None:
    table = politics.presidents()
    assert list(table.columns) == ['year', 'president_party']
    parties = table.set_index('year')['president_party']
    assert parties.index[0] == 1933
    # A president who takes office in a year is the president of that year.
    assert [parties[y] for y in (1980, 1981, 1992, 1993, 2008, 2009, 2020, 2021, 2025)] == [
        -1, 1, 1, -1, 1, -1, 1, -1, 1]
    assert list(politics.presidents(2000, 2002)['year']) == [2000, 2001, 2002]
    with pytest.raises(ValueError, match = 'knows the party'):
        politics.presidents(1900)
    with pytest.raises(ValueError, match = 'knows the party'):
        politics.presidents(end = parties.index[-1] + 1)


def test_presidents_reads_its_file(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    # The terms come from a file, to which a president can be added.
    terms = pd.read_csv(politics._PRESIDENTS_FILE)
    added = pd.DataFrame({'president': ['Next'], 'party': [-1], 'start_date': ['2029-01-20'], 'end_date': ['2033-01-20']})
    path = tmp_path / 'presidents.csv'
    pd.concat([terms, added]).to_csv(path, index = False)
    monkeypatch.setattr(politics, '_PRESIDENTS_FILE', path)
    table = politics.presidents(2028)
    assert table.to_dict('list') == {'year': [2028, 2029, 2030, 2031, 2032], 'president_party': [1, -1, -1, -1, -1]}
    assert table['president_party'].dtype == 'Int64'


def test_executives() -> None:
    table = politics.executives()
    assert list(table.columns) == ['executive_name', 'executive_ideology', 'start_date', 'end_date']
    assert table['start_date'].is_monotonic_increasing
    # Each term ends when the next begins.
    assert (table['end_date'].iloc[:-1].to_numpy() == table['start_date'].iloc[1:].to_numpy()).all()
    assert table.iloc[0]['executive_name'] == 'Franklin D. Roosevelt'
    assert set(table['executive_ideology']) == {-1, 1}


def test_legislatures(members: pd.DataFrame) -> None:
    table = politics.legislatures(members)
    assert list(table.columns) == ['congress', 'start_date', 'end_date', 'senate_ideology', 'house_ideology']
    assert list(table['congress']) == [97, 98]
    assert list(table['start_date'].dt.strftime('%Y-%m-%d')) == ['1981-01-03', '1983-01-03']
    assert list(table['end_date'].dt.strftime('%Y-%m-%d')) == ['1983-01-03', '1985-01-03']
    assert list(table['senate_ideology']) == pytest.approx([0.1, 0.2])
    assert list(table['house_ideology']) == pytest.approx([0.1, -0.3])
    # Before the Twentieth Amendment, a Congress first met on March 4.
    assert politics._first_day(73) == '1933-03-04'


def test_high_courts(scores: pd.DataFrame) -> None:
    table = politics.high_courts(scores)
    assert list(table.columns) == ['term', 'start_date', 'end_date', 'high_court_ideology']
    assert list(table['start_date'].dt.strftime('%Y-%m-%d')) == ['2020-10-01', '2021-10-01']
    assert list(table['end_date'].dt.strftime('%Y-%m-%d')) == ['2021-09-30', '2022-09-30']
    assert list(table['high_court_ideology']) == [0.961, 1.004]


def test_add_executive() -> None:
    cases = pd.DataFrame({
        'date_filed': ['2009-01-19', '2009-01-20', '2017-06-01', None, '1900-01-01'],
        'x': [1, 2, 3, 4, 5]}, index = pd.Index(list('abcde'), name = 'case_id'))
    dataset = courtpy.code(cases.copy(), 'add_executive')
    assert isinstance(dataset, courtpy.Cases)
    data = dataset.data
    # The day of an inauguration has the new president.
    assert list(data['executive_name'].iloc[:3]) == ['George W. Bush', 'Barack Obama', 'Donald J. Trump']
    assert list(data['executive_ideology'].iloc[:3]) == [1, -1, 1]
    assert data['executive_name'].iloc[3:].isna().all()
    assert list(data.index) == list('abcde')
    record = dataset.history[-1]
    assert (record['rows'], record['matched']) == (5, 3)
    # Another table of executives, and another column of dates.
    governors = pd.DataFrame({
        'executive_name': ['A', 'B'], 'executive_ideology': [1, -1],
        'start_date': ['2000-01-01', '2004-01-01'], 'end_date': ['2004-01-01', '2008-01-01']})
    data = politics.AddExecutive().apply(
        amos.Dataset(pd.DataFrame({'decided': ['2005-05-05']})), source = governors, date = 'decided',
        prefix = 'state_', indicator = 'known').data
    assert data.iloc[0].to_dict() == {
        'decided': '2005-05-05', 'state_executive_name': 'B', 'state_executive_ideology': -1, 'known': True}
    with pytest.raises(KeyError, match = 'date_filed'):
        politics.AddExecutive().apply(amos.Dataset(pd.DataFrame({'x': [1]})))
    with pytest.raises(KeyError, match = 'start_date'):
        politics.AddExecutive().apply(
            amos.Dataset(pd.DataFrame({'date_filed': ['2000-01-01']})), source = governors.drop(columns = 'start_date'))


def test_add_legislature_and_high_court(scores: pd.DataFrame, members: pd.DataFrame) -> None:
    cases = pd.DataFrame({'date_filed': ['1981-06-01', '1983-01-02', '1983-01-03', '2021-09-30', '2021-10-01']})
    data = politics.AddLegislature().apply(amos.Dataset(cases.copy()), source = politics.legislatures(members)).data
    # A Congress sits until the next one first meets.
    assert list(data['senate_ideology']) == pytest.approx([0.1, 0.1, 0.2, float('nan'), float('nan')], nan_ok = True)
    assert list(data['house_ideology'].iloc[:3]) == pytest.approx([0.1, 0.1, -0.3])
    data = politics.AddHighCourt().apply(amos.Dataset(cases.copy()), source = politics.high_courts(scores)).data
    # A term runs from October to September.
    assert pd.isna(data['high_court_ideology'].iloc[0])
    assert list(data['high_court_ideology'].iloc[3:]) == [0.961, 1.004]


def test_add_legislature_downloads_its_source(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(courtpy.utilities.requests, 'Session', lambda: site)
    cases = pd.DataFrame({'date_filed': ['1984-05-01']})
    data = courtpy.code(cases, ['add_legislature', 'add_high_court']).data
    assert data.loc[0, 'house_ideology'] == pytest.approx(-0.3)
    assert pd.isna(data.loc[0, 'high_court_ideology'])


def test_martin_quinn(scores: pd.DataFrame) -> None:
    table = politics.martin_quinn(scores)
    assert list(table.columns) == [
        'year', 'supreme_court_median', 'supreme_court_min', 'supreme_court_max']
    assert list(table['year']) == [2020, 2021]
    # Each term's scores are summaries of those of its justices.
    assert list(table['supreme_court_median']) == [0.961, 1.004]
    assert list(table['supreme_court_min']) == [0.3, 1.004]
    assert list(table['supreme_court_max']) == [3.0, 1.004]
    with pytest.raises(KeyError, match = 'Martin-Quinn'):
        politics.martin_quinn(scores.drop(columns = 'post_mn'))


def test_justices(scores: pd.DataFrame, tmp_path: pathlib.Path) -> None:
    path = tmp_path / 'justices.csv'
    scores.to_csv(path, index = False)
    table = politics.justices(path)
    assert list(table.columns) == ['term', 'justice', 'justiceName', 'martin_quinn', 'jcs']
    assert list(table['martin_quinn']) == [0.961, 1.004, 0.3, 3.0]
    # judicial-common-space puts the scores on the scale of the Judicial
    # Common Space, which is from -1 to 1, in the same order.
    common = table['jcs'].to_numpy()
    assert (abs(common) < 1).all()
    assert list(table['jcs'].rank()) == list(table['martin_quinn'].rank())
    with pytest.raises(KeyError, match = 'Martin-Quinn'):
        politics.justices(scores.drop(columns = 'post_mn'))
    # The scores have the Supreme Court Database's numbers for the justices,
    # so a merger adds them to its votes.
    votes = pd.DataFrame({'term': [2021, 2020, 2019], 'justice': [117, 111, 117], 'vote': [1, 2, 1]})
    merged = amos.mergers.MergeKeys().apply(votes, source = table, on = ['term', 'justice'])
    assert merged.data['martin_quinn'].tolist()[:2] == [1.004, 0.3]
    assert pd.isna(merged.data['martin_quinn'].iloc[2])
    assert merged.history[-1]['matched'] == 2


def test_nominate(members: pd.DataFrame) -> None:
    table = politics.nominate(members)
    assert list(table.columns) == ['year', 'senate_median', 'house_median']
    # The 97th Congress sat in 1981 and 1982, and the 98th in 1983 and 1984.
    assert list(table['year']) == [1981, 1982, 1983, 1984]
    assert list(table['senate_median']) == pytest.approx([0.1, 0.1, 0.2, 0.2])
    assert list(table['house_median']) == pytest.approx([0.1, 0.1, -0.3, -0.3])
    assert list(politics.nominate(members, score = 'nominate_dim2')['senate_median']) == [0.5, 0.5, 0.3, 0.3]
    with pytest.raises(KeyError, match = 'members of Congress'):
        politics.nominate(members, score = 'no_such_score')


def test_download(site: Site, tmp_path: pathlib.Path) -> None:
    paths = politics.download(tmp_path / 'scores', session = site)
    assert list(paths) == ['justices', 'congress']
    assert [p.name for p in paths.values()] == ['justices.csv', 'HSall_members.csv']
    assert all(p.is_file() for p in paths.values())
    # judicial-common-space keeps the files in the "politics" folder of the
    # folder.
    assert {p.parent for p in paths.values()} == {tmp_path / 'scores' / 'politics'}
    # The Martin-Quinn file is found by its link on its page.
    assert site.urls == [MQ_PAGE, MQ_JUSTICES, VOTEVIEW]
    # Files that are there are not downloaded again unless asked.
    politics.download(tmp_path / 'scores', session = site)
    assert len(site.urls) == 3
    politics.download(tmp_path / 'scores', kinds = 'congress', overwrite = True, session = site)
    assert site.urls[3:] == [VOTEVIEW]
    assert list(politics.download(tmp_path / 'one', kinds = ['justices'], session = site)) == ['justices']
    # The default folder is outside of any project.
    assert politics.download(session = site)['congress'].parent == (
        courtpy.utilities.data_folder() / 'politics')


def test_download_fails_clearly(site: Site, tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match = 'kinds'):
        politics.download(tmp_path, kinds = 'presidents', session = site)
    site.pages[MQ_PAGE] = '<a href="media/2024/court.csv">court.csv</a>'
    with pytest.raises(ValueError, match = "no link to 'justices.csv'"):
        politics.download(tmp_path, kinds = 'justices', session = site)
    assert not (tmp_path / 'politics' / 'justices.csv').exists()
    with pytest.raises(RuntimeError, match = '503'):
        politics.download(tmp_path, session = Site(site.pages, status = 503))


def test_build_table(scores: pd.DataFrame, members: pd.DataFrame, tmp_path: pathlib.Path) -> None:
    assert politics.build_table(False, False).equals(politics.presidents())
    path = tmp_path / 'justices.csv'
    scores.to_csv(path, index = False)
    table = politics.build_table(path, members).set_index('year')
    assert list(table.columns) == [
        'president_party', 'supreme_court_median', 'supreme_court_min',
        'supreme_court_max', 'senate_median', 'house_median']
    assert table.index.is_monotonic_increasing and table.index.is_unique
    assert table.loc[2020, 'supreme_court_median'] == 0.961
    assert table.loc[1981, 'senate_median'] == pytest.approx(0.1)
    assert pd.isna(table.loc[1981, 'supreme_court_median'])
    assert table.loc[1981, 'president_party'] == 1
    assert 'house_median' not in politics.build_table(scores, False).columns


def test_build_table_downloads_its_sources(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    # With no files, the sources' current files are downloaded, once.
    monkeypatch.setattr(courtpy.utilities.requests, 'Session', lambda: site)
    table = politics.build_table().set_index('year')
    assert table.loc[2020, 'supreme_court_median'] == 0.961
    assert table.loc[1983, 'house_median'] == pytest.approx(-0.3)
    assert site.headers == {'User-Agent': courtpy.options._USER_AGENT}
    folder = courtpy.utilities.data_folder() / 'politics'
    assert sorted(p.name for p in folder.iterdir()) == ['HSall_members.csv', 'justices.csv']
    asked = len(site.urls)
    assert politics.build_table(True, True).set_index('year').equals(table)
    assert len(site.urls) == asked
    assert list(politics.justices()['justice']) == [117, 117, 111, 108]


def test_load_and_download_politics(site: Site, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    assert amos.library.classify('load_politics') == 'reference_loader'
    assert amos.library.classify('download_politics') == 'reference_loader'
    monkeypatch.setattr(courtpy.utilities.requests, 'Session', lambda: site)
    dataset = politics.DownloadPolitics().apply(None, source = str(tmp_path))
    table = dataset.data.set_index('year')
    assert table.loc[2020, 'supreme_court_median'] == 0.961
    assert table.loc[1983, 'house_median'] == pytest.approx(-0.3)
    assert sorted(p.name for p in (tmp_path / 'politics').iterdir()) == [
        'HSall_members.csv', 'justices.csv']
    asked = len(site.urls)
    only = politics.DownloadPolitics().apply(None, source = str(tmp_path), congress = 'false')
    assert 'house_median' not in only.data.columns
    assert len(site.urls) == asked
    politics.DownloadPolitics().apply(
        None, source = str(tmp_path), supreme_court = False, refresh = True)
    assert site.urls[asked:] == [VOTEVIEW]
    # The table is made from the current files, or is a saved one.
    loaded = politics.LoadPolitics().apply(None, congress = 'false')
    assert 'supreme_court_median' in loaded.data.columns
    assert 'house_median' not in loaded.data.columns
    path = tmp_path / 'years.csv'
    table.reset_index().to_csv(path, index = False)
    saved = politics.LoadPolitics().apply(None, source = str(path))
    assert list(saved.data.columns) == ['year', *table.columns]
    assert saved.history[-1]['source'] == str(path)
