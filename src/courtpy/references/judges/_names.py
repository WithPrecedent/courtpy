"""How the names of judges are compared.

Contents:
    clean_name: returns a name the way that names are compared.
    edit_distance: returns how many edits turn one name into another.
    name_forms: returns the ways that an opinion may write a judge's name,
        grouped by how much of the name they give.
    repaired_names: returns a name with the damage that some opinions' text
        does undone.
    shorter_names: returns shorter ways of writing a name that an opinion
        gives, to try when the name itself fits no judge.
    _LEVELS: the groups of the forms of a judge's name, from the most of
        the name to the least.
    _NAME_PUNCTUATION: pattern for the punctuation that is removed from
        names before they are compared.
    _SUFFIXES: the suffixes of names, as `clean_name` writes them.

"""

from __future__ import annotations

import re
import unicodedata

# The groups of the forms of a judge's name (see `name_forms`), in the order
# that `Roster.match` tries them: from the most of the name to the least.
_LEVELS: tuple[str, ...] = ('full', 'initials', 'last')
# The curly apostrophe (U+2019) is added with `chr` so that the source file
# has only plain characters.
_NAME_PUNCTUATION: re.Pattern[str] = re.compile(
    r"[.,\[\]'" + chr(0x2019) + ']')
_SUFFIXES: frozenset[str] = frozenset({'JR', 'SR', 'II', 'III', 'IV', 'V'})


""" Public Functions """


def clean_name(name: str) -> str:
    """Returns a name the way that names are compared.

    Args:
        name: a name or a part of one, such as "R[obert] Lanier" or
            "O'Scannlain".

    Returns:
        The name in capital letters, without accents, periods, commas,
            brackets, or apostrophes, and with single spaces (as the `names`
            rules of a rulebook write the names they find). Accents are left
            out because sources differ in whether they write them (so a name
            with an accented letter matches the same name without it).

    """
    letters = ''.join(
        character for character in unicodedata.normalize('NFKD', name)
        if not unicodedata.combining(character))
    return ' '.join(_NAME_PUNCTUATION.sub('', letters.upper()).split())


def name_forms(
    first: str,
    middle: str,
    last: str,
    suffix: str = '') -> dict[str, list[str]]:
    """Returns the ways that an opinion may write a judge's name.

    Opinions name judges by their last names, with initials or first names
    only when two judges of a court share one. The forms are grouped by how
    much of the name they give, which is the order in which `Roster.match`
    tries them. For Sandra Lea Lynch, they are:

    | Level | Forms |
    | --- | --- |
    | `full` | "SANDRA LEA LYNCH", "SANDRA L LYNCH", and "SANDRA LYNCH". |
    | `initials` | "S LEA LYNCH", "S L LYNCH", "SL LYNCH" (as "S.L." is written once its periods are removed), "S LYNCH", and "LEA LYNCH" (for a judge who goes by a middle name). |
    | `last` | "LYNCH". |

    With a suffix, each form is also written with it after the last name
    (such as "M D SMITH JR" and "SMITH JR"). A form is in only the first
    level that has it.

    Args:
        first: the judge's first name.
        middle: the judge's middle name or names, which may be blank.
        last: the judge's last name.
        suffix: the suffix of the judge's name, such as "Jr." or "III".
            Defaults to an empty `str`.

    Returns:
        The forms of each level ("full", "initials", and "last"), as
            `clean_name` writes them, without repeats. There are none if
            `last` is blank.

    """
    first, middle, last, suffix = (
        clean_name(part) for part in (first, middle, last, suffix))
    levels: dict[str, list[str]] = {level: [] for level in _LEVELS}
    if not last:
        return levels
    written = {
        'full': [
            f'{first} {middle} {last}',
            f'{first} {middle[:1]} {last}',
            f'{first} {last}'],
        'initials': [
            f'{first[:1]} {middle} {last}',
            f'{first[:1]} {middle[:1]} {last}',
            f'{first[:1]}{middle[:1]} {last}',
            f'{first[:1]} {last}',
            # An initial alone is not a name that a judge goes by.
            f'{middle} {last}' if len(middle) > 1 else ''],
        'last': [last]}
    # Without a first name, a full name or initials would be the last name
    # alone, which belongs to the last level.
    alone = {last, f'{last} {suffix}'.strip()}
    seen: set[str] = set()
    for level, forms in written.items():
        for form in forms:
            for written_form in (form, f'{form} {suffix}' if suffix else ''):
                named = ' '.join(written_form.split())
                if not named or named in seen or (
                    level != 'last' and named in alone):
                    continue
                seen.add(named)
                levels[level].append(named)
    return levels


def edit_distance(first: str, second: str) -> int:
    """Returns how many edits turn one name into another.

    An edit adds, removes, or changes a letter, or swaps two letters next to
    each other (the optimal string alignment distance), which are the errors
    that scanning and typing make in names ("KRAVTTCH" for "KRAVITCH", or
    "TJOFALT" for "TJOFLAT").

    Args:
        first: a name.
        second: another name.

    Returns:
        The number of edits.

    """
    rows = len(first) + 1
    columns = len(second) + 1
    table = [[0] * columns for _ in range(rows)]
    for row in range(rows):
        table[row][0] = row
    for column in range(columns):
        table[0][column] = column
    for row in range(1, rows):
        for column in range(1, columns):
            changed = int(first[row - 1] != second[column - 1])
            table[row][column] = min(
                table[row - 1][column] + 1,
                table[row][column - 1] + 1,
                table[row - 1][column - 1] + changed)
            if (
                row > 1 and column > 1
                and first[row - 1] == second[column - 2]
                and first[row - 2] == second[column - 1]):
                table[row][column] = min(
                    table[row][column], table[row - 2][column - 2] + 1)
    return table[-1][-1]


def repaired_names(name: str) -> list[str]:
    """Returns a name with the damage that some opinions' text does undone.

    Some opinions are printed in small capitals, which their text writes
    with a space after each large first letter ("P OSNER" for "POSNER", or
    "V AN B OKKELEN"), break a hyphenated name at its hyphen
    ("JACKSON- AKIWUMI"), or run a word of the panel into a name
    ("BEFORENIEMEYER"). `Roster.match` tries these forms of a name that fits
    no judge as it is written.

    Args:
        name: the name, as `clean_name` returns it.

    Returns:
        The repaired forms, without repeats or `name` itself.

    """
    forms = [
        re.sub(r'\b([A-Z]) (?=[A-Z]{2,})', r'\1', name),
        re.sub(r'\s*-\s*', '-', name).strip('-'),
        name.replace(' ', '-'),
        re.sub(r'^(?:BEFORE|PRESENT)(?=[A-Z]{3,})', '', name)]
    return [form for form in dict.fromkeys(forms) if form and form != name]


def shorter_names(name: str) -> list[str]:
    """Returns shorter ways of writing a name that an opinion gives.

    An opinion may give more of a judge's name than the Federal Judicial
    Center's files do (as "Susan P. Graber" for a judge whom the files name
    "Susan Graber"), give middle initials that are not those of the files'
    middle names (as "Sarah A. L. Merriam" for "Sarah Ann Leilani Merriam"),
    or give a short first name (as "Ed Carnes" for "Edward Carnes"). Such a
    name is none of the forms of the judge's name (see `name_forms`), but a
    shorter way of writing it is: the first and last names, and then the
    first initial and the last name. A suffix stays with the last name. The
    last name alone is never one of them, since a name that gives more
    should not be matched by less than its first name or initial.

    Args:
        name: the name, as `clean_name` returns it.

    Returns:
        The first and last names (if the name has a middle name or initial)
            and the first initial and last name (if the first name is longer
            than an initial), as `clean_name` writes them, without repeats
            or `name` itself. There are none for a name of one word.

    """
    parts = name.split()
    tail = 2 if len(parts) > 1 and parts[-1] in _SUFFIXES else 1
    given, last = parts[:-tail], ' '.join(parts[-tail:])
    if not given:
        return []
    shorter = []
    if len(given) > 1:
        shorter.append(f'{given[0]} {last}')
    if len(given[0]) > 1:
        shorter.append(f'{given[0][:1]} {last}')
    return [form for form in dict.fromkeys(shorter) if form != name]
