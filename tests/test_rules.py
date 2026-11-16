"""Tests the rules module: courtpy's rulebooks."""

from __future__ import annotations

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
    assert len(federal) == len(amos.parsers.Rulebook.create(rules.ParseFederal))
    assert len(amos.parsers.Rulebook.create('lexis_nexis')) > 10
    with pytest.raises(FileNotFoundError, match = 'federal'):
        amos.parsers.Rulebook.create('no_such_rules')


def test_files_named_twice_are_read_once() -> None:
    both = amos.parsers.Rulebook.create('civil', 'federal')
    assert len(both) == len(amos.parsers.Rulebook.create('federal'))


def test_built_in_rulebooks_are_valid() -> None:
    federal = amos.parsers.Rulebook.create('federal')
    lexis = amos.parsers.Rulebook.create('lexis_nexis')
    assert len(federal) > 300
    for variable in (
        'party1', 'party2', 'court_num', 'agency', 'panel_judges', 'authors',
        'concurring', 'dissenting', 'disposition_reverse', 'opinion_reverse',
        'criminal_firearm', 'civil_titlevii', 'constitutional_amend4',
        'citations_case', 'citations_statute', 'cite_federal_reporter',
        'party1_appellant', 'party2_united_states', 'counsel_us_attorney',
        'docket_criminal', 'notice_unpublished', 'agencies'):
        assert variable in federal.names
    assert lexis.names == [
        'header', 'opinion', 'party', 'court', 'docket_number', 'history',
        'future', 'counsel', 'notice', 'dates', 'disposition', 'citation',
        'judges', 'opinion_by', 'concurring_lines', 'dissenting_lines']
    # Several values in a cell are separated by "; ", with no line breaks in
    # the files (which a checkout on Windows would make "\r\n").
    for rule in [*federal, *lexis]:
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
     'opinion.', ['ROBERTS', 'SCALIA', 'KENNEDY', 'THOMAS', 'GINSBURG'])])
def test_federal_rules_split_judges(judges: str, expected: list[str]) -> None:
    found = apply('federal', judges = judges)
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
    # Not a panel.
    ('Before April 25, 2016, Sabaini made deposits of over $2,000.', []),
    ('LYNCH, Circuit Judge. Before trial, Doe moved to suppress.', [])])
def test_federal_rules_find_the_panel_in_the_opinion(
    opening: str,
    expected: list[str]) -> None:
    found = apply('federal', opinion = opening)
    assert found['panel_judges'] == ('; '.join(expected) or None)


def test_federal_rules_prefer_the_panel_in_the_opinion() -> None:
    # CourtListener's "judges" may name only the author.
    found = apply(
        'federal',
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
def test_federal_rules_find_the_caption_in_the_opinion(
    opening: str,
    roles: tuple[bool, bool, bool, bool]) -> None:
    found = apply('federal', party = 'United States v. Doe', opinion = opening)
    assert (
        found['party1_appellant'], found['party1_appellee'],
        found['party2_appellant'], found['party2_appellee']) == roles
    assert (found['caption'] is None) == (roles == (False, False, False, False))


def test_federal_rules_keep_the_caption_of_the_header() -> None:
    found = apply(
        'federal',
        party = 'Mary SMITH, Plaintiff-Appellant, v. ACME CORP., Defendant-Appellee',
        opinion = 'ACME CORP., Plaintiff-Appellee, v. MARY SMITH, Defendant-Appellant.')
    assert found['caption'].startswith('Mary SMITH')
    assert found['party1_appellant'] and found['party2_appellee']
    assert not found['party1_appellee'] and not found['party2_appellant']


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
    ('Appeal from the United States Tax Court. The IRS assessed a deficiency.', 'Internal Revenue Service, United States Tax Court'),
    ('The ATF agents searched the house.', 'Bureau of Alcohol Tobacco Firearms and Explosives'),
    ('The U.S. Department of Transportation and the FAA regulate pilots.', 'Department of Transportation, Federal Aviation Administration'),
    ('UNITED STATES DEPARTMENT OF LABOR, Respondent', 'Department of Labor'),
    ('The Secretary of Labor sued under the Fair Labor Standards Act.', 'Department of Labor'),
    ('the Department of State issued a passport', 'Department of State'),
    ('The Commodity Futures Trading Commission (CFTC) brought the action.', 'Commodity Futures Trading Commission'),
    ('The EPA issued a rule under the Clean Air Act.', 'Environmental Protection Agency'),
    ('He served in the U.S. Army and later the Navy.', 'Department of the Army, Department of the Navy'),
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
