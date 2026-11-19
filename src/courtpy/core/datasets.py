"""The kinds of datasets that courtpy makes, one for each kind of row.

Each is an `amos.Dataset`, so every technique of `amos` works on it, and
everything that `amos` says about datasets is true of it. What a class adds
is what its rows are, the column that labels them, and how to save and load
it. courtpy's loaders make `Cases`, and its shapers turn one kind into
another:

| Dataset | One row for each | Labeled by | Made by |
| --- | --- | --- | --- |
| `Cases` | Case, with its information and the text of its sections. | `case_id` | courtpy's loaders, `votes_to_cases`, `dockets_to_cases` |
| `Dockets` | Docket number of each case, with the case's columns. A case that consolidated several appeals has a row for each. | `case_docket` | `cases_to_dockets` |
| `Votes` | Judge on each case (or each docket), with the case's columns and the judge's vote. | `vote_id` | `cases_to_votes`, `dockets_to_votes` |
| `Judges` | Judge, with what is known about the judge and summaries of the judge's votes. | `judge_nid` | `cases_to_judges` |
| `Courts` | Court, with summaries of its cases and their judges. | `court_num` | `cases_to_courts` |
| `CaseTypes` | Case type (such as "criminal" or "tort"), with summaries of its cases. | `case_type` | `cases_to_case_types` |
| `PartyTypes` | Party type, with summaries of the cases of parties of that type. | `party_type` | `cases_to_party_types` |

`Cases`, `Dockets`, and `Votes` can be made from each other. `Judges`, `Courts`,
`CaseTypes`, and `PartyTypes` summarize many cases, and they keep nothing
about any one case (such as its docket number or date), so there is no
going back from them.

`save` saves a dataset whole (with its label, split, history, and anything
that techniques have added) in a joblib file, and its data as a table that a
spreadsheet or another program can read, as the `save_data` technique of
`amos` does. `load` loads either one:

```python
import courtpy

cases = courtpy.Cases.load('cases.csv')
cases.save('cases.parquet')
```

Contents:
    CaseTypes: a table with one row for each case type.
    Cases: a table with one row for each case.
    CourtData: base class for courtpy's datasets.
    Courts: a table with one row for each court.
    Dockets: a table with one row for each docket number of each case.
    Judges: a table with one row for each judge.
    PartyTypes: a table with one row for each party type.
    Votes: a table with one row for each judge on each case.
    _TABLE_FORMATS: the format of the table that `CourtData.save` saves, by
        the extension of the file.

"""

from __future__ import annotations

import copy
import dataclasses
import pathlib
from typing import Any, ClassVar, Self

import amos
import nagata
import pandas as pd

from . import cases

_TABLE_FORMATS: dict[str, str | None] = {
    '.csv': 'csv',
    '.parquet': 'parquet',
    '.xlsx': 'excel',
    '.joblib': None,
    '': None}


@dataclasses.dataclass(eq = False)
class CourtData(amos.Dataset):
    """Base class for courtpy's datasets.

    A subclass names the column that labels its rows (`key`). It has no
    fields of its own, so a dataset of one kind can become another (see
    `adopt`) without losing anything.

    Args:
        data: the data. Defaults to an empty `DataFrame`.
        (the other arguments of `amos.Dataset`)

    Attributes:
        key: the name of the index of the rows (such as "case_id").

    """

    key: ClassVar[str] = ''

    """ Class Methods """

    @classmethod
    def adopt(cls, dataset: amos.Dataset) -> Self:
        """Returns `dataset` as a dataset of this kind.

        The new dataset shares everything with `dataset` (its data, label,
        split, history, and so on), so a shaper can hand on a dataset of
        another kind. If the data has a column named `key`, it labels the
        rows.

        Args:
            dataset: a dataset of any kind.

        Returns:
            `dataset` itself if it is already of this kind, and otherwise a
                new dataset of this kind with the same attributes.

        """
        if type(dataset) is cls:
            adopted = dataset
        else:
            adopted = cls.__new__(cls)
            adopted.__dict__.update(dataset.__dict__)
        adopted._label_rows()
        return adopted

    @classmethod
    def create(cls, item: Any, **kwargs: Any) -> Self:
        """Returns a dataset of this kind made from `item`.

        Args:
            item: anything that `amos.Dataset.create` takes: a dataset, a
                table, or the path of a data file (including a joblib file
                that `save` saved).
            **kwargs: arguments of `amos.Dataset.create`, such as "label"
                and "groups".

        Returns:
            The dataset.

        """
        return cls.adopt(amos.Dataset.create(item, **kwargs))

    @classmethod
    def load(cls, path: pathlib.Path | str, **kwargs: Any) -> Self:
        """Loads a dataset that `save` saved, or a table of one.

        A joblib file holds the whole dataset, which goes on from where it
        was saved. A table (such as a CSV or parquet file) holds only its
        data: the column named `key` labels the rows again, and columns of
        booleans and whole numbers with missing values get the types that
        allow them (see `cases.tidy`).

        Args:
            path: the path of the file.
            **kwargs: arguments of `amos.Dataset.create`, such as "label"
                and "groups".

        Raises:
            FileNotFoundError: if there is no file at `path`.
            TypeError: if the file holds a courtpy dataset of another kind.

        Returns:
            The dataset.

        """
        path = pathlib.Path(path).expanduser()
        if not path.is_file():
            message = f'there is no file of {cls.__name__} at {path}'
            raise FileNotFoundError(message)
        loaded = amos.Dataset.create(path, **kwargs)
        if isinstance(loaded, CourtData) and not isinstance(loaded, cls):
            message = (
                f'{path} holds {type(loaded).__name__}, not {cls.__name__}: '
                f'load it with courtpy.{type(loaded).__name__}.load'
            )
            raise TypeError(message)
        dataset = loaded if isinstance(loaded, cls) else cls.adopt(loaded)
        if not isinstance(loaded, CourtData):
            dataset.data = cases.tidy(dataset.data)
            dataset._label_rows()
        return dataset

    """ Public Methods """

    def save(
        self,
        path: pathlib.Path | str,
        *,
        clerk: nagata.FileManager | None = None,
        compress: int | bool = 0) -> list[pathlib.Path]:
        """Saves the whole dataset, and its data as a table.

        The `save_data` technique of `amos` saves the dataset in a joblib file
        named for `path` (such as "cases.joblib" beside "cases.csv"), which
        `load` loads as it was, and the data in `path`, in the format of its
        extension: ".csv", ".parquet", or ".xlsx". A path ending in ".joblib"
        (or with no extension) saves only the dataset. Several values in one
        cell (such as the lists that `split_values` makes) are saved as text,
        with "; " between them, as courtpy's rules write them. The dataset's
        history records where the files are.

        Args:
            path: the path of the table. Its folder is made if needed.
            clerk: the file manager that saves the files. Defaults to `None`,
                in which case one for the folder of `path` is used, so
                nothing else is made.
            compress: how much joblib compresses the file of the dataset,
                from 0 (not at all) to 9. Defaults to 0.

        Raises:
            ValueError: if the extension of `path` is not one listed above.

        Returns:
            The paths of the files that were saved.

        """
        path = pathlib.Path(path).expanduser().resolve()
        suffix = path.suffix.lower()
        if suffix not in _TABLE_FORMATS:
            message = (
                f'{path.name} must end in one of '
                f'{[s for s in _TABLE_FORMATS if s]}')
            raise ValueError(message)
        folder = path.parent
        folder.mkdir(parents = True, exist_ok = True)
        if clerk is None:
            clerk = nagata.FileManager(
                root_folder = folder,
                input_folder = folder,
                interim_folder = folder,
                output_folder = folder)
        joined = copy.copy(self)
        joined.data = _join_lists(self.data)
        joined.history = list(self.history)
        amos.savers.SaveData(clerk = clerk).apply(
            joined,
            folder = folder,
            file_name = path.stem,
            table_format = _TABLE_FORMATS[suffix] or False,
            compress = compress)
        self.history.append(joined.history[-1])
        return [pathlib.Path(file) for file in joined.history[-1]['files']]

    """ Private Methods """

    def _label_rows(self) -> None:
        """Makes the column named `key`, if the data has one, label the rows.

        A table read from a CSV file has its labels as a column, since a CSV
        file has no index.

        """
        if self.key and self.key in self.data.columns:
            labeled = self.data.set_index(self.key)
            if self.key in {'case_id', 'case_docket', 'vote_id'}:
                labeled.index = labeled.index.astype(str)
            self.data = labeled


@dataclasses.dataclass(eq = False)
class Cases(CourtData):
    """A table with one row for each case.

    The rows are labeled by "case_id", and the columns are what courtpy's
    rules and coders find in each case: its information (court, date,
    parties, judges, and so on), the issues that it discusses, its outcome,
    and (with a loader's "keep_text") the text of its sections. courtpy's
    loaders make it, and `votes_to_cases` makes it from `Votes`.

    """

    key: ClassVar[str] = 'case_id'


@dataclasses.dataclass(eq = False)
class Dockets(CourtData):
    """A table with one row for each docket number of each case.

    A case that decided several consolidated appeals has several docket
    numbers, and records kept by docket (such as the Federal Judicial
    Center's Integrated Database, which `add_idb` adds) have one for each.
    The rows are labeled by "case_docket" (the case's id and the docket's
    place among its docket numbers, such as "4567890-2"), "case_id" says
    which case each row belongs to, and "docket" is the row's one docket
    number. Each row has the case's columns. `cases_to_dockets` makes it from
    `Cases`, and `dockets_to_cases` and `dockets_to_votes` make `Cases` and
    `Votes` from it.

    """

    key: ClassVar[str] = 'case_docket'


@dataclasses.dataclass(eq = False)
class Votes(CourtData):
    """A table with one row for each judge on each case.

    The rows are labeled by "vote_id" (the case's id and the judge's place on
    the panel, such as "4567890-2"), and "case_id" says which case each row
    belongs to. Each row has the case's columns, the judge's (such as
    "judge_party"), the other judges' (such as "colleagues_party"), and the
    judge's vote (such as "vote_reversal"). `cases_to_votes` makes it from
    `Cases`.

    """

    key: ClassVar[str] = 'vote_id'


@dataclasses.dataclass(eq = False)
class Judges(CourtData):
    """A table with one row for each judge.

    The rows are labeled by "judge_nid" (the Federal Judicial Center's number
    for the judge). Each row has the judge's name, the number of the judge's
    cases, what is known about the judge, and the means of the judge's votes:
    the share of the judge's votes to reverse, the share of the judge's cases
    of each case type, and so on. `cases_to_judges` makes it from `Cases` or
    `Votes`.

    """

    key: ClassVar[str] = 'judge_nid'


@dataclasses.dataclass(eq = False)
class Courts(CourtData):
    """A table with one row for each court.

    The rows are labeled by the court's number ("court_num", unless another
    column was named). Each row has the number of the court's cases and of
    its judges, and the means of its cases' columns: the share of its cases
    of each case type, the share that it reversed, the mean composition of
    its panels, and so on. `cases_to_courts` makes it from `Cases`.

    """

    key: ClassVar[str] = 'court_num'


@dataclasses.dataclass(eq = False)
class CaseTypes(CourtData):
    """A table with one row for each case type.

    The rows are labeled by "case_type" (such as "criminal", "civil", "tort",
    or "contract"; see `code_case_type`). Each row has the number of cases of
    the type and the means of their columns. A case of several types (such
    as a tort case and a contract case) counts for each of them.
    `cases_to_case_types` makes it from `Cases`.

    """

    key: ClassVar[str] = 'case_type'


@dataclasses.dataclass(eq = False)
class PartyTypes(CourtData):
    """A table with one row for each party type.

    The rows are labeled by "party_type" (such as "individual" or
    "corporation"). Each row has the number of parties of the type, the
    share of them that won, and the means of the columns of their cases.
    `cases_to_party_types` makes it from `Cases` whose parties have types.

    """

    key: ClassVar[str] = 'party_type'


""" Private Functions """


def _join_lists(data: pd.DataFrame) -> pd.DataFrame:
    """Returns a table with each list in a cell joined into text.

    Args:
        data: the table.

    Returns:
        A copy of `data` in which each list or tuple in a column of objects
            is its items, joined with "; ". `data` itself if it has none.

    """
    listed = [
        column for column in data.columns
        if data[column].dtype == object
        and data[column].map(_is_list).any()]
    if not listed:
        return data
    joined = data.copy()
    for column in listed:
        joined[column] = joined[column].map(
            lambda v: cases._SEPARATOR.join(map(str, v)) if _is_list(v)
            else v)
    return joined


def _is_list(value: Any) -> bool:
    """Returns whether a value is a `list` or `tuple`.

    Args:
        value: a cell of a table.

    Returns:
        Whether it is a `list` or `tuple`.

    """
    return isinstance(value, list | tuple)
