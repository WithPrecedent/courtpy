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

* `add_biography` (an `amos.Merger`) adds what the roster says about each
  judge that each row names. Each row of `Votes` gets "judge_party",
  "judge_woman", and so on, and each row of `Cases` gets them for each seat
  of its panel: "judge_name1", "judge_party1", "judge_woman1", and so on
  for the first judge, "judge_name2" and the rest for the second.
* `add_jcs` (an `amos.Merger`) is `add_biography` for each judge's Judicial
  Common Space score alone ("judge_jcs", or "judge_jcs1" and so on).
* `add_circuit` (an `amos.Merger`) adds the median and total of the parties
  of the appointing presidents, and of the Judicial Common Space scores, of
  the active (not senior) judges of each case's circuit on the day it was
  decided.
* `code_panels` (an `amos.Munger`) adds the composition of each case's
  panel: the share of its judges who are women, the mean party of the
  presidents who appointed them, and so on. It makes a row for each judge on
  each case (with `lists_to_rows`), finds the judges (with
  `add_biography`), and adds summaries of each case's judges to the case
  (with `merge_summary`).
* `cases_to_votes` (an `amos.Shaper`) makes `Votes`: a table with one row
  for each judge on each case, with the judge's attributes, those of the
  other judges on the panel, and how the judge voted.
* `dockets_to_votes` (an `amos.Shaper`) is `cases_to_votes` for `Dockets`:
  a row for each judge on each docket.
* `votes_to_cases` (an `amos.Shaper`) undoes `cases_to_votes`: it makes
  `Votes` `Cases` again.
* `cases_to_judges` (an `amos.Shaper`) makes `Judges`: a table with one row
  for each judge, which summarizes the judge's votes (with `group_rows`).
* `load_roster` and `download_biographies` (reference loaders, see
  `courtpy.loaders.ReferenceLoader`) start a study of the judges themselves
  with a saved roster or one made from the Federal Judicial Center's files.

The parts are in private modules: `_names` (how names are compared),
`_roster` (the roster and its loaders), `_biographies` (`AddBiography` and
`AddJcs`), `_circuits` (`AddCircuit`), and `_panels` (the techniques for
panels and votes).

Contents:
    AddBiography: adds what a roster says about each judge that each row
        names.
    AddCircuit: adds the ideology of the active judges of each case's
        circuit when the case was decided.
    AddJcs: adds the Judicial Common Space score of each judge that each row
        names.
    CasesToJudges: makes a table with one row for each judge.
    CasesToVotes: makes a table with one row for each judge on each case.
    CodePanels: adds the judges and the composition of each case's panel.
    DocketsToVotes: makes a table with one row for each judge on each
        docket.
    DownloadBiographies: downloads the Federal Judicial Center's files about
        judges and loads the roster that they make.
    LoadRoster: loads the table of a roster of judges.
    Roster: a table of judges that finds the judge a name refers to.
    VotesToCases: makes a table of votes a table of cases again.
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

from ._biographies import AddBiography, AddJcs
from ._circuits import AddCircuit
from ._names import clean_name, name_forms
from ._panels import (
    CasesToJudges,
    CasesToVotes,
    CodePanels,
    DocketsToVotes,
    VotesToCases,
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
    'AddBiography',
    'AddCircuit',
    'AddJcs',
    'CasesToJudges',
    'CasesToVotes',
    'CodePanels',
    'DocketsToVotes',
    'DownloadBiographies',
    'LoadRoster',
    'Roster',
    'VotesToCases',
    'build_roster',
    'clean_name',
    'download',
    'name_forms',
    'vote_table']
