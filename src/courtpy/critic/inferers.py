"""Techniques that infer the effects of panels on judges' votes.

`panel_effects` (`PanelEffects`) is an `amos` inferer
(`amos.inferers.Inferer`), so it is added to the `amos` library when
courtpy is imported, can be named in the settings of a "critic" worker,
adds its table of effects to the dataset's `tables` under its name, and
draws it as a `coefficient_plot` with "visualize".

Contents:
    PanelEffects: estimates the effect of a judge's colleagues on the
        judge's vote, with a test that reassigns panels at random.
    _Z_95: the number of standard errors on each side of an estimate in its
        95% confidence interval.

"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from typing import Any

import amos
import numpy as np
import pandas as pd

from ..core import cases, utilities
from . import _strata

# The number of standard errors on each side of an estimate in its 95%
# confidence interval, from the normal distribution.
_Z_95: float = 1.959963984540054


@dataclasses.dataclass
class PanelEffects(amos.inferers.Inferer):
    """Estimates the effect of a judge's colleagues on the judge's vote.

    The data is `Votes` (see `cases_to_votes`): a row for each judge on
    each case, with the judge's vote (such as "vote_reversal"), the party of
    the president who appointed the judge ("judge_party", -1 or 1), and the
    mean party of the judge's colleagues on the panel ("colleagues_party").
    The vote is regressed on the colleagues' party, the judge's own party,
    and (with "interact") their product, which says whether a judge of one
    party is moved more by the other party's colleagues, with a fixed effect
    for each court in each year, so that each vote is compared only with
    the votes of its own court and year (a linear probability model for a
    vote of yes or no).

    Panels are assigned at random within a court (or so the design
    assumes; see `audit_random_assignment`), so the effects are causal if
    that holds. Two tests say how sure the estimates are:

    * The standard errors are clustered by case, since the judges of a case
      vote together, with Stata's correction for few clusters, and give the
      p-values and 95% confidence intervals.
    * A randomization test reassigns each vote's colleagues' party at random
      among the votes of the same court and year `n_permutations` times, and
      its p-value is the share of reassignments whose estimate is at least
      as far from 0 as the one found. It assumes nothing about the
      distribution of the votes.

    The table has a row for each term, with "coefficient", "std_error",
    "t_statistic", "p_value", "ri_p_value" (for the colleagues' party and
    its product with the judge's party), "ci_lower", and "ci_upper".

    """

    """ Required Methods """

    def infer(
        self,
        item: amos.Dataset,
        *,
        outcome: str | None = None,
        treatment: str = 'colleagues_party',
        controls: Sequence[str] | str = ('judge_party',),
        interact: bool = True,
        strata: Sequence[str] | str = ('court_num', 'year'),
        cluster: str = 'case_id',
        n_permutations: int = 1000,
        seed: int = 0,
        **kwargs: Any) -> amos.inferers.Inference:
        """Returns the effects of the colleagues on the votes of `item`.

        Args:
            item: the votes, a row for each judge on each case.
            outcome: the column with each judge's vote. Defaults to `None`,
                which uses the dataset's label, or else "vote_reversal".
            treatment: the column with the judge's colleagues' party.
                Defaults to "colleagues_party".
            controls: other columns of the regression, as a list or a
                comma-separated `str`. Defaults to "judge_party".
            interact: whether to add the product of the treatment and the
                first control. Defaults to `True`.
            strata: the columns within whose values votes are compared (a
                fixed effect for each combination). Defaults to "court_num"
                and "year".
            cluster: the column whose values group the votes for the
                standard errors. Defaults to "case_id".
            n_permutations: the number of random reassignments of the
                treatment. 0 skips the randomization test. Defaults to 1000.
            seed: the seed of the random reassignments. Defaults to 0.
            **kwargs: not used.

        Raises:
            KeyError: if the votes lack a column that is needed.
            ValueError: if no vote has every column.

        Returns:
            The table of effects, the arrays of the fitted regression, and
                the details to record.

        """
        data = item.data
        outcome = outcome or item.label or 'vote_reversal'
        named = utilities.listify(controls)
        grouped = utilities.listify(strata)
        cases.require_columns(
            data, [outcome, treatment, *named, *grouped, cluster],
            'panel_effects')
        numbers = pd.DataFrame({
            c: _numbers(data[c]) for c in [outcome, treatment, *named]})
        codes = _strata.stratum_codes(data, grouped)
        kept = (
            numbers.notna().all(axis = 1) & (codes >= 0)
            & data[cluster].notna()).to_numpy()
        if not kept.any():
            message = 'no vote has every column that panel_effects needs'
            raise ValueError(message)
        y = numbers.loc[kept, outcome].to_numpy(dtype = float)
        dose = numbers.loc[kept, treatment].to_numpy(dtype = float)
        others = numbers.loc[kept, named].to_numpy(dtype = float)
        stratum = pd.factorize(codes[kept])[0]
        groups = pd.factorize(data.loc[kept, cluster])[0]
        terms = [treatment]
        if interact and named:
            terms.append(f'{treatment} x {named[0]}')
        terms.extend(named)

        def design(treated: np.ndarray) -> np.ndarray:
            """Returns the regression's columns with strata's means removed.

            Args:
                treated: the treatment of each vote.

            Returns:
                The treatment, its product with the first control (if
                    interacted), and the controls, each less the mean of
                    its stratum.

            """
            columns = [treated]
            if interact and named:
                columns.append(treated * others[:, 0])
            raw = np.column_stack([*columns, others])
            return _strata.demean(raw, stratum)

        x = design(dose)
        centered = _strata.demean(y, stratum)
        coefficients, *_ = np.linalg.lstsq(x, centered, rcond = None)
        errors = _clustered_errors(
            x, centered - x @ coefficients, groups,
            absorbed = int(stratum.max()) + 1)
        tested = 2 if interact and named else 1
        reassigned = _randomization_p_values(
            coefficients[:tested], dose = dose, stratum = stratum,
            centered = centered, design = design,
            n_permutations = n_permutations, seed = seed)
        t_statistics = np.divide(
            coefficients, errors, out = np.full_like(coefficients, np.nan),
            where = errors > 0)
        table = pd.DataFrame({
            'coefficient': coefficients,
            'std_error': errors,
            't_statistic': t_statistics,
            'p_value': [
                math.erfc(abs(t) / math.sqrt(2)) if np.isfinite(t)
                else np.nan for t in t_statistics],
            'ri_p_value': [
                *reassigned, *[np.nan] * (len(terms) - tested)],
            'ci_lower': coefficients - _Z_95 * errors,
            'ci_upper': coefficients + _Z_95 * errors},
            index = pd.Index(terms, name = 'term'))
        fitted = {
            'terms': terms, 'coefficients': coefficients, 'errors': errors}
        details = {
            'tool': 'courtpy (least squares with fixed effects)',
            'outcome': outcome,
            'treatment': treatment,
            'controls': named,
            'strata': grouped,
            'votes': int(kept.sum()),
            'clusters': int(groups.max()) + 1,
            'n_permutations': n_permutations}
        return amos.inferers.Inference(
            table = table, fitted = fitted, details = details)


""" Private Functions """


def _clustered_errors(
    x: np.ndarray,
    residuals: np.ndarray,
    groups: np.ndarray,
    absorbed: int) -> np.ndarray:
    """Returns standard errors clustered by group.

    Args:
        x: the regression's columns, with the strata's means removed.
        residuals: the regression's errors.
        groups: the cluster of each row, from 0.
        absorbed: the number of fixed effects that removing the strata's
            means absorbed, which count against the degrees of freedom.

    Returns:
        The standard error of each coefficient, with Stata's correction for
            few clusters: G / (G - 1) times (N - 1) / (N - K), where G is
            the number of clusters, N of rows, and K of coefficients and
            fixed effects.

    """
    rows, width = x.shape
    clusters = int(groups.max()) + 1
    scores = np.column_stack([
        np.bincount(groups, weights = x[:, c] * residuals,
                    minlength = clusters)
        for c in range(width)])
    bread = np.linalg.pinv(x.T @ x)
    covariance = bread @ (scores.T @ scores) @ bread
    freedom = max(rows - width - absorbed, 1)
    correction = (
        clusters / max(clusters - 1, 1) * (rows - 1) / freedom)
    errors: np.ndarray = np.sqrt(
        np.clip(np.diag(covariance) * correction, 0, None))
    return errors


def _numbers(values: pd.Series) -> pd.Series:
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


def _randomization_p_values(
    found: np.ndarray,
    *,
    dose: np.ndarray,
    stratum: np.ndarray,
    centered: np.ndarray,
    design: Any,
    n_permutations: int,
    seed: int) -> list[float]:
    """Returns the p-values of a test that reassigns the treatment at random.

    Args:
        found: the coefficients to test (the treatment's, and its product's
            with the first control), as estimated.
        dose: the treatment of each row.
        stratum: the stratum of each row, within which the treatment is
            reassigned.
        centered: the outcome, less the mean of its stratum.
        design: a function that makes the regression's columns from a
            treatment.
        n_permutations: the number of reassignments, or 0 for none.
        seed: the seed of the reassignments.

    Returns:
        For each coefficient of `found`, the share of reassignments (counting
            the one found) whose estimate is at least as far from 0, or
            missing values if there are no reassignments.

    """
    if n_permutations <= 0:
        return [np.nan] * len(found)
    generator = np.random.default_rng(seed)
    extreme = np.zeros(len(found))
    for _ in range(n_permutations):
        shuffled = design(_strata.permute_within(dose, stratum, generator))
        estimate, *_ = np.linalg.lstsq(shuffled, centered, rcond = None)
        extreme += np.abs(estimate[:len(found)]) >= np.abs(found) - 1e-12
    return [float((e + 1) / (n_permutations + 1)) for e in extreme]
