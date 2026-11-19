"""Strata of cases (such as a court in a year), which the critics share.

Panels are assigned at random within a court in a year (or so a study
assumes), so the critics compare cases only with the cases of their own
stratum: they remove each stratum's mean and shuffle values within strata.

Contents:
    demean: returns values less the mean of their stratum.
    permute_within: returns values shuffled within their strata.
    stratum_codes: returns the stratum of each row as a whole number.

"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from ..core import cases

""" Public Functions """


def demean(values: np.ndarray, codes: np.ndarray) -> np.ndarray:
    """Returns values less the mean of their stratum.

    Args:
        values: the values, one for each row (or a column for each of
            several variables, a row for each row of the data).
        codes: the stratum of each row (see `stratum_codes`), from 0.

    Returns:
        The values, with the mean of each stratum's values subtracted from
            them, in the shape of `values`.

    """
    counts = np.bincount(codes)
    if values.ndim == 1:
        means = np.bincount(codes, weights = values) / counts
        single: np.ndarray = values - means[codes]
        return single
    centered = np.empty_like(values, dtype = float)
    for column in range(values.shape[1]):
        means = np.bincount(codes, weights = values[:, column]) / counts
        centered[:, column] = values[:, column] - means[codes]
    return centered


def permute_within(
    values: np.ndarray,
    codes: np.ndarray,
    generator: np.random.Generator) -> np.ndarray:
    """Returns values shuffled within their strata.

    Args:
        values: the values, one for each row.
        codes: the stratum of each row (see `stratum_codes`).
        generator: the source of random numbers.

    Returns:
        The values, each moved to a random row of its own stratum, so each
            stratum keeps the same values (and so the same mean).

    """
    ordered = np.argsort(codes, kind = 'stable')
    shuffled = np.lexsort((generator.random(len(codes)), codes))
    permuted = np.empty_like(values)
    permuted[ordered] = values[shuffled]
    return permuted


def stratum_codes(
    data: pd.DataFrame,
    columns: Sequence[str]) -> pd.Series:
    """Returns the stratum of each row as a whole number.

    Args:
        data: the rows.
        columns: the columns whose values together make a stratum, such as
            "court_num" and "year".

    Raises:
        KeyError: if `data` lacks a column of `columns`.

    Returns:
        A number for each stratum, from 0, with -1 for a row that is missing
            any of `columns`.

    """
    cases.require_columns(data, list(columns), 'the strata')
    codes, _ = pd.MultiIndex.from_frame(
        data[list(columns)].astype('string')).factorize()
    missing = data[list(columns)].isna().any(axis = 1).to_numpy()
    return pd.Series(np.where(missing, -1, codes), index = data.index)
