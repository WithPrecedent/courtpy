"""How the names of judges are compared.

Contents:
    clean_name: returns a name the way that names are compared.
    name_forms: returns the ways that an opinion may write a judge's name,
        grouped by how much of the name they give.
    _LEVELS: the groups of the forms of a judge's name, from the most of
        the name to the least.
    _NAME_PUNCTUATION: pattern for the punctuation that is removed from
        names before they are compared.

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
