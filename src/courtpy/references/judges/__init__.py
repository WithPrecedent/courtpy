"""Identifies the judges in parsed cases and adds what is known about them.

The federal rules find the names of the judges on each case as the opinion
writes them, such as "LYNCH" and "R THOMPSON" (the "panel_judges", "authors",
"concurring", and "dissenting" columns, with "; " between the names). To
study the judges, each name has to be matched to a person. A `Roster` is a
table of judges, with one row for each court that a judge has served on,
which finds the judge that a name refers to from the court and year of the
case.

`build_roster` makes that table with the fjc-biographies package
(https://github.com/WithPrecedent/fjc_biographies), from three files of the
Federal Judicial Center's Biographical Directory of Article III Federal
Judges (which `download` gets with it): the judges' service on each court,
their demographics, and their careers before the bench. The rules in its
"judges" rulebook code the careers, and another rulebook can be named, so
they can be changed without changing courtpy. fjc-biographies also adds
scores of the judges' ideology, which it gets from the judicial-common-space
package (https://github.com/WithPrecedent/judicial_common_space): each
appointment's Judicial Common Space score ("jcs") and the justices'
Martin-Quinn scores ("mq_first", "mq_last", "mq_mean", and "mq_terms"):

```python
import courtpy

roster = courtpy.judges.Roster.from_fjc(jcs = True, martin_quinn = True)
roster.save()
```

A saved roster is kept outside of projects (in "judges" in
`courtpy.utilities.data_folder()`), where the techniques look for it when no
roster is named. It is a CSV file, so judges and columns (such as a score of
each judge's ideology) can be added to it in a spreadsheet. Every column of
numbers or booleans that does not identify or date a judge's service is an
attribute of the judge, which the techniques use.

These techniques use a roster or the tables that it makes. They are added
to the `amos` library as soon as courtpy is imported, so they can be named
in settings. Cases and judges are different things, so the techniques are
built from the mergers and shapers of `amos`, which join tables whose rows
are not the same:

* `merge_biographies` (an `amos.Merger`) adds what the roster says about the
  judge that each row names, such as the author of each opinion.
* `code_panels` (an `amos.Munger`) adds the composition of each case's
  panel: the share of its judges who are women, the mean party of the
  presidents who appointed them, and so on. It makes a row for each judge on
  each case (with `lists_to_rows`), finds the judges (with
  `merge_biographies`), and adds summaries of each case's judges to the case
  (with `merge_summary`).
* `reshape_by_votes` (an `amos.Shaper`) makes a table with one row for each
  judge on each case, with the judge's attributes, those of the other judges
  on the panel, and how the judge voted.
* `reshape_by_panel` (an `amos.Shaper`) undoes `reshape_by_votes`: it makes
  the table of votes a table of cases again.
* `reshape_by_judge` (an `amos.Shaper`) makes a table with one row for each
  judge, which summarizes the judge's votes (with `group_rows`).
* `load_roster` and `download_biographies` (reference loaders, see
  `courtpy.loaders.ReferenceLoader`) start a study of the judges themselves
  with a saved roster or one made from the Federal Judicial Center's files.

The parts are in private modules: `_names` (how names are compared),
`_roster` (the roster and its loaders), `_biographies` (`MergeBiographies`),
and `_panels` (the techniques for panels and votes).

Contents:
    CodePanels: adds the judges and the composition of each case's panel.
    DownloadBiographies: downloads the Federal Judicial Center's files about
        judges and loads the roster that they make.
    LoadRoster: loads the table of a roster of judges.
    MergeBiographies: adds what a roster says about the judge that each row
        names.
    ReshapeByJudge: makes a table with one row for each judge.
    ReshapeByPanel: makes a table of votes a table of cases again.
    ReshapeByVotes: makes a table with one row for each judge on each case.
    Roster: a table of judges that finds the judge a name refers to.
    build_roster: makes the table of a roster from the Federal Judicial
        Center's files with fjc-biographies.
    clean_name: returns a name the way that names are compared.
    download: downloads the Federal Judicial Center's files about judges
        with fjc-biographies.
    name_forms: returns the ways that an opinion may write a judge's name,
        grouped by how much of the name they give.
    vote_table: returns a table with one row for each judge on each case.

"""

from __future__ import annotations

from ._biographies import MergeBiographies
from ._names import clean_name, name_forms
from ._panels import (
    CodePanels,
    ReshapeByJudge,
    ReshapeByPanel,
    ReshapeByVotes,
    vote_table,
)
from ._roster import (
    DownloadBiographies,
    LoadRoster,
    Roster,
    build_roster,
    download,
)

__all__ = [
    'CodePanels',
    'DownloadBiographies',
    'LoadRoster',
    'MergeBiographies',
    'ReshapeByJudge',
    'ReshapeByPanel',
    'ReshapeByVotes',
    'Roster',
    'build_roster',
    'clean_name',
    'download',
    'name_forms',
    'vote_table']
