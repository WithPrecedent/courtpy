"""Techniques that load court cases into an `amos` project.

Loaders make a project's data from a source named in its settings, so a
project with a loader needs no `item`. They are usually the first step of the
wrangler, and they work through the project's clerk (its
`nagata.FileManager`): a folder or file named by a relative path is looked
for in the current folder and then in the clerk's input folder (the
"input_folder" of the "files" section), and downloads are saved in the input
folder.

courtpy's loaders collect court cases (downloading or dividing them first, if
asked), parse them with rulebooks, and code them, so the label of a study
(such as "outcome_reversal", which a coder makes) exists when the data is
loaded. As with reference data, `load_courtlistener` parses the cases that
were saved before, and `download_courtlistener` downloads them first (from
CourtListener's bulk data, unless "method" is "api"):

```ini
[general]
seed = 43
label = outcome_reversal

[files]
input_folder = data

[appeals_project]
appeals_workers = wrangler, analyst, critic

[wrangler]
techniques = download_courtlistener, drop_text_columns

[download_courtlistener_parameters]
source = courtlistener
method = bulk
courts = federal_geographic_circuits
start_date = 2019-01-01
end_date = 2019-12-31
save = cases.csv
reuse = true
```

Every loader takes these parameters, set in its "{name}_parameters" section:

| Parameter | Meaning |
| --- | --- |
| `source` | The folder of saved cases (or, for `load_cases`, a saved table). |
| `coders` | Techniques to apply after parsing. Defaults to "code_parties, code_case_type, code_outcome" ("none" for `load_cases`). Use "none" for none. |
| `save` | File to save the coded table to (".csv", ".parquet", or ".xlsx"), with the whole dataset beside it in a joblib file of the same name (see `Cases.save`). A relative path is in the clerk's interim folder. |
| `reuse` | Whether to load the saved dataset, if there is one, instead of collecting, parsing, and coding the cases again. Defaults to false. |
| `label`, `task`, `groups` | As in `amos`: they default to those in the "general" section. |

Other modules add reference loaders (see `ReferenceLoader`), which load a
table that describes something other than cases. Each "load_" technique
loads the files that courtpy keeps (or a file named as its "source"), and
each "download_" technique downloads the files first, again if "refresh" is
true:

| Technique | Table | Module |
| --- | --- | --- |
| `load_roster`, `download_biographies` | A roster of judges. | `courtpy.judges` |
| `load_scdb`, `download_scdb` | The Supreme Court Database's cases or votes. | `courtpy.scdb` |
| `load_idb`, `download_idb` | The Integrated Database's appeals. | `courtpy.fjc_idb` |
| `load_politics`, `download_politics` | The political context of each year. | `courtpy.politics` |
| `download_jcs` | The Judicial Common Space scores. | `courtpy.jcs` |

Contents:
    CaseLoader: base class for techniques that load court cases.
    LoadCases: loads a dataset of cases saved by `Cases.save`, or a table of
        one.
    DownloadCourtlistener: downloads CourtListener cases, and parses and
        codes them.
    LoadCourtlistener: parses and codes saved CourtListener cases.
    LoadLexisNexis: divides, parses, and codes Lexis-Nexis cases.
    ReferenceLoader: base class for techniques that load a table of
        reference data, such as `load_scdb` and `download_biographies`.
    SourceLoader: base class for loaders that parse a folder of a source's
        saved cases.

"""

from __future__ import annotations

import abc
import dataclasses
import pathlib
from typing import Any, ClassVar

import amos
import pandas as pd

from ..core import datasets, options, utilities

# Importing the modules of the sources adds them to `base.SOURCES`.
from ..sources import courtlistener, lexis
from . import coders, parsers


@dataclasses.dataclass
class CaseLoader(amos.Loader, abc.ABC):
    """Base class for techniques that load court cases.

    A subclass writes `load`, which collects and parses the cases at a source
    (a folder or file, already found with the clerk) and returns a table of
    them, one row for each case. `apply` then codes the table with the
    loader's "coders", saves it if "save" is set, and makes it the dataset
    that the rest of the workflow works on, with the label, task, and groups
    from the loader's parameters (which default to the "general" section of
    the settings). The label can be a column that a coder makes. If no coder
    makes it, it is pending, as in `amos`: a later technique (such as
    "derive_columns") can still make it, and using it before then raises an
    error. The dataset's history records the loader and then each coder.

    The dataset is `Cases`, or the kind that the last of the coders makes
    (such as `Votes`, if "cases_to_votes" is the last). If "save" is set, it
    is saved with `CourtData.save`: whole, in a joblib file beside the table
    (such as "cases.joblib" beside "cases.csv"), and as the table. If
    "reuse" is true and it was saved before, the saved dataset is loaded
    instead (from the joblib file, or else from the table), and nothing is
    collected, parsed, or coded again.

    Args:
        name: name used to refer to the technique in a workflow. Defaults to
            `None`, in which case it is the snake case name of the class.
        contents: not used. Defaults to `None`.
        parameters: "source", "coders", "save", "reuse", "label", "task", and
            "groups" (see the module's documentation), and parameters for
            `load`. Defaults to an empty `dict`.
        clerk: the file manager that finds folders and files. Defaults to
            `None`, in which case one for the current folder is made when it
            is needed. A loader built from a project's settings uses the
            project's clerk.

    Attributes:
        default_coders: the coders applied when "coders" is not set.
        default_source: the source used when "source" is not set, or `None`
            if a source must be set.

    """

    default_coders: ClassVar[tuple[str, ...]] = options._DEFAULT_CODERS
    default_source: ClassVar[str | None] = None

    """ Public Methods """

    def apply(self, item: amos.Dataset, **kwargs: Any) -> amos.Dataset:
        """Loads, codes, and saves the cases, as a dataset continuing `item`.

        Args:
            item: the dataset so far, whose seed and history are kept.
            **kwargs: "source", "coders", "save", "reuse", "label", "task", and
                "groups", and parameters for `load`.

        Raises:
            ValueError: if there is no "source" and the loader has no default
                source.

        Returns:
            The dataset of the coded cases.

        """
        source = kwargs.pop('source', None) or self.default_source
        if source is None:
            message = (
                f'{self.name!r} has nothing to load: set its "source" in the '
                f'"{self.name}_parameters" section of the settings'
            )
            raise ValueError(message)
        label = kwargs.pop('label', None) or item.label
        task = kwargs.pop('task', None)
        groups = kwargs.pop('groups', None) or item.groups or None
        names = kwargs.pop('coders', self.default_coders)
        save = kwargs.pop('save', None)
        reuse = utilities.to_bool(kwargs.pop('reuse', False))
        saved = self._interim(save) if save else None
        reused = _reusable(saved) if saved is not None and reuse else None
        dataset: amos.Dataset
        if reused is not None:
            dataset = LoadCases().load(reused)
            dataset.seed = item.seed
            dataset.history = [*item.history, *dataset.history]
            dataset.record(
                self.name, source = str(source), reused = str(reused),
                rows = len(dataset.data), columns = len(dataset.data.columns))
        else:
            loaded = self.load(self._locate(source), **kwargs)
            if isinstance(loaded, amos.Dataset):
                dataset = loaded
                dataset.seed = item.seed
                dataset.history = [*item.history, *dataset.history]
            else:
                dataset = datasets.Cases(data = loaded, seed = item.seed)
                dataset.history = item.history
            dataset.record(
                self.name, source = str(source), rows = len(dataset.data),
                columns = len(dataset.data.columns))
            dataset = coders.code(dataset, names)
            if saved is not None and isinstance(dataset, datasets.CourtData):
                dataset.save(saved, clerk = self._get_clerk())
        return type(dataset).create(
            dataset, label = label, task = task, groups = groups)

    """ Private Methods """

    def _interim(self, path: Any) -> pathlib.Path:
        """Returns where to save a table of cases.

        Args:
            path: the "save" parameter: a path to a ".csv" or ".parquet" file.

        Returns:
            `path` itself if it is absolute, and otherwise `path` in the
                clerk's interim folder.

        """
        resolved = pathlib.Path(str(path)).expanduser()
        if resolved.is_absolute():
            return resolved
        return pathlib.Path(self._get_clerk().interim_folder) / resolved

    def _locate(self, path: Any) -> pathlib.Path:
        """Returns a folder or file named in the settings, found with the clerk.

        Args:
            path: a path from the settings, which may begin with "~" for the
                user's home folder.

        Returns:
            `path` itself if it is absolute or exists in the current folder,
                and otherwise `path` in the clerk's input folder (where a
                download saves its cases, even if the folder does not exist
                yet).

        """
        resolved = pathlib.Path(str(path)).expanduser()
        if resolved.is_absolute() or resolved.exists():
            return resolved
        return pathlib.Path(self._get_clerk().input_folder) / resolved


@dataclasses.dataclass
class LoadCases(CaseLoader):
    """Loads a dataset of cases saved by `Cases.save`, or a table of one.

    A joblib file holds the whole dataset, of the kind that it was (so a
    saved `Votes` is `Votes` again), with its history. A table (such as a
    CSV or parquet file) becomes `Cases`, labeled by "case_id", and columns
    of booleans and whole numbers with missing values get types that allow
    them (see `CourtData.load`). A saved dataset is usually coded already,
    so no coders are applied unless "coders" names some.

    """

    default_coders: ClassVar[tuple[str, ...]] = ()

    def load(self, source: Any, **kwargs: Any) -> amos.Dataset:
        """Loads the dataset at `source`.

        Args:
            source: path of a joblib, CSV, or parquet file saved by
                `CourtData.save`, found with the clerk.
            **kwargs: not used.

        Raises:
            FileNotFoundError: if there is no file at `source`.

        Returns:
            The dataset.

        """
        loaded = datasets.CourtData.load(pathlib.Path(source))
        if type(loaded) is datasets.CourtData:
            return datasets.Cases.adopt(loaded)
        return loaded


@dataclasses.dataclass
class SourceLoader(CaseLoader, abc.ABC):
    """Base class for loaders that parse a folder of a source's saved cases.

    The source is a folder of saved cases of the `courtpy.sources.Source`
    named by `reads`. A subclass sets `reads` and `default_source`, and can
    extend `load` to collect the cases first (as `DownloadCourtlistener`
    downloads them and `LoadLexisNexis` divides files of many cases).

    | Parameter | Meaning |
    | --- | --- |
    | `rulebooks` | Rules to parse with (such as "civil, criminal"), after the source's header rules and "general", which are always applied. Defaults to "federal". |
    | `keep_text` | Whether to keep the text of the cases' sections (such as "party", "history", and "opinion") in the table, which `parse_all` can parse again. |
    | `limit` | Most cases to parse, for trying out rules. |
    | `workers` | Number of processes to parse with. |

    Attributes:
        reads: the name of the source of the saved cases, such as
            "courtlistener".

    """

    reads: ClassVar[str] = ''

    """ Required Methods """

    def load(
        self,
        source: Any,
        *,
        rulebooks: Any = None,
        keep_text: Any = False,
        limit: Any = None,
        workers: Any = None,
        **kwargs: Any) -> pd.DataFrame:
        """Parses the folder `source`.

        Args:
            source: the folder of saved cases, found with the clerk.
            rulebooks: rules to parse with. Defaults to `None`, in which case
                `options._DEFAULT_JURISDICTION` is used.
            keep_text: whether to keep the text of the cases' sections.
                Defaults to `False`.
            limit: most cases to parse. Defaults to `None` (every case).
            workers: number of processes to parse with. Defaults to `None`
                (one).
            **kwargs: not used.

        Raises:
            ValueError: if no cases are found.

        Returns:
            The table of parsed cases, labeled by "case_id".

        """
        return _parse(
            pathlib.Path(source), self.reads, rulebooks = rulebooks,
            keep_text = keep_text, limit = limit, workers = workers)


@dataclasses.dataclass
class LoadCourtlistener(SourceLoader):
    """Parses and codes cases saved from CourtListener.

    The source is a folder of cases saved by `courtpy.CourtListener` (by
    default, "courtlistener" in the clerk's input folder), from its bulk
    data or its API. To download them first, use `download_courtlistener`.
    It takes the parameters of `SourceLoader`.

    """

    default_source: ClassVar[str | None] = 'courtlistener'
    reads: ClassVar[str] = 'courtlistener'


@dataclasses.dataclass
class DownloadCourtlistener(LoadCourtlistener):
    """Downloads cases from CourtListener, and parses and codes them.

    The cases are downloaded into the source folder (by default,
    "courtlistener" in the clerk's input folder) with
    `courtpy.CourtListener.download`, and then the folder is parsed as
    `load_courtlistener` parses it. With "bulk" (the default), they are
    extracted from CourtListener's bulk data, which needs no API key. With
    "api", they are downloaded with the API, with the key from
    `courtpy.secrets`. Cases that were saved before are not downloaded again
    unless "refresh" is true.

    It takes the parameters of `SourceLoader`, and these:

    | Parameter | Meaning |
    | --- | --- |
    | `method` | "bulk" (the default) or "api". |
    | `courts` | CourtListener court ids (such as "ca1, ca2") or groups (such as "federal_appellate") to download. |
    | `start_date`, `end_date` | Dates filed to download (YYYY-MM-DD). |
    | `max_cases` | Most cases to download: in all with "bulk", and in each court with "api". |
    | `refresh` | Whether to download cases that were already saved. |
    | `dockets` | For "api", whether to download each case's docket too (the bulk data always has it). |
    | `bulk_folder`, `bulk_date`, `stream` | For "bulk", where to keep the bulk files (found with the clerk), which date's files to use, and whether to read them without saving them. |

    """

    """ Required Methods """

    def load(
        self,
        source: Any,
        *,
        method: Any = 'bulk',
        courts: Any = None,
        start_date: Any = None,
        end_date: Any = None,
        max_cases: Any = None,
        refresh: Any = False,
        dockets: Any = False,
        bulk_folder: Any = None,
        bulk_date: Any = None,
        stream: Any = False,
        **kwargs: Any) -> pd.DataFrame:
        """Downloads the cases into the folder `source` and parses it.

        Settings can be text (as a settings file gives them), so each is
        converted to the type it needs.

        Args:
            source: the folder to save the cases in, found with the clerk.
            method: "bulk" or "api". Defaults to "bulk".
            courts: CourtListener court ids or groups to download. Defaults
                to `None`, which raises an error.
            start_date: earliest date filed to download (YYYY-MM-DD).
                Defaults to `None`.
            end_date: latest date filed to download (YYYY-MM-DD). Defaults
                to `None`.
            max_cases: most cases to download. Defaults to `None` (every
                case).
            refresh: whether to download cases that were already saved.
                Defaults to `False`.
            dockets: with "api", whether to download each case's docket too.
                Defaults to `False`.
            bulk_folder: with "bulk", the folder to keep the bulk files in,
                found with the clerk. Defaults to `None`, in which case
                "bulk" in `utilities.data_folder()` is used.
            bulk_date: with "bulk", the date of the files to use. Defaults to
                `None` (the newest).
            stream: with "bulk", whether to read the files without saving
                them. Defaults to `False`.
            **kwargs: the parameters of `SourceLoader.load`.

        Raises:
            ValueError: if "method" is not "bulk" or "api", if no courts are
                named, or if no cases are found.

        Returns:
            The table of parsed cases, labeled by "case_id".

        """
        folder = pathlib.Path(source)
        client = courtlistener.CourtListener(
            bulk_folder = self._locate(bulk_folder) if bulk_folder else None,
            bulk_date = utilities.to_date(bulk_date),
            stream = utilities.to_bool(stream))
        client.download(
            courts or [],
            utilities.to_date(start_date),
            utilities.to_date(end_date),
            folder,
            method = str(method),
            max_cases = utilities.to_integer(max_cases),
            dockets = utilities.to_bool(dockets),
            refresh = utilities.to_bool(refresh))
        return super().load(folder, **kwargs)


@dataclasses.dataclass
class LoadLexisNexis(SourceLoader):
    """Divides, parses, and codes cases downloaded from Lexis-Nexis.

    The source is a folder of Lexis-Nexis cases, one per text file (by
    default, "lexis_nexis" in the clerk's input folder). If "batches" names
    files (or folders) of many cases, as Lexis-Nexis downloads them, they are
    divided into the source folder first (see `courtpy.lexis.split`).

    It takes the parameters of `SourceLoader`, and:

    | Parameter | Meaning |
    | --- | --- |
    | `batches` | Lexis-Nexis downloads of many cases to divide first. |

    """

    default_source: ClassVar[str | None] = 'lexis_nexis'
    reads: ClassVar[str] = 'lexis_nexis'

    """ Required Methods """

    def load(
        self,
        source: Any,
        *,
        batches: Any = None,
        **kwargs: Any) -> pd.DataFrame:
        """Divides any batches into the folder `source` and parses it.

        Args:
            source: the folder of Lexis-Nexis cases, found with the clerk.
            batches: files or folders of downloads of many cases, found with
                the clerk. The ".txt" files in a folder are used. Defaults to
                `None` (none).
            **kwargs: the parameters of `SourceLoader.load`.

        Returns:
            The table of parsed cases, labeled by "case_id".

        """
        folder = pathlib.Path(source)
        if batches:
            files = []
            for batch in utilities.listify(batches):
                found = self._locate(batch)
                files.extend(
                    sorted(found.glob('*.txt')) if found.is_dir() else [found])
            lexis.split(files, folder)
        return super().load(folder, **kwargs)


@dataclasses.dataclass
class ReferenceLoader(amos.Loader, abc.ABC):
    """Base class for techniques that load a table of reference data.

    Reference data describes something other than parsed cases: the judges,
    the Supreme Court Database, the Integrated Database, or the political
    context of each year. Unlike a `CaseLoader`, a reference loader needs no
    "source". Without one, it loads the files that courtpy keeps outside of
    projects (in `courtpy.utilities.data_folder()`), which are downloaded
    first if they are missing, and the dataset's history records the source
    as "current". A relative "source" is looked for in the current folder and
    then in the clerk's input folder.

    Like every loader, it starts a new dataset, so it usually begins a study
    whose rows are what the table describes (such as each justice's vote in
    each case). To add a table's columns to parsed cases, use a merger (such
    as `add_scdb`) instead.

    Attributes:
        default_source: the source that is recorded when "source" is not
            set.

    """

    default_source: ClassVar[str] = 'current'

    """ Public Methods """

    def apply(self, item: amos.Dataset, **kwargs: Any) -> amos.Dataset:
        """Loads the table into a dataset that continues `item`.

        Args:
            item: the dataset so far, whose seed and history are kept.
            **kwargs: "source", "label", "task", and "groups", and parameters
                for `load`.

        Returns:
            The dataset of the loaded table.

        """
        kwargs['source'] = kwargs.get('source') or self.default_source
        return super().apply(item, **kwargs)

    """ Private Methods """

    def _choose(self, value: Any) -> bool | pathlib.Path | None:
        """Returns a setting that names a file or says whether to use one.

        Args:
            value: `None`, a `bool`, text that `utilities.to_bool` reads
                (such as "false"), or the path of a file.

        Returns:
            `None`, the boolean, or the path, found with the clerk (see
                `utilities.locate`).

        """
        if value is None or isinstance(value, bool):
            return value
        try:
            return utilities.to_bool(value)
        except ValueError:
            return utilities.locate(value, self._get_clerk())

    def _locate(self, source: Any) -> pathlib.Path | None:
        """Returns the folder or file that a source names.

        Args:
            source: the "source" parameter.

        Returns:
            `None` if `source` is missing or `default_source` (so the current
                files are used), and otherwise the path, found with the
                clerk (see `utilities.locate`).

        """
        if source is None or str(source) == self.default_source:
            return None
        return utilities.locate(source, self._get_clerk())


""" Private Functions """


def _parse(
    folder: pathlib.Path,
    source: str,
    *,
    rulebooks: Any,
    keep_text: Any,
    limit: Any,
    workers: Any) -> pd.DataFrame:
    """Parses a folder of saved cases with settings that may be text.

    Args:
        folder: the folder of saved cases.
        source: the name of their source, such as "courtlistener".
        rulebooks: rules to parse with, or `None` (or blank) for
            `options._DEFAULT_JURISDICTION`.
        keep_text: whether to keep the text of the cases' sections.
        limit: most cases to parse, or `None` for every case.
        workers: number of processes to parse with, or `None` for one.

    Raises:
        ValueError: if no cases are found in `folder`.

    Returns:
        The table of parsed cases, labeled by "case_id".

    """
    data = parsers.parse(
        folder,
        source = source,
        rulebooks = rulebooks or options._DEFAULT_JURISDICTION,
        keep_text = utilities.to_bool(keep_text),
        limit = utilities.to_integer(limit),
        workers = utilities.to_integer(workers) or 1)
    if data.empty:
        message = f'no {source} cases were found in {folder}'
        raise ValueError(message)
    return data


def _reusable(saved: pathlib.Path) -> pathlib.Path | None:
    """Returns the file of a saved dataset that a loader can reuse.

    Args:
        saved: the path of the saved table (the loader's "save").

    Returns:
        The joblib file beside it (which holds the whole dataset), if there is
            one, or else the table, if it exists, or else `None`.

    """
    whole = saved.with_suffix('.joblib')
    if whole.is_file():
        return whole
    return saved if saved.is_file() else None
