"""Techniques that check court data and how well it was coded.

Each is an `amos` evaluator (`amos.evaluators.Evaluator`), so it is added to
the `amos` library when courtpy is imported, can be named in the settings
of a "critic" worker, and adds a table to the dataset's `tables` under its
name. Unlike `amos`'s audits, they check the data, not a fitted model, so
they need no model.

| Technique | Checks | Needs |
| --- | --- | --- |
| `audit_random_assignment` | Whether the traits of cases (such as their types, and whether they review an agency) are balanced across the compositions of their panels within each court in each year, as random assignment of panels would make them. | `Cases`, with the judges' parties (from `add_biography` or `code_panels`). |
| `audit_parsing` | How many cases lack what the rules should find (the court, the court below, the judges, the year, or the outcome), have panels of another size, or have a header's disposition that disagrees with the decision that the opinion states, with examples to read. | `Cases`. |
| `audit_coverage` | How many cases of each court in each year the data has, against the appeals that the Federal Judicial Center's Integrated Database records, and so how much of each court's work it covers. | `Cases` of the courts of appeals, with "year". |
| `validate_coding` | How often courtpy's coding agrees with another source's (such as the Integrated Database after `add_idb`, or the Supreme Court Database after `add_scdb`): the share of cases on which they agree and Cohen's kappa. | `Cases`, with both columns of each pair. |

Contents:
    AuditCoverage: compares the cases of each court in each year with the
        appeals of the Integrated Database.
    AuditParsing: counts the cases that lack what the rules should find, or
        whose parts disagree.
    AuditRandomAssignment: checks that the traits of cases are balanced
        across the compositions of their panels.
    ValidateCoding: measures how often courtpy's coding agrees with another
        source's.
    _BALANCE_TRAITS: the traits of cases checked for balance when none are
        named.
    _RULINGS: the rulings that a header's disposition and an opinion's
        decision are compared on.
    _VALIDATION_CODES: the codes that mean true in the other source's
        columns that have codes, unless others are named.
    _VALIDATIONS: the pairs of columns compared when none are named, if the
        data has them.

"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Mapping, Sequence
from typing import Any

import amos
import numpy as np
import pandas as pd

from ..core import cases, utilities
from ..references import courts, fjc_idb, judges
from . import _strata

# The traits of cases checked for balance across panels when none are named:
# what kind of case it is and where it comes from, which a panel cannot
# change.
_BALANCE_TRAITS: tuple[str, ...] = (
    'type_criminal', 'type_civil', 'review_agency', 'review_immigration',
    'procedure_pro_se', 'party1_united_states', 'party2_united_states')
# The rulings on which a header's disposition ("disposition_...") and the
# decision the opinion states ("decision_...") are compared.
_RULINGS: tuple[str, ...] = (
    'affirm', 'reverse', 'vacate', 'remand', 'dismiss')
# The pairs of columns that `validate_coding` compares when none are named,
# if the data has both: courtpy's column and the other source's.
_VALIDATIONS: dict[str, str] = {
    'published': 'idb_published',
    'procedure_pro_se': 'idb_pro_se_party',
    'type_criminal': 'idb_appeal_type'}
# The codes that mean true in the other source's columns that have codes,
# unless "true_values" names others: the Integrated Database's types of
# criminal appeals (see fjc-idb's `rules.appellate.appeal_types_to_columns`).
_VALIDATION_CODES: dict[str, tuple[str, ...]] = {
    'idb_appeal_type': tuple(str(code) for code in range(13, 23))}


@dataclasses.dataclass
class AuditRandomAssignment(amos.evaluators.Evaluator):
    """Checks that the traits of cases are balanced across their panels.

    Studies of panels (such as of whether a judge votes differently beside
    judges appointed by the other party) rely on panels being assigned to
    cases at random within a court. If they are, a trait of a case that the
    panel cannot change (such as whether it is criminal) has nothing to do
    with the panel's composition within each court in each year.

    For each trait, the table has its mean for each composition of the panel
    ("DDD" to "RRR"; see `courtpy.judges.panel_compositions`), the
    correlation between the trait and the number of Republican appointees
    within each court and year (each stratum's mean removed), and the share
    of `n_permutations` random reassignments of the compositions within each
    court and year whose correlation is at least as far from 0 (a
    permutation test, with no assumption about how the trait is
    distributed). A trait is balanced if that share is at least `alpha`.

    """

    """ Required Methods """

    def evaluate(
        self,
        item: amos.Dataset,
        *,
        traits: Sequence[str] | str | None = None,
        size: int = 3,
        strata: Sequence[str] | str = ('court_num', 'year'),
        n_permutations: int = 1000,
        alpha: float = 0.05,
        seed: int = 0,
        **kwargs: Any) -> pd.DataFrame:
        """Returns the balance of each trait across panel compositions.

        Args:
            item: the cases, with the parties of their judges.
            traits: the columns of the traits to check. Defaults to `None`,
                which checks those of `_BALANCE_TRAITS` that the cases have.
            size: the number of judges on the panels to check. Defaults to 3.
            strata: the columns within whose values panels are assigned.
                Defaults to "court_num" and "year".
            n_permutations: the number of random reassignments. Defaults to
                1000.
            alpha: the smallest share of reassignments at which a trait is
                balanced. Defaults to 0.05.
            seed: the seed of the random reassignments. Defaults to 0.
            **kwargs: not used.

        Raises:
            ValueError: if no trait is named or found, or no case has a panel
                of `size` judges whose parties are known.

        Returns:
            A row for each trait, labeled by it, with the trait's mean for
                each composition, "correlation", "p_value", "balanced", and
                "cases" (the number of cases compared).

        """
        data = item.data
        named = utilities.listify(traits) or [
            t for t in _BALANCE_TRAITS if t in data.columns]
        if not named:
            message = 'audit_random_assignment needs "traits" to check'
            raise ValueError(message)
        cases.require_columns(data, named, 'audit_random_assignment')
        compositions = judges.panel_compositions(data, size)
        republicans = judges.republican_appointees(data, size)
        codes = _strata.stratum_codes(data, utilities.listify(strata))
        usable = republicans.notna() & (codes >= 0)
        if not usable.any():
            message = (
                f'no case has a panel of {size} judges whose parties are '
                f'known')
            raise ValueError(message)
        generator = np.random.default_rng(seed)
        rows = []
        for trait in named:
            values = _flags_or_numbers(data[trait])
            kept = (usable & values.notna()).to_numpy()
            found = values[kept].to_numpy(dtype = float)
            count = republicans[kept].to_numpy(dtype = float)
            stratum = pd.factorize(codes[kept])[0]
            centered = _strata.demean(found, stratum)
            counted = _strata.demean(count, stratum)
            observed = _correlation(centered, counted)
            # Shuffling within strata keeps each stratum's mean, so the
            # shuffled counts are already centered.
            extreme = sum(
                abs(_correlation(centered, _strata.permute_within(
                    counted, stratum, generator))) >= abs(observed) - 1e-12
                for _ in range(n_permutations))
            p_value = (extreme + 1) / (n_permutations + 1)
            means = values[kept].groupby(
                compositions[kept], observed = False).mean()
            rows.append({
                **means.to_dict(),
                'correlation': observed,
                'p_value': p_value,
                'balanced': p_value >= alpha,
                'cases': int(kept.sum())})
        return pd.DataFrame(rows, index = pd.Index(named, name = 'trait'))


@dataclasses.dataclass
class AuditParsing(amos.evaluators.Evaluator):
    """Counts the cases that lack what the rules should find.

    Each row is a check that the cases have: their court ("court_num"), the
    court below ("lower_court_num", except for a review of an agency or of
    the Board of Immigration Appeals), their judges ("panel_judges"), a
    panel of `size` judges ("panel_size"), their year, and their outcome
    ("outcome_reversal"), and that the disposition in the header
    ("disposition_...") agrees with the decision that the opinion states
    ("decision_...") where both are found. A check of a column that the cases
    do not have is left out. After a change to the rules, the examples are
    the cases to read first.

    """

    """ Required Methods """

    def evaluate(
        self,
        item: amos.Dataset,
        *,
        size: int = 3,
        examples: int = 10,
        **kwargs: Any) -> pd.DataFrame:
        """Returns how many cases fail each check.

        Args:
            item: the cases.
            size: the number of judges that a panel should have. Defaults to
                3.
            examples: the most cases to list for each check. Defaults to 10.
            **kwargs: not used.

        Returns:
            A row for each check, labeled by it, with "cases" (how many fail
                it), "share" (of all the cases), and "examples" (the labels
                of the first that fail it, separated by "; ").

        """
        data = item.data
        checks: dict[str, pd.Series] = {}
        if 'court_num' in data.columns:
            checks['no court'] = data['court_num'].isna()
        if 'lower_court_num' in data.columns:
            agency = pd.Series(False, index = data.index)
            for column in ('review_agency', 'review_immigration'):
                if column in data.columns:
                    agency |= cases.column_as_flags(data, column)
            checks['no court below'] = data['lower_court_num'].isna() & ~agency
        if 'panel_judges' in data.columns:
            checks['no judges'] = ~_has_text(data['panel_judges'])
        if 'panel_size' in data.columns:
            checks[f'panel not of {size}'] = pd.to_numeric(
                data['panel_size'], errors = 'coerce') != size
        if 'year' in data.columns:
            checks['no year'] = data['year'].isna()
        if 'outcome_reversal' in data.columns:
            checks['no outcome'] = data['outcome_reversal'].isna()
        disagreement = _disagreement(data)
        if disagreement is not None:
            checks['disposition and decision disagree'] = disagreement
        total = max(len(data), 1)
        rows = []
        for check in checks.values():
            failing = check.fillna(False).astype(bool)
            rows.append({
                'cases': int(failing.sum()),
                'share': failing.sum() / total,
                'examples': cases._SEPARATOR.join(
                    str(label) for label in data.index[failing][:examples])})
        return pd.DataFrame(
            rows, index = pd.Index(list(checks), name = 'check'))


@dataclasses.dataclass
class AuditCoverage(amos.evaluators.Evaluator):
    """Compares the cases of each court in each year with the database's.

    The Federal Judicial Center's Integrated Database records every appeal
    that the courts of appeals decide. For each court and year of the cases,
    the table has how many cases the data has, how many appeals the
    database records as decided (by the year of their judgment), and the
    share of them that the data has, which shows which courts and years a
    study's cases (such as CourtListener's) leave out. If both have
    publication, it has the same for published opinions.

    The database's records come from fjc-idb (see `courtpy.fjc_idb.appeals`),
    or from "source".

    """

    """ Required Methods """

    def evaluate(
        self,
        item: amos.Dataset,
        *,
        source: Any = None,
        folder: pathlib.Path | str | None = None,
        download: bool = True,
        year: str = 'year',
        court_name: str = 'court_name',
        court_num: str = 'court_num',
        **kwargs: Any) -> pd.DataFrame:
        """Returns the coverage of each court in each year.

        Args:
            item: the cases of the courts of appeals.
            source: the database's table of appeals, or the path of a file
                of it (see `courtpy.fjc_idb.AddIdb`). Defaults to `None`, in
                which case the database's records of the years of the cases
                are read (and downloaded, if `download`).
            folder: the folder of the database's yearly files, without a
                `source`. Defaults to `None`, for fjc-idb's folder in
                courtpy's data folder.
            download: whether to download the yearly files that are missing,
                without a `source`. Defaults to `True`.
            year: the column with each case's year. Defaults to "year".
            court_name: the column with courtpy's name for each case's court.
                Defaults to "court_name".
            court_num: the column with courtpy's number for each case's
                court. Defaults to "court_num".
            **kwargs: not used.

        Raises:
            KeyError: if the cases have no `year`, or the database's table
                has no "circuit" or "judgment_date".

        Returns:
            A row for each court (by its label) and year, with "cases",
                "idb_appeals", and "coverage" (and "published",
                "idb_published", and "published_coverage" if both have
                publication).

        """
        data = item.data
        cases.require_columns(data, [year], 'audit_coverage')
        years = pd.to_numeric(data[year], errors = 'coerce')
        found = pd.DataFrame({
            'court': courts.court_labels(
                data, court_name = court_name, court_num = court_num),
            'year': years}).dropna()
        if found.empty:
            message = 'no case has a known court and year'
            raise ValueError(message)
        appeals = self._appeals(
            source, int(found['year'].min()), int(found['year'].max()) + 1,
            folder, download)
        cases.require_columns(
            appeals, ['circuit', 'judgment_date'], 'the database of appeals')
        recorded = pd.DataFrame({
            'court': appeals['circuit'].astype('string'),
            'year': pd.to_datetime(
                appeals['judgment_date'], errors = 'coerce').dt.year})
        group = ['court', 'year']
        counts = found.assign(court = found['court'].astype('string')).groupby(
            group).size().rename('cases')
        expected = recorded.dropna().groupby(group).size().rename(
            'idb_appeals')
        table = pd.concat([counts, expected], axis = 1).loc[counts.index]
        table['idb_appeals'] = table['idb_appeals'].fillna(0).astype('int64')
        table['coverage'] = table['cases'] / table['idb_appeals'].where(
            table['idb_appeals'] > 0)
        if 'published' in data.columns and 'published' in appeals.columns:
            mine = found.assign(
                court = found['court'].astype('string'),
                published = cases.column_as_flags(data, 'published')[
                    found.index])
            theirs = recorded.assign(published = pd.to_numeric(
                appeals['published'], errors = 'coerce').fillna(0) > 0)
            table['published'] = mine.groupby(group)['published'].sum()
            table['idb_published'] = theirs.dropna().groupby(group)[
                'published'].sum().reindex(table.index).fillna(0).astype(
                    'int64')
            table['published_coverage'] = table['published'] / table[
                'idb_published'].where(table['idb_published'] > 0)
        order = {c: n for n, c in enumerate(
            courts.court_labels(data).cat.categories)}
        return table.sort_index(
            key = lambda level: level.map(order) if level.name == 'court'
            else level)

    """ Private Methods """

    def _appeals(
        self,
        source: Any,
        start_year: int,
        stop_year: int,
        folder: pathlib.Path | str | None,
        download: bool) -> pd.DataFrame:
        """Returns the database's table of appeals.

        Args:
            source: a table or the path of a file of one, or `None`.
            start_year: the first year of the cases.
            stop_year: the year after the last year of the cases (the
                database's years end on September 30).
            folder: the folder of the database's yearly files, or `None`.
            download: whether to download the yearly files that are missing.

        Returns:
            The table of appeals.

        """
        if isinstance(source, pd.DataFrame):
            return source
        if source is not None:
            reader = fjc_idb.AddIdb()
            reader.clerk = getattr(self, 'clerk', None)
            return reader.read(source)
        return fjc_idb.appeals(
            start_year, stop_year, folder, download = download)


@dataclasses.dataclass
class ValidateCoding(amos.evaluators.Evaluator):
    """Measures how often courtpy's coding agrees with another source's.

    Each pair names a column of courtpy's (such as "published") and the
    other source's column for the same thing (such as "idb_published",
    after `add_idb`). Both are read as flags: true, nonzero, or (for the
    other source's column) one of its `true_values`. Only the cases with
    both are compared. Cohen's kappa is the agreement beyond what the shares
    of true values in each would give by chance (1 is perfect agreement,
    and 0 is no better than chance).

    """

    """ Required Methods """

    def evaluate(
        self,
        item: amos.Dataset,
        *,
        pairs: Mapping[str, str] | str | None = None,
        true_values: Mapping[str, Sequence[Any] | str] | None = None,
        **kwargs: Any) -> pd.DataFrame:
        """Returns the agreement of each pair of columns.

        Args:
            item: the cases.
            pairs: courtpy's columns and the other source's, as a `dict` or
                text such as "published = idb_published, type_criminal =
                idb_appeal_type". Defaults to `None`, which compares the
                pairs of `_VALIDATIONS` that the cases have.
            true_values: for a column of the other source with codes, the
                codes that mean true (as a list, or text separated by "|"),
                by the column's name. Defaults to `None`, which uses
                `_VALIDATION_CODES` for the columns it names.
            **kwargs: not used.

        Raises:
            ValueError: if no pair is named or found.
            KeyError: if a column of a pair is not in the cases.

        Returns:
            A row for each pair, labeled by courtpy's column, with
                "reference" (the other column), "cases" (how many have both),
                "agreement", "kappa", "both_true", "both_false",
                "courtpy_only" (true only in courtpy's), and "reference_only".

        """
        data = item.data
        chosen = _parse_pairs(pairs) or {
            mine: theirs for mine, theirs in _VALIDATIONS.items()
            if mine in data.columns and theirs in data.columns}
        if not chosen:
            message = (
                'validate_coding needs "pairs" of columns to compare, such as '
                '"published = idb_published"')
            raise ValueError(message)
        cases.require_columns(
            data, [*chosen, *chosen.values()], 'validate_coding')
        codes = {
            column: [str(v) for v in utilities.listify(
                values.split('|') if isinstance(values, str) else values)]
            for column, values in {
                **_VALIDATION_CODES, **(true_values or {})}.items()}
        rows = []
        for mine, theirs in chosen.items():
            ours = _flags_or_numbers(data[mine]).ne(0).where(
                data[mine].notna())
            reference = data[theirs]
            if theirs in codes:
                truth = reference.astype('string').isin(codes[theirs])
            else:
                truth = _flags_or_numbers(reference).ne(0)
            truth = truth.where(reference.notna())
            both = ours.notna() & truth.notna()
            a = ours[both].astype(bool).to_numpy()
            b = truth[both].astype(bool).to_numpy()
            rows.append({
                'reference': theirs,
                'cases': int(both.sum()),
                **_agreement(a, b)})
        return pd.DataFrame(
            rows, index = pd.Index(list(chosen), name = 'column'))


""" Private Functions """


def _agreement(first: np.ndarray, second: np.ndarray) -> dict[str, Any]:
    """Returns how often two columns of flags agree.

    Args:
        first: courtpy's flags.
        second: the other source's flags, for the same cases.

    Returns:
        "agreement" (the share of cases on which they agree), "kappa"
            (Cohen's kappa, missing if either is constant), "both_true",
            "both_false", "courtpy_only", and "reference_only".

    """
    total = len(first)
    if not total:
        return {
            'agreement': np.nan, 'kappa': np.nan, 'both_true': 0,
            'both_false': 0, 'courtpy_only': 0, 'reference_only': 0}
    agreement = float((first == second).mean())
    chance = float(
        first.mean() * second.mean()
        + (1 - first.mean()) * (1 - second.mean()))
    kappa = (agreement - chance) / (1 - chance) if chance < 1 else np.nan
    return {
        'agreement': agreement,
        'kappa': kappa,
        'both_true': int((first & second).sum()),
        'both_false': int((~first & ~second).sum()),
        'courtpy_only': int((first & ~second).sum()),
        'reference_only': int((~first & second).sum())}


def _correlation(first: np.ndarray, second: np.ndarray) -> float:
    """Returns the correlation of two columns whose means are 0.

    Args:
        first: values with each stratum's mean removed.
        second: values with each stratum's mean removed.

    Returns:
        Their correlation, or 0 if either does not vary.

    """
    scale = float(np.sqrt((first ** 2).sum() * (second ** 2).sum()))
    return float((first * second).sum() / scale) if scale else 0.0


def _disagreement(data: pd.DataFrame) -> pd.Series | None:
    """Returns which cases' header disposition and stated decision disagree.

    Args:
        data: the cases.

    Returns:
        Whether each case's disposition and decision differ on any ruling of
            `_RULINGS`, among the cases that have at least one ruling in
            each, or `None` if the cases have neither kind of column.

    """
    rulings = [
        r for r in _RULINGS
        if f'disposition_{r}' in data.columns
        and f'decision_{r}' in data.columns]
    if not rulings:
        return None
    header = pd.DataFrame({
        r: cases.column_as_flags(data, f'disposition_{r}') for r in rulings})
    stated = pd.DataFrame({
        r: cases.column_as_flags(data, f'decision_{r}') for r in rulings})
    both = header.any(axis = 1) & stated.any(axis = 1)
    return both & (header != stated).any(axis = 1)


def _flags_or_numbers(values: pd.Series) -> pd.Series:
    """Returns a column as numbers (1 for true and 0 for false).

    Args:
        values: a column of flags or numbers, which may be missing.

    Returns:
        The values as decimals, with missing values kept missing.

    """
    if values.dtype == object:
        values = values.map(
            lambda v: float(v) if isinstance(v, bool | int | float) else v)
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.astype('Float64').astype(float)
    return pd.to_numeric(values, errors = 'coerce').astype(float)


def _has_text(values: pd.Series) -> pd.Series:
    """Returns which values are text that is not blank.

    Args:
        values: a column.

    Returns:
        Whether each value is text with something in it (a list counts if
            it is not empty).

    """
    return values.map(
        lambda v: bool(v) if isinstance(v, list | tuple)
        else isinstance(v, str) and bool(v.strip()))


def _parse_pairs(pairs: Mapping[str, str] | str | None) -> dict[str, str]:
    """Returns the pairs of columns that `validate_coding` compares.

    Args:
        pairs: a `dict`, or text such as "a = b, c = d", or `None`.

    Raises:
        ValueError: if a pair in text has no "=".

    Returns:
        courtpy's columns and the other source's, in order.

    """
    if pairs is None:
        return {}
    if isinstance(pairs, Mapping):
        return {str(k): str(v) for k, v in pairs.items()}
    found: dict[str, str] = {}
    for pair in utilities.listify(pairs):
        mine, equals, theirs = str(pair).partition('=')
        if not equals:
            message = (
                f'{pair!r} is not a pair such as '
                f'"published = idb_published"')
            raise ValueError(message)
        found[mine.strip()] = theirs.strip()
    return found
