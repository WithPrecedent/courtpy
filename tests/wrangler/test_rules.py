"""Tests the rules module: courtpy's rulebooks."""

from __future__ import annotations

import csv
import pathlib
import re
from typing import Any

import amos
import pandas as pd
import pytest

from courtpy import parsers, rules


def apply(name: str, **sections: str) -> dict[str, Any]:
    """Applies a rulebook to the sections of one case.

    Args:
        name: the name of the rulebook.
        **sections: the sections of text, by name.

    Returns:
        The columns that the rules made, with `None` for missing values.

    """
    table = pd.DataFrame({k: [v] for k, v in sections.items()}, dtype = 'str')
    _, made = parsers._apply(amos.parsers.Rulebook.create(name), table)
    return {
        k: None if pd.isna(v) else v for k, v in made.iloc[0].to_dict().items()}


def test_rulebooks_are_named() -> None:
    assert amos.library.classify('parse_federal') == 'parser'
    federal = amos.parsers.Rulebook.create('federal')
    assert len(federal) == len(amos.parsers.Rulebook.create(rules.RULEBOOKS['federal']))
    assert len(amos.parsers.Rulebook.create('lexis_nexis')) > 10
    with pytest.raises(FileNotFoundError, match = 'federal'):
        amos.parsers.Rulebook.create('no_such_rules')


def test_rule_files_are_general_then_federal() -> None:
    general, federal = rules._GENERAL, rules._INSTRUCTIONS / 'federal'
    assert rules.find_rule_files('criminal') == [
        general / 'criminal.csv', federal / 'criminal.csv']
    assert rules.find_rule_files('citations') == [general / 'citations.csv']
    assert rules.find_rule_files('agencies') == [federal / 'agencies.csv']
    assert rules.find_rule_files('criminal', None) == [general / 'criminal.csv']
    with pytest.raises(FileNotFoundError, match = 'no_such_topic'):
        rules.find_rule_files('no_such_topic')
    names = amos.parsers.Rulebook.create('criminal').names
    assert 'criminal_firearm' in names and 'criminal_acca' in names


def test_register_rulebooks(tmp_path: pathlib.Path) -> None:
    # A study's folders make a rulebook of each topic, applied in the order
    # of the folders, and one that combines them.
    general, texas = tmp_path / 'general', tmp_path / 'texas'
    general.mkdir()
    texas.mkdir()
    header = 'column,name,kind,pattern\n'
    (general / 'oil.csv').write_text(header + 'opinion,oil_well,flags,well\n', encoding = 'utf-8')
    (texas / 'oil.csv').write_text(header + 'opinion,oil_rrc,flags,Railroad Commission\n', encoding = 'utf-8')
    (texas / 'cattle.csv').write_text(header + 'opinion,cattle_brand,flags,brand\n', encoding = 'utf-8')
    books = rules.register_rulebooks(general, texas, combined = 'texas_all', prefix = 'texas')
    assert list(books) == ['texas_cattle', 'texas_oil', 'texas_all']
    assert books['texas_oil'].__name__ == 'ParseTexasOil'
    assert amos.parsers.Rulebook.create('texas_oil').names == ['oil_well', 'oil_rrc']
    assert amos.parsers.Rulebook.create('parse_texas_all').names == [
        'cattle_brand', 'oil_well', 'oil_rrc']
    assert amos.library.classify('parse_texas_cattle') == 'parser'
    assert list(rules.register_rulebooks(texas, topics = ['oil'])) == ['oil']
    with pytest.raises(FileNotFoundError, match = 'sheep'):
        rules.register_rulebooks(general, topics = ['sheep'])
    with pytest.raises(FileNotFoundError, match = 'no files of rules'):
        rules.register_rulebooks(tmp_path / 'empty')


def test_review_rules() -> None:
    found = apply(
        'review',
        opening_lines = (
            'Appeal from the United States District Court for the District of '
            'Massachusetts\n[Hon. William G. Young, U.S. District Judge]'),
        history = '', party = 'UNITED STATES, Appellee')
    assert found['review_district'] and not found['review_agency']
    assert found['district_judges'] == 'WILLIAM G YOUNG'
    found = apply(
        'review',
        opening_lines = 'On Petition for Review of an Order of the Board of Immigration Appeals',
        history = '', party = 'JOHN DOE, Petitioner')
    assert found['review_agency'] and found['review_immigration']
    assert not found['review_district'] and found['district_judges'] is None
    standards = apply('general', opinion = 'We review for plain error. Substantial evidence supports it.')
    assert standards['standard_plain_error'] and standards['standard_named']
    assert standards['standard_substantial_evidence'] and not standards['standard_de_novo']


def test_structure_files_are_by_source_and_courts() -> None:
    path = rules.find_structure_file('lexis_nexis', 'federal_appellate')
    assert path == rules._INSTRUCTIONS / 'sources' / 'lexis_nexis' / 'federal_appellate.csv'
    with pytest.raises(FileNotFoundError, match = 'state_trial'):
        rules.find_structure_file('lexis_nexis', 'state_trial')


def read_rows(path: Any) -> list[dict[str, str]]:
    """Returns the rows of a CSV file of rules.

    Args:
        path: the path of the file.

    Returns:
        The rows, as `dict`s by the names of the columns.

    """
    with path.open(encoding = 'utf-8-sig', newline = '') as file:
        return list(csv.DictReader(file))


def test_federal_files_do_not_repeat_general_rules() -> None:
    for path in sorted((rules._INSTRUCTIONS / 'federal').glob('*.csv')):
        general = rules._GENERAL / path.name
        if general.exists():
            names = {row['name'] for row in read_rows(general)}
            repeated = {row['name'] for row in read_rows(path)} & names
            assert not repeated, (path.name, repeated)


def test_rules_that_ignore_case_do_not_list_both_cases() -> None:
    both = re.compile(r'\[([A-Za-z])([A-Za-z])\]')
    for path in sorted(rules._INSTRUCTIONS.rglob('*.csv')):
        for row in read_rows(path):
            # The tables of courts and presidents are not rules.
            if 'flags' not in row or 'ignorecase' not in row['flags']:
                continue
            for first, second in both.findall(row['pattern']):
                assert first.lower() != second.lower(), (path, row['name'])


def test_files_named_twice_are_read_once() -> None:
    both = amos.parsers.Rulebook.create('civil', 'federal')
    assert len(both) == len(amos.parsers.Rulebook.create('federal'))


def test_built_in_rulebooks_are_valid() -> None:
    federal = amos.parsers.Rulebook.create('federal')
    lexis = amos.parsers.Rulebook.create('lexis_nexis')
    general_header = amos.parsers.Rulebook.create('header')
    lexis_header = amos.parsers.Rulebook.create('lexis_nexis_header')
    courtlistener_header = amos.parsers.Rulebook.create('courtlistener_header')
    assert len(federal) > 300
    for variable in (
        'opinion_reverse', 'criminal_firearm',
        'civil_titlevii', 'constitutional_amend4', 'citations_case',
        'citations_statute', 'agencies', 'review_district'):
        assert variable in federal.names
    # The header rules are applied by source, not with the federal rules.
    assert 'party1' not in federal.names and 'panel_judges' not in federal.names
    shared = (
        'party1', 'party2', 'panel_judges', 'authors', 'concurring',
        'dissenting', 'disposition_reverse', 'cite_federal_reporter', 'party1_appellant',
        'party2_united_states', 'counsel_us_attorney', 'docket_criminal',
        'party1_agencies', 'party2_agencies', 'history_agencies',
        'lower_court_num', 'lower_court_name')
    for book in (general_header, lexis_header, courtlistener_header):
        for variable in shared:
            assert variable in book.names
    for variable in ('court_num', 'court_name', 'notice_unpublished', 'future_grant', 'cite_lexis'):
        assert variable in lexis_header.names
        assert variable not in courtlistener_header.names
    assert 'caption' in courtlistener_header.names and 'caption' not in lexis_header.names
    assert 'agency' not in lexis_header.names
    assert lexis.names == [
        'header', 'opinion', 'party', 'court', 'docket_number', 'history',
        'future', 'counsel', 'notice', 'dates', 'disposition', 'citation',
        'judges', 'opinion_by', 'concurring_lines', 'dissenting_lines']
    # Several values in a cell are separated by "; ", with no line breaks in
    # the files (which a checkout on Windows would make "\r\n").
    for rule in [*federal, *lexis, *lexis_header, *courtlistener_header]:
        if rule.kind in ('names', 'matches'):
            assert rule.separator == '; '


def test_lexis_dates_are_lines() -> None:
    found = apply(
        'lexis_nexis',
        text = (
            '\nA v. B\n\nMarch 3, 2009, Argued\nJune 1, 2009, Decided\n'
            'JUDGES: Smith.\nOPINION\n\nWe affirm.\n'))
    assert found['dates'] == 'March 3, 2009, Argued; June 1, 2009, Decided'


@pytest.mark.parametrize(('judges', 'expected'), [
    # A middle initial "J." is not "Justice".
    ('PRESENT: DENNIS JACOBS, SARAH A. L. MERRIAM, Circuit Judges, LAWRENCE '
     'J. VILARDO, District Judge.',
     ['DENNIS JACOBS', 'SARAH A L MERRIAM', 'LAWRENCE J VILARDO']),
    # "JR." after a name is a suffix, and "S.R." before one is initials.
    ('Present: JOHN M. WALKER, JR., PIERRE N. LEVAL, MICHAEL H. PARK, Circuit '
     'Judges.', ['JOHN M WALKER', 'PIERRE N LEVAL', 'MICHAEL H PARK']),
    ('Before: S.R. THOMAS, BRESS, and DE ALBA, Circuit Judges.',
     ['SR THOMAS', 'BRESS', 'DE ALBA']),
    # "J." and "JJ." after names are still titles.
    ('ROBERTS, C. J., delivered the opinion of the Court, in which SCALIA, '
     'KENNEDY, and THOMAS, JJ., joined. GINSBURG, J., filed a dissenting '
     'opinion.', ['ROBERTS', 'SCALIA', 'KENNEDY', 'THOMAS', 'GINSBURG']),
    # CourtListener's list of judges can have words that are not names.
    ('Agee, Dismissed, King, Per Curiam, Thacker', ['AGEE', 'KING', 'THACKER']),
    ('Gregory, Keenan, Eastern, Curium', ['GREGORY', 'KEENAN'])])
def test_header_rules_split_judges(judges: str, expected: list[str]) -> None:
    found = apply('header', judges = judges)
    assert found['panel_judges'] == '; '.join(expected)


@pytest.mark.parametrize(('opening', 'expected'), [
    ('Before JORDAN, ROSENBAUM, and ABUDU, Circuit Judges. PER CURIAM: Doe '
     'appeals.', ['JORDAN', 'ROSENBAUM', 'ABUDU']),
    # A chief judge in the middle, an accent, and a judge by designation.
    ('Before Barron, Chief Judge, Gelpí and Montecalvo, Circuit Judges. Jane '
     'Roe, Assistant Federal Public Defender, for appellant.',
     ['BARRON', 'GELPÍ', 'MONTECALVO']),
    ('Before: PAEZ and OWENS, Circuit Judges, and SEEBORG,* Chief District '
     'Judge. Following a trial', ['PAEZ', 'OWENS', 'SEEBORG']),
    ('Before SYKES, Chief Judge, and BRENNAN and ST. EVE, Cir- cuit Judges. '
     'BRENNAN, Circuit Judge. Police stopped', ['SYKES', 'BRENNAN', 'ST EVE']),
    # The Seventh Circuit lists the judges with only spaces between them.
    ('Decided March 28, 2022 Before JOHN DOE, Circuit Judge AMY J. ST. ROE, '
     'Circuit Judge RICHARD ROE, Chief Judge No. 21-1819 UNITED STATES OF '
     'AMERICA, Plaintiff-Appellee, v. JANE DOE, Defendant-Appellant.',
     ['JOHN DOE', 'AMY J ST ROE', 'RICHARD ROE']),
    # Not a panel.
    ('Before April 25, 2016, Sabaini made deposits of over $2,000.', []),
    ('LYNCH, Circuit Judge. Before trial, Doe moved to suppress.', [])])
def test_header_rules_find_the_panel_in_the_opinion(
    opening: str,
    expected: list[str]) -> None:
    found = apply('header', opinion = opening)
    assert found['panel_judges'] == ('; '.join(expected) or None)


def test_header_rules_prefer_the_panel_in_the_opinion() -> None:
    # CourtListener's "judges" may name only the author.
    found = apply(
        'courtlistener_header',
        judges = 'Brennan',
        opinion = 'Before SYKES, Chief Judge, and BRENNAN and ST. EVE, Circuit '
                  'Judges. BRENNAN, Circuit Judge.')
    assert found['panel_judges'] == 'SYKES; BRENNAN; ST EVE'


@pytest.mark.parametrize(('opening', 'roles'), [
    # (party1 appellant, party1 appellee, party2 appellant, party2 appellee)
    ('In the United States Court of Appeals For the Eleventh Circuit ____ No. '
     '23-12565 ____ UNITED STATES OF AMERICA, Plaintiﬀ-Appellee, versus JOHN '
     'DOE, Defendant-Appellant. ____ Appeal from the United States District '
     'Court', (False, True, True, False)),
    # The government's appeal, with dashes around "v.".
    ('UNITED STATES OF AMERICA, Appellant, –v.– JOHN DOE, Defendant-Appellee. '
     'Before: LYNCH and PARK, Circuit Judges.', (True, False, False, True)),
    # A short title before the caption.
    ('22-1481 (L) United States v. Doe UNITED STATES COURT OF APPEALS FOR THE '
     'SECOND CIRCUIT August Term 2023 Docket No. 22-1481 UNITED STATES OF '
     'AMERICA, Appellee, v. JOHN DOE, AKA J. DOE, Defendant-Appellant.',
     (False, True, True, False)),
    # Docket numbers from another column between the role and "v.".
    ('UNITED STATES OF AMERICA, No. 23-481 D.C. No. Plaintiff - Appellee, '
     '3:18-cr-00136-SLG-1 v. MEMORANDUM* JOHN DOE, Jr., Defendant - '
     'Appellant. Appeal from', (False, True, True, False)),
    # One role, as the Third Circuit writes captions.
    ('NOT PRECEDENTIAL UNITED STATES COURT OF APPEALS FOR THE THIRD CIRCUIT '
     '____ No. 24-1625 ____ UNITED STATES OF AMERICA v. JOHN DOE, a/k/a '
     'Johnny, Appellant ____ Appeal from the United States District Court',
     (False, False, True, False)),
    # A citation and a party in the opinion's words are not a caption.
    ('LYNCH, Circuit Judge. Under United States v. Booker, 543 U.S. 220 '
     '(2005), the guidelines are advisory. The appellant argues that the '
     'district court erred. Appellee United States disagrees.',
     (False, False, False, False))])
def test_courtlistener_rules_find_the_caption_in_the_opinion(
    opening: str,
    roles: tuple[bool, bool, bool, bool]) -> None:
    found = apply('courtlistener_header', party = 'United States v. Doe', opinion = opening)
    assert (
        found['party1_appellant'], found['party1_appellee'],
        found['party2_appellant'], found['party2_appellee']) == roles
    assert (found['caption'] is None) == (roles == (False, False, False, False))


@pytest.mark.parametrize(('opening', 'expected'), [
    # The Seventh Circuit's orders print the caption in two columns, so the
    # district court's name falls between the roles and "v.".
    ('No. 10-2228 Appeal from the United States District UNITED STATES OF '
     'AMERICA, Court for the Northern District of Illinois, Plaintiff\u2010'
     'Appellee, Eastern Division. v. No. 09 CR 78\u20101 JOHN DOE, Jane Roe, '
     'Defendant\u2010Appellant. Judge. O R D E R John Doe pleaded guilty.',
     ('Plaintiff\u2010Appellee', True, False, False, False)),
    # "Appeal from the United States" is the district court, not the party,
    # even with the other party's name between the words.
    ('Appeal from the United States JOHN DOE, District Court for the '
     'Northern Petitioner-Appellant, District of Illinois. v. No. 14-3216 '
     'UNITED STATES OF AMERICA, Respondent-Appellee.',
     ('Respondent-Appellee', True, False, False, False)),
    # A government appeal, with the roles in a caption of numbered lines.
    ('UNITED STATES OF AMERICA, 13 14 Appellant, 15 16 -v.- 17 18 JOHN DOE, '
     '19 20 Defendant-Appellee.', ('Appellant', False, True, False, False)),
    # No caption: the opening's sentences say who appeals.
    ('PER CURIAM: John Doe, proceeding pro se, appeals from the order '
     'denying his motion.', (None, False, False, False, True)),
    ('PER CURIAM: Counsel for John Doe has filed a brief in accordance with '
     'Anders v. California, 386 U.S. 738 (1967).',
     (None, False, False, False, True)),
    ('SMITH, Circuit Judge: Defendant-appellant John Doe asserts that the '
     'search was unlawful.', (None, True, False, False, False)),
    ('MEMORANDUM The United States appeals from the sentence imposed on '
     'John Doe.', (None, False, False, True, False)),
    # An earlier appeal is not this one, and a citation is not a party.
    ('The government appealed the sentence, and we reversed. Under United '
     'States v. Booker, 543 U.S. 220 (2005), the guidelines are advisory.',
     (None, False, False, False, False))])
def test_general_rules_find_who_appeals_in_the_opening(
    opening: str,
    expected: tuple[str | None, bool, bool, bool, bool]) -> None:
    found = apply('courtlistener_header', party = 'United States v. Doe', opinion = opening)
    assert (
        found['opening_united_states_role'],
        found['opening_defendant_appellant'],
        found['opening_defendant_appellee'],
        found['opening_government_appeals'],
        found['opening_party_appeals']) == expected


def test_courtlistener_rules_keep_the_caption_of_the_header() -> None:
    found = apply(
        'courtlistener_header',
        party = 'Mary SMITH, Plaintiff-Appellant, v. ACME CORP., Defendant-Appellee',
        opinion = 'ACME CORP., Plaintiff-Appellee, v. MARY SMITH, Defendant-Appellant.')
    assert found['caption'].startswith('Mary SMITH')
    assert found['party1_appellant'] and found['party2_appellee']
    assert not found['party1_appellee'] and not found['party2_appellant']


@pytest.mark.parametrize(('court', 'number', 'name'), [
    ('UNITED STATES COURT OF APPEALS FOR THE TENTH CIRCUIT', 10, 'tenth_circuit'),
    # The D.C. Circuit is not the District of Columbia's district court.
    ('UNITED STATES COURT OF APPEALS FOR THE DISTRICT OF COLUMBIA CIRCUIT', 12, 'dc_circuit'),
    ('UNITED STATES BANKRUPTCY APPELLATE PANEL OF THE NINTH CIRCUIT', 110,
     'bankruptcy_appellate_panel_ninth_circuit'),
    ('TEMPORARY EMERGENCY COURT OF APPEALS', 105, 'temporary_emergency_court_of_appeals'),
    ('UNITED STATES COURT OF APPEALS FOR THE STATE OF NOWHERE', None, None)])
def test_lexis_rules_find_the_court(court: str, number: int | None, name: str | None) -> None:
    found = apply('lexis_nexis_header', court = court)
    assert (found['court_num'], found['court_name']) == (number, name)


def test_court_rules_are_made_from_the_table_of_courts() -> None:
    made = rules.make_court_rules()
    assert {rule['name'] for rule in made} == {'court_num', 'court_name'}
    assert {rule['column'] for rule in made} == {'court'}
    lower = rules.make_court_rules(column = 'history', prefix = 'lower_', levels = ('trial',))
    assert {rule['name'] for rule in lower} == {'lower_court_num', 'lower_court_name'}
    assert 'tenth_circuit' not in {rule['value'] for rule in lower}
    assert rules.make_court_rules('nowhere') == []


@pytest.mark.parametrize(('history', 'name'), [
    ('Appeal from the United States District Court for the District of Colorado.',
     'district_of_colorado'),
    # Lexis abbreviations, after an earlier appeal that is not the court below.
    ('(D.C. No. CR 05-0916 JH). (D. New Mexico). United States v. Mora, 262 Fed. '
     'Appx. 864, 2008 U.S. App. LEXIS 2334 (10th Cir. N.M., 2008)', 'district_of_new_mexico'),
    ('(D. of Kan.). (D.C. No.08-CR-10010-WEB-1).', 'district_of_kansas'),
    ('(W.D. Oklahoma). (D.C. No. 5:03-cr-00243-F-1).', 'western_district_of_oklahoma'),
    ('(D. N.M.). (D.Ct. No. 1:06-CR-01622-MCA-1).', 'district_of_new_mexico'),
    ('Logan v. Sabre, Inc., 2008 U.S. Dist. LEXIS 37749 (N.D. Okla., May 7, 2008)',
     'northern_district_of_oklahoma'),
    ('(BAP No. NO-07-057). (BAP). In re Tollefsen, 397 B.R. 545 (B.A.P. 10th Cir., 2008)',
     'bankruptcy_appellate_panel_tenth_circuit'),
    # Only an earlier appeal, or an agency.
    ('United States v. Collins, 511 F.3d 1276, 2008 U.S. App. LEXIS 174 (10th Cir. Okla., 2008)',
     None),
    ('Petition for review of an order of the Board of Immigration Appeals.', None)])
def test_header_rules_find_the_lower_court(history: str, name: str | None) -> None:
    found = apply('header', history = history)
    assert found['lower_court_name'] == name
    assert (found['lower_court_num'] is None) == (name is None)


@pytest.mark.parametrize(('party', 'history', 'expected'), [
    ('ACME CORP., Petitioner, v. NATIONAL LABOR RELATIONS BOARD, Respondent.',
     'Petition for review of an order of the National Labor Relations Board.',
     (None, 'National Labor Relations Board', 'National Labor Relations Board')),
    # A company named for an agency's abbreviation, and an agency before "et al.".
    ('PACIFIC GAS COMPANY; FMC WYOMING CORPORATION, Petitioners, v. UNITED STATES '
     'DEPARTMENT OF LABOR et al., Respondents', '',
     (None, 'Department of Labor', None)),
    # An agency between parties, and a judge's initials in a docket number.
    ('JOHN DOE, Plaintiff-Appellant, v. UNITED STATES OF AMERICA; FEDERAL BUREAU OF '
     'PRISONS; ERIC H. HOLDER, JR., Attorney General, Defendants-Appellees.',
     'D.C. No. 2:08-cr-00021-FMC-1. (D.C. No. 06-CR-126-CAB).',
     (None, 'Bureau of Prisons', None))])
def test_header_rules_find_agencies_that_are_parties(
    party: str,
    history: str,
    expected: tuple[str | None, str | None, str | None]) -> None:
    found = apply('header', party = party, history = history)
    assert (
        found['party1_agencies'], found['party2_agencies'], found['history_agencies']) == expected


@pytest.mark.parametrize(('party', 'expected'), [
    ('UNITED STATES OF AMERICA, Plaintiff-Appellee, v. JOHN DOE', True),
    ('United States v. Doe', True),
    ('JOHN DOE; UNITED STATES OF AMERICA, Defendants-Appellees, v. JANE ROE', True),
    ('UNITED STATES ex rel. RUTH RITCHIE, Plaintiff, v. ACME CORP.', True),
    ('USA, Plaintiff, v. DOE', True),
    ('U.S. BANK, N.A., Defendant, v. DOE', False),
    ('UNITED STATES FIDELITY AND GUARANTY CO., Plaintiff, v. DOE', False),
    ('ERIC H. HOLDER, Attorney General of the United States, Respondent, v. DOE', False),
    ('JOHN SMITH, United States Marshal, Defendant, v. DOE', False)])
def test_header_rules_find_the_united_states(party: str, expected: bool) -> None:
    assert apply('header', party = party)['party1_united_states'] is expected


@pytest.mark.parametrize(('history', 'criminal', 'civil'), [
    ('(D.C. No. 06-CR-126-CAB). (D. Wyo.).', True, False),
    ('USDC No. 2:08-CR-4-1.', True, False),
    ('No. 4:07CR00123', True, False),
    ('Criminal Action No. 07-123', True, False),
    ('(D.C. No. 08-cv-1478-ZLW).', False, True),
    ('CIV. 05-1234', False, True),
    ('Civil Action No. 05-123', False, True),
    ('(D.C. Nos. CIV-05-630 JP/KBM & CR-03-2570 JP).', True, True),
    # Words, not docket numbers.
    ('Crawford v. Washington; see Fed. R. Crim. P. 35(b).', False, False),
    ('A civil rights claim under 42 U.S.C. 1983.', False, False)])
def test_header_rules_find_kinds_of_dockets(history: str, criminal: bool, civil: bool) -> None:
    found = apply('header', history = history)
    assert (found['docket_criminal'], found['docket_civil']) == (criminal, civil)


@pytest.mark.parametrize(('future', 'granted'), [
    ('Rehearing, en banc, granted by Doe v. Roe, 590 F.3d 1 (2009)', True),
    ('Vacated by, Motion granted by Pulido v. Chrones, 567 F.3d 1 (2009)', True),
    ('US Supreme Court certiorari denied by Grantham v. United States', False),
    ('Mandate issued', False)])
def test_lexis_rules_find_what_was_granted(future: str, granted: bool) -> None:
    assert apply('lexis_nexis_header', future = future)['future_grant'] is granted


def test_lexis_rules_find_concurrences_and_dissents_in_capitals() -> None:
    found = apply(
        'lexis_nexis',
        text = (
            '\nA v. B\n\nJUDGES: Before SMITH, JONES, and LEE, Circuit Judges.\n'
            'OPINION BY: SMITH\n\nCONCUR BY: JONES\n\nOPINION\n\nWe affirm.\n'
            'concurring: LEE, who did not write.\nLee, dissenting: in part.\n'
            'dissenting).\nCONCUR\n\nJONES, Circuit Judge, concurring.\n'))
    assert found['concurring_lines'] == 'CONCUR BY: JONES; CONCUR'
    assert found['dissenting_lines'] is None


@pytest.mark.parametrize(('opinion', 'decision', 'rulings'), [
    # (affirm, reverse, vacate, remand, dismiss)
    ('We review de novo and will reverse only if the error was plain. The '
     'district court did not err. AFFIRMED.', 'AFFIRMED',
     (True, False, False, False, False)),
    ('Affirmed in part, vacated in part, and remanded by unpublished per '
     'curiam opinion. Doe appeals.',
     'Affirmed in part, vacated in part, and remanded by unpublished per '
     'curiam opinion', (True, False, True, True, False)),
    ('In Smith, we vacated a similar sentence. For these reasons, we vacate '
     'the sentence and remand for resentencing.',
     'we vacate the sentence and remand for resentencing.',
     (False, False, True, True, False)),
    ('We GRANT the petition for rehearing and VACATE our prior opinion. The '
     'evidence was sufficient. We affirm.', 'We affirm.',
     (True, False, False, False, False)),
    ('The appeal is DISMISSED.', 'DISMISSED',
     (False, False, False, False, True)),
    # An earlier decision is not this one.
    ('The court reversed the conviction in an earlier appeal.', None,
     (False, False, False, False, False))])
def test_federal_rules_find_the_stated_decision(
    opinion: str,
    decision: str | None,
    rulings: tuple[bool, ...]) -> None:
    found = apply('federal', opinion = opinion)
    assert found['decision'] == decision
    assert tuple(
        found[f'decision_{r}']
        for r in ('affirm', 'reverse', 'vacate', 'remand', 'dismiss')) == rulings


@pytest.mark.parametrize(('text', 'expected'), [
    ('Petition for review of an order of the National Labor Relations Board.', 'National Labor Relations Board'),
    ('NATIONAL LABOR RELATIONS BOARD, Petitioner, v. ACME CORP.', 'National Labor Relations Board'),
    ('The N.L.R.B. found that the NLRB had jurisdiction.', 'National Labor Relations Board'),
    ('The SEC sued, and the Securities and Exchange Commission won.', 'Securities and Exchange Commission'),
    ('Appeal from the United States Tax Court. The IRS assessed a deficiency.', 'Internal Revenue Service; United States Tax Court'),
    ('The ATF agents searched the house.', 'Bureau of Alcohol Tobacco Firearms and Explosives'),
    ('The U.S. Department of Transportation and the FAA regulate pilots.', 'Department of Transportation; Federal Aviation Administration'),
    ('UNITED STATES DEPARTMENT OF LABOR, Respondent', 'Department of Labor'),
    ('The Secretary of Labor sued under the Fair Labor Standards Act.', 'Department of Labor'),
    ('the Department of State issued a passport', 'Department of State'),
    ('The Commodity Futures Trading Commission (CFTC) brought the action.', 'Commodity Futures Trading Commission'),
    ('The EPA issued a rule under the Clean Air Act.', 'Environmental Protection Agency'),
    ('He served in the U.S. Army and later the Navy.', 'Department of the Army; Department of the Navy'),
    ('The VA denied his claim for benefits.', 'Department of Veterans Affairs'),
    ('A CMS manual governs Medicare reimbursement.', 'Health Care Financing Administration'),
    ('The BIA affirmed, and the INS removed him.', 'Immigration and Naturalization Service'),
    ('The General Accounting Office (GAO) reported.', 'Government Accountability Office'),
    # Words and abbreviations that are not these agencies.
    ('Claims under the Equal Pay Act (EPA) fail, so the EPA claim is dismissed.', None),
    ('The ALJ relied on the Dictionary of Occupational Titles (DOT).', None),
    ('The agreement is governed by the Federal Arbitration Act (FAA).', None),
    ('JOHN DOE, Plaintiff-Appellant, v. JANE DOE.', None),
    ('The Illinois Department of Transportation (IDOT) let the contract.', None),
    ('the Pennsylvania Department of Labor and Industry denied benefits', None),
    ('the state department of corrections transferred him', None),
    ('Cal/OSHA cited the employer.', None),
    ('SEC. 2. DEFINITIONS.', None),
    ('Richmond, VA 23219. See Va. Code Ann.', None),
    ('AETNA INS. CO. v. Smith', None),
    ('The Salvation Army ran the shelter.', None),
    ('The district court granted summary judgment.', None)])
def test_federal_rules_find_agencies(text: str, expected: str | None) -> None:
    found = apply('agencies', opinion = text)
    assert found['agencies'] == expected


def test_agencies_are_those_of_fjc_idb() -> None:
    # Each agency of fjc-idb has rules, named by its code in their notes,
    # except its codes for no agency, its second code for the Environmental
    # Protection Agency, and "RTCO", which it does not name.
    import fjc_idb.rules.appellate
    book = amos.parsers.Rulebook.create('agencies')
    codes = {
        rule.note.split(':')[1].split('.')[0].strip()
        for rule in book if rule.note.startswith('fjc-idb:')}
    assert set(fjc_idb.rules.appellate.agencies) - codes == {'-8', '-9', '7', 'RTCO'}
    values = {rule.value for rule in book}
    assert len(values) == 104
    assert all(',' not in value for value in values)
    assert {rule.kind for rule in book} == {'categories'}


def test_case_type_prefixes() -> None:
    prefixes = rules.case_type_prefixes()
    assert prefixes[:2] == ['criminal', 'civil']
    assert {'tort', 'contract', 'ip', 'writ', 'constitutional'} <= set(prefixes)
    assert 'party1' not in prefixes and 'citations' not in prefixes
