# Advanced User Guide

The [tutorial](tutorial.md) shows how to build a study. This guide describes
how courtpy works and everything you can configure.

## How the pieces fit together

```text
CourtListener ──BulkData / CourtListener──▶ saved cases ──read──▶ Case ──Parser──▶ case table ──coders──▶ amos.Dataset ──amos.Project──▶ results
Lexis-Nexis   ──lexis.split──────────────▶ (JSON or text)        (sections   (rulebooks)  (one row      (parties,                   (models, tables,
                                                                   of text)                 per case)     outcomes)                   figures, report)
```

In a project, a loader (such as `load_court_listener`) does every step before
`amos.Dataset` as the first technique of the wrangler.

courtpy's modules are in four folders, as `amos` keeps its modules in a
folder for each stage: `sources` (where cases come from), `wrangler`
(courtpy's steps of the `amos` wrangler), `references` (tables that
describe something other than cases), and `core` (what the others share).
Each module can also be imported from `courtpy` itself (such as
`courtpy.judges` for `courtpy.references.judges`).

| Folder | Module | Contents |
| --- | --- | --- |
| sources | `courtpy.bulk` | `BulkData`, which extracts cases from CourtListener's bulk data. |
| sources | `courtpy.courtlistener` | `CourtListener`, a client for the REST API, and `read_case`, which reads a saved CourtListener case. |
| sources | `courtpy.lexis` | `split` and `read_case` for Lexis-Nexis text files. |
| wrangler | `courtpy.rules` | courtpy's rulebooks (`RULEBOOKS`, such as "federal"), which are `amos` rulebooks (`amos.parsers.ParseAll`) of the CSV files of rules, and `register_rulebooks`, which makes rulebooks of a study's own folders of rules. |
| wrangler | `courtpy.parsers` | `Parser` and `parse`, which turn saved cases into a table, and the `parse_all` technique (`ParseAll`), which parses loaded cases again from their kept text. |
| wrangler | `courtpy.coders` | The coders, which are `amos` techniques (including `tidy_cases`, which gives columns with missing values the right types), and `code`, which applies them. |
| wrangler | `courtpy.shapers` | `cases_to_dockets` and `dockets_to_cases`, which make a row for each docket number of each case and make cases of them again, `cases_to_courts`, `cases_to_case_types`, and `cases_to_party_types`, which summarize cases by court, case type, and party type, and `summarize`, which they share with `cases_to_judges`. |
| wrangler | `courtpy.loaders` | The loaders, which are `amos` techniques that collect, parse, and code cases in a project, and `ReferenceLoader`, the base of the techniques that load other tables (see [Reference tables](#reference-tables)). |
| artist | `courtpy.plots` | The plots, which are `amos` plots: `court_rates`, `cases_over_time`, `issues_over_time`, `panel_composition`, `lower_court_rates`, `trends_by_administration`, and `judge_network` (see [Figures and checks](#figures-and-checks)). |
| critic | `courtpy.audits` | The evaluators that check court data: `audit_random_assignment`, `audit_parsing`, `audit_coverage`, and `validate_coding`. |
| critic | `courtpy.inferers` | `panel_effects`, which estimates the effect of a judge's colleagues on the judge's vote. |
| references | `courtpy.judges` | `Roster`, which matches the names in opinions to judges (from a roster that fjc-biographies makes), and the `add_biography`, `add_jcs`, `add_circuit`, `code_panels`, `cases_to_votes`, `dockets_to_votes`, `votes_to_cases`, `cases_to_judges`, `load_roster`, and `download_biographies` techniques. |
| references | `courtpy.politics` | `build_table`, which makes a table of each year's political context from the sources' current files, `justices`, which returns each justice's Martin-Quinn and Judicial Common Space scores, the tables of date ranges `executives`, `legislatures`, and `high_courts`, and the `add_executive`, `add_legislature`, `add_high_court`, `load_politics`, and `download_politics` techniques. |
| references | `courtpy.courts` | `court_table` and `federal_courts`, the tables of courts in "instructions/{jurisdiction}/courts.csv", `court_labels`, which labels each case's court for tables and plots, and `circuits`, which finds the circuit of each case. |
| references | `courtpy.scores` | The `add_judge_scores` and `add_court_scores` techniques, which add scores of judges and courts from training data. |
| references | `courtpy.jcs` | `medians`, which loads the Judicial Common Space medians of each year, and `download`, which downloads the published scores with judicial-common-space, and the `download_jcs` technique. |
| references | `courtpy.scdb` | `cases` and `votes`, which load the Supreme Court Database, and the `add_scdb`, `load_scdb`, and `download_scdb` techniques. |
| references | `courtpy.fjc_idb` | `appeals` and `download`, which load and download the Federal Judicial Center's Integrated Database with fjc-idb, and the `add_idb`, `load_idb`, and `download_idb` techniques. |
| core | `courtpy.datasets` | `Cases`, `Dockets`, `Votes`, `Judges`, `Courts`, `CaseTypes`, and `PartyTypes`, the kinds of `amos.Dataset` that courtpy makes, which can be saved and loaded whole. |
| core | `courtpy.cases` | `Case`, and helpers for their columns (`split_cell`, `column_as_flags`, `flags_as_numbers`, `select_whole_cases`, and `require_columns`). |
| core | `courtpy.secrets` | Storing and finding the CourtListener API key. |
| core | `courtpy.options` | Defaults that a project can change before they are used. |

## Saved cases

Both ways of collecting CourtListener cases save each case as a JSON file named
for its cluster id, in a folder named for its court. Its keys are:

| Key | Contents |
| --- | --- |
| `source` | "courtlistener". |
| `court` | The court's `id`, `full_name`, `short_name`, `citation_string`, and `jurisdiction`. |
| `cluster` | CourtListener's opinion cluster: the case name, date filed, judges, attorneys, disposition, precedential status, and so on. |
| `docket` | CourtListener's whole docket (the docket number, the dates it was filed, argued, and terminated, the court appealed from, the PACER case id, the type of appeal, and so on, without the fields in `options._DOCKET_SKIPPED`), from the bulk data, or from the API if "dockets" was asked for. Otherwise `null`. |
| `citations` | The case's citations as text, such as "950 F.3d 12". |
| `opinions` | Each opinion: its type (such as "010combined" or "040dissent"), author, and one field of text (the first of `options._TEXT_FIELDS` that is not blank, which CourtListener recommends be "html_with_citations"). |
| `bulk_date` | For cases from the bulk data, the date of the files. |

Lexis-Nexis cases are text files, one for each case. `courtpy.lexis.split`
divides Lexis-Nexis downloads of many cases into such files and removes
clutter such as star paging.

## Parsing

`courtpy.parse` (or a `Parser`) turns each saved case into a row in three
stages:

1. A reader makes a `Case` with sections of text and `metadata`. CourtListener
   sections come from its data (see the table of sections in [Writing
   Rules](rules.md)); a Lexis-Nexis case has one section, "text".
2. For Lexis-Nexis, the "lexis_nexis" rules divide the text into the header and
   the opinions and find each part of the header.
3. Every section except those whose names end in "_lines" is collapsed onto one
   line, and the rules are applied: the source's header rules (its `header`,
   such as "lexis_nexis_header", which find the court and the agencies with
   the jurisdiction's "courts.csv" and "agencies.csv") and "general" always,
   and then the rulebooks that are named ("federal" by default).

The row starts with the case's `metadata`, which is used instead of anything
the rules find with the same name (unless the metadata is missing). A few
columns are then added: `author` (the first of `authors`), `panel_size`,
`concurrences`, `dissents`, and `word_count`. The text of the cases'
sections (such as `party`, `history`, `judges`, and `opinion`) is not kept
unless `keep_text` is true, because it would make the table very large.

With the text kept, the `parse_all` technique parses the cases again without
reading the saved files, as after a change to the rules. Each case gets its
source's header rules (by its `source` column), "general", and the
rulebooks in its "rulebooks" parameter ("federal" unless it is set). A value
that the rules find replaces the table's, and where they find nothing, the
table's is kept. Given "rules", `parse_all` is `amos`'s, which it replaces in
the `amos` library, so settings written for `amos` still work.

```toml
[wrangler]
techniques = "load_court_listener, parse_all, drop_text_columns"

[load_court_listener_parameters]
keep_text = true

[parse_all_parameters]
rulebooks = "federal, deference.csv"
```

Parsing a large set of cases takes a while. Pass `workers` (the number of
processes) to `parse` to use more of your computer.

## The case table

The table is labeled by "case_id": the CourtListener cluster id, or the name of
the Lexis-Nexis file. Flags are booleans, counts are integers, and matches and
names are lists. Columns of booleans or whole numbers that are missing for
some cases (such as `published` or `year`) have the "boolean" and "Int64"
types, which allow missing values.

`Cases.save` saves the whole dataset in a joblib file (with its label,
history, and anything techniques have added), as the `save_data` technique of
`amos` does, and its data as a table beside it: a CSV, parquet, or Excel
file, named by the path's extension. Lists are written as text, separated by
"; ", as the rules write several values. `Cases.load` loads either file: the
joblib file as it was, or the table, labeled by "case_id" again and with the
types that allow missing values. Every kind of courtpy dataset (`Votes`,
`Judges`, and so on) saves and loads in the same way.

## Coders

The coders are `amos` techniques, so they can be named in the settings of any
`amos` worker, and they record what they did in the dataset's `history`.
`code_parties`, `code_case_type`, `code_outcome`, and `tidy_cases` are
mungers (`amos.Munger`), which change and add columns without adding or removing rows, so the history
lists the columns that each one changed and created. `drop_text_columns` is a cleaner
(`amos.Cleaner`), which removes columns. They use the columns made by the
federal rules.

| Coder | Adds |
| --- | --- |
| `code_parties` | Completes the parties' roles from their opposites (if one party is an appellant, the other is an appellee), and adds `party1_appealing`, `party1_defending`, and the same for `party2`. |
| `code_case_type` | `type_criminal` (the United States is a party and there is a sign of a criminal case), and each party's role in the case: `party1_prosecution`, `party1_criminal_defendant`, `party1_civil_plaintiff`, and `party1_civil_defendant` (and the same for `party2`). |
| `code_outcome` | `outcome_reversal` (from the header's disposition, or else from the decision that the opinion states, or else from the opinion's words anywhere), `outcome_party1_won` and `outcome_party2_won`, the winner by side (`outcome_criminal_defendant_won`, `outcome_prosecution_won`, `outcome_civil_plaintiff_won`, and `outcome_civil_defendant_won`), and `appeal_by_defendant`. Outcomes that cannot be known are missing. |
| `drop_text_columns` | Removes columns of text and lists (such as names and dates), which models cannot use. Its `keep` parameter names columns to keep. |
| `tidy_cases` | Gives columns of booleans and whole numbers with missing values the "boolean" and "Int64" types, which allow them. Tables that courtpy parses or loads are tidied already, so it is for tables made or changed in other ways. |

To write your own, subclass `amos.Munger` and write `munge` (or subclass
`amos.Cleaner` and write `clean` for a coder that removes rows or columns,
`amos.Merger` and write `match` for one that adds the columns of another
table, or `amos.Shaper` and write `shape` for one that changes what a row
is). It is added to the library as soon as it is defined, so it can be named
in settings:

```python
import dataclasses

import amos


@dataclasses.dataclass
class CodeLongOpinion(amos.Munger):
    """Flags opinions longer than a number of words."""

    def munge(self, data, words = 5000, **kwargs):
        data["long_opinion"] = data["word_count"] > words
        return data
```

## Judges and panels

The federal rules find the names of each case's judges as the opinion writes
them (`panel_judges`, `authors`, `concurring`, and `dissenting`), such as
"LYNCH; HOWARD; THOMPSON". `courtpy.judges` matches those names to people, with a roster that
[fjc-biographies](https://github.com/WithPrecedent/fjc_biographies) makes from
the Federal Judicial Center's
[Biographical Directory of Article III Federal Judges](https://www.fjc.gov/history/judges/biographical-directory-article-iii-federal-judges-export):

```python
import courtpy

roster = courtpy.judges.Roster.from_fjc()
roster.save()
```

`from_fjc` downloads three files of a few megabytes (federal judicial service,
demographics, and professional careers) with fjc-biographies, into "raw" in
"judges" in courtpy's data folder, unless they were downloaded before
(`update = True` downloads them again, for the judges and changes since). The
roster is fjc-biographies' table with one row for each court that a judge has
served on, with the president who made the appointment and that president's
party, the American Bar Association's rating, the Senate's vote, the judge's
sex, race or ethnicity, and year of birth, the judge's career and flags for
it, and the two columns that courtpy adds to find judges, `aliases` and
`court_num` (see `courtpy.judges.build_roster` for the columns). `save` writes it as
"roster.csv" in "judges" in courtpy's data folder, outside of any project,
where the techniques below look for it. Their `roster` parameter names another.

The roster is a CSV file, so you can change it in a spreadsheet:

* Add a judge, or another name that opinions use for a judge (as "First
  Middle Last" in the `aliases` column, with semicolons between names).
* Add a column of your own, such as a score of each judge's ideology (or pass
  `scores`, a table with the judges' `nid` numbers, to `from_fjc`, or
  `jcs = True` for the judges' Judicial Common Space scores and
  `martin_quinn = True` for the justices' Martin-Quinn scores; see
  [below](#the-judicial-common-space)). Every column of numbers or booleans
  that does not identify or date a judge's service is an attribute of the
  judge, which the techniques use.
* Change how careers are coded with rules of your own (the `rulebook`
  argument). The built-in rules are fjc-biographies'
  [`judges.csv`](https://github.com/WithPrecedent/fjc_biographies/blob/main/src/fjc_biographies/instructions/judges.csv).

A name is matched by how much of a judge's name it gives, from the most to
the least (see `courtpy.judges.name_forms`):

1. A full name: any of the ways that fjc-biographies writes the judge's name
   (the roster's `name_...` columns, such as "Sandra Lea Lynch", "Sandra L.
   Lynch", and "Sandra Lynch", each with or without a suffix), or one of the
   judge's `aliases`.
2. Initials and the last name: "S. Lynch", "S. L. Lynch", "S.L. Lynch", or
   "S. Lea Lynch", or the middle and last names ("Lea Lynch", for a judge who
   goes by a middle name).
3. The last name alone (with any suffix), which is how opinions usually name
   judges.

Only judges who were serving in the case's year, or had left their court no
more than two years before (`options._JUDGE_GRACE`), are considered, and the
first of these ways that fits any of them is used. The judges it fits are then
narrowed by the case's court: to a judge of that court, or else to a judge of a
district court in its circuit (who may sit by designation), or else to a judge
of any other court, such as a court of appeals or district court of another
circuit (who may sit by designation). Rather than guess, a name that fits more
than one judge at that step is not matched (which is why opinions add
initials, as in "M. SMITH" and "N.R. SMITH"), and neither is a name on a case
of a court that has no judges in the roster, such as a bankruptcy appellate
panel.

Cases and judges are different things: a case table has a row for each case,
and a roster a row for each court that each judge has served on. `amos`
joins such tables with
[mergers](https://WithPrecedent.github.io/amos/advanced/#merging-data), which
add the columns of another table to the rows that they match without ever
adding or losing a row, and
[shapers](https://WithPrecedent.github.io/amos/advanced/#reshaping-data),
which change what a row is. courtpy's techniques for judges are built
from them:

| Technique | Adds |
| --- | --- |
| `add_biography` | A merger. Each row names one judge (in the column that its `name` parameter names, which is "judge" unless another is set), and gets the columns of that judge's row of the roster, with "judge_" (or another `prefix`) before their names: every attribute, and `age`, `senior`, `designated` (sitting on a court other than the judge's own), and `district_judge`, which depend on the case's year and court. All are numbers (1 and 0 for true and false). Its `columns` parameter names the columns to add, which can be any others of the roster too (such as `judge`, the judge's name, or `president`), and `indicator` names a column that says whether each judge was found. In `Cases` without a `name`, each case names the judges in `panel_judges`, and the columns are numbered by each judge's seat: `judge_name1`, `judge_nid1`, `judge_party1`, and so on for the first judge, `judge_name2` and the rest for the second. Its `lookup` parameter can be a function (of a judge's name, the case's court, and its year) that takes the place of the roster. |
| `add_jcs` | A merger. `add_biography` with `jcs` as its only column (`judge_jcs`, or `judge_jcs1` and so on in `Cases`), which needs a roster made with `jcs = True`. |
| `add_circuit` | A merger. The makeup of the active (not senior) judges of each case's circuit on the day it was decided: `circuit_median_party`, `circuit_total_party`, `circuit_median_jcs`, `circuit_total_jcs`, and `circuit_judges` (see [Political context](#political-context)). |
| `code_panels` | A munger. `panel_names` (the judges who were found, as the roster names them), `panel_found` (how many, to compare with `panel_size`), `judge_name1`, `judge_nid1`, `judge_name2`, `judge_nid2`, and so on (each judge who was found, in the panel's order, with the Federal Judicial Center's name and `nid`), `author_name`, `concurring_names`, and `dissenting_names`, and the composition of the panel: `panel_{attribute}` is the mean of each attribute among its judges. So `panel_woman` is the share who are women, and `panel_party` is the mean party of the presidents who appointed them (from -1, all Democrats, to 1, all Republicans). `panel_age`, `panel_senior`, `panel_designated`, and `panel_district_judge` depend on the case's year and court. |
| `cases_to_votes` | A shaper. Replaces the table of cases with one row for each judge on each case, labeled by "vote_id" (such as "4567890-2"): the case's columns, `case_id`, `judge`, `judge_nid`, `judge_{attribute}`, `colleagues_{attribute}` (the mean among the other judges of the panel), `judge_author`, `judge_concurred`, `judge_dissented`, and for each outcome of the case, `vote_{outcome}`: the outcome, or its opposite if the judge dissented. So `vote_reversal` is whether the judge voted to reverse. Its `outcomes` parameter names the outcomes (by default, every column that starts with "outcome_"). Like every shaper, it takes `label`, `task`, and `groups` for the table that it makes, and must come before the data is split. |
| `votes_to_cases` | A shaper. Undoes `cases_to_votes`: the rows of each case become one row again, labeled by "case_id", with the case's columns as they were. `judge` and the columns that begin with `judge_`, `colleagues_`, or `vote_` are removed, and each case keeps the other columns of its first row. A case with no judge who was found in the roster has no votes, so it does not come back. Without `label`, a label such as `vote_reversal` becomes the outcome it was made from (`outcome_reversal`), and the groups lose `case_id`. |
| `cases_to_judges` | A shaper. Makes `Judges`, a table with one row for each judge, labeled by "judge_nid": `judge`, `cases` (how many votes; `count` names it, or "none"), and the means of the columns of numbers and booleans, as `group_rows` takes them, so `vote_reversal` is the share of the judge's votes to reverse, `judge_dissented` the share of the judge's cases with a dissent by the judge, and `type_criminal` the share of the judge's cases that are criminal. Nothing about any one case is kept: text (such as `court` or the cases' names) and ids (such as `case_id`) are left out unless its `keep` parameter names them, or its `how` parameter names a summary for them, as in `{"case_id": "list"}`. Given a table of cases, it makes the votes first, with `roster` and `outcomes`. Without `groups`, the table has none, and without `task`, the task is inferred again, since a vote is now a share. |

`code_panels` and `cases_to_votes` do what a wrangler of
`lists_to_rows, add_biography, group_rows` would do: they make a row for
each name that a case lists, find the judge that each name refers to, and
(for `code_panels`) summarize the rows of each case. Use `add_biography`
itself for a table that names one judge in each row. For example, to add what is
known about the author of each opinion to a table of cases:

```ini
[wrangler]
techniques = load_court_listener, add_biography, drop_text_columns

[add_biography_parameters]
name = author
prefix = author_
indicator = author_found
```

The dataset's history records how many rows a merger matched, which is worth
checking (and reporting) every time:

```python
print(project.result.history[-2])
# {'technique': 'add_biography', 'source': '...roster.csv', 'rows': 5212, 'matched': 4980, 'created': ['author_party', ...]}
```

Each of them can be among a loader's "coders", so a vote can be the label of a
study (see [examples/cases_to_votes.ini](https://github.com/WithPrecedent/courtpy/blob/main/examples/cases_to_votes.ini)
and the [recipes](recipes.md)). In Python, `courtpy.judges.vote_table` makes
the same table as `cases_to_votes`, and a `Roster` matches one name at a
time:

```python
row = roster.match("LYNCH", court_num = 1, year = 2020)
print(roster.names([row]), roster.describe(row, court_num = 1, year = 2020))
```

A loader passes its coders no parameters, so as coders they use the saved
roster. To name another, list them as techniques of the wrangler instead
(after the loader), with a section of parameters for each.
`add_biography` takes the roster as its `source`, as every merger takes
its other table, and finds a file that is named there as the project's clerk
finds files: in the current folder, and then in the input folder.
`code_panels`, `cases_to_votes`, and `cases_to_judges` take it as `roster`, whose path is relative to the folder that the study is
run from.

## Political context

Three mergers add who held power on the day each case was decided. Each
matches the case's date ("date_filed", unless `date` names another column)
to a table of date ranges (with "start_date" and "end_date") with the
`merge_ranges` technique of `amos`, so a table of your own with the same
columns (such as a state's governors) can be its `source`. A date on which
one range ends and the next begins (such as the day of an inauguration)
gets the later one.

| Technique | Adds | Table |
| --- | --- | --- |
| `add_executive` | `executive_name` and `executive_ideology` (the president's party: -1 for Democratic and 1 for Republican). | `courtpy.politics.executives`, from "instructions/federal/presidents.csv", where a president can be added. |
| `add_legislature` | `senate_ideology` and `house_ideology`: the median [NOMINATE](https://voteview.com/data) score of the members of each chamber of the Congress then sitting. | `courtpy.politics.legislatures`, from "HSall_members.csv", the ideology of every member of every Congress (Voteview's "Member Ideology" data). |
| `add_high_court` | `high_court_ideology`: the [Martin-Quinn score](https://mqscores.wustl.edu/measures.php) of the median justice in the Supreme Court's term then sitting (October to September). | `courtpy.politics.high_courts`, from "justices.csv", the score of each justice in each term. |

Higher scores are more conservative. The sources' current files (about 6
megabytes) are downloaded the first time, with
[judicial-common-space](https://github.com/WithPrecedent/judicial_common_space),
and kept in "politics" in courtpy's data folder, where that package and
fjc-biographies look for them too.
`courtpy.politics.download(overwrite = True)` downloads them again, for the
terms and votes since. The Martin-Quinn page sometimes refuses automated
requests; then save "justices.csv" from it in a browser and put it in that
folder.

```ini
[wrangler]
techniques = load_court_listener, add_executive, add_legislature, add_high_court, add_circuit, drop_text_columns
```

`add_circuit` adds the makeup of the whole circuit of each case on the day
it was decided (for a district court, the circuit that hears its appeals,
from "instructions/federal/courts.csv"; see `courtpy.courts`). The circuit's
judges are those of its court of appeals in the roster who were active then:
appointed, not yet gone, and not senior, since senior judges do not sit en
banc. It adds `circuit_median_party` and `circuit_total_party` (the median
and sum of the parties of the presidents who appointed them),
`circuit_median_jcs` and `circuit_total_jcs` (of their Judicial Common Space
scores, if the roster was made with `jcs = True`), and `circuit_judges`.

`courtpy.politics.build_table` still makes a table of each year's political
context (`president_party`, `supreme_court_median`, `supreme_court_min`,
`supreme_court_max`, `senate_median`, and `house_median`), which
`load_politics` and `download_politics` load to study the years themselves,
and which the `merge_keys` technique of `amos` can add to cases by "year".

`courtpy.politics.justices` returns the Martin-Quinn score of each justice in
each term, from the same "justices.csv", with the score put on the scale of
the Judicial Common Space by judicial-common-space (`jcs`), for studies of the
Supreme Court (see below).

## The Judicial Common Space

The [Judicial Common Space](https://epstein.wustl.edu/jcs) (Epstein, Martin,
Segal, and Westerland, 2007) puts judges, justices, members of Congress, and
presidents on one scale of ideology, on which higher scores are more
conservative. A judge's score is the NOMINATE score of the judge's home-state
senators of the appointing president's party, or else of the president, and a
justice's is the justice's Martin-Quinn score, put on the same scale.
[judicial-common-space](https://github.com/WithPrecedent/judicial_common_space)
computes the scores from their sources, which courtpy uses in three ways:

| Scores | How courtpy adds them |
| --- | --- |
| Each appointment of a judge or justice | `Roster.from_fjc(jcs = True)` adds `jcs` to the roster, with fjc-biographies. The published scores are of the judges of the courts of appeals and the justices; the computed ones are of district judges too. |
| Each justice in each term | `courtpy.politics.justices` returns `jcs` beside `martin_quinn`, by term and the Supreme Court Database's numbers for the justices. |
| Each year's medians | `courtpy.jcs.medians` reads the published file of medians: `jcs_president`, `jcs_house_median`, `jcs_senate_median`, `jcs_supreme_court_median`, and `jcs_circuit{n}_median` and `jcs_circuit{n}_sd` for each court of appeals (numbered as `court_num` numbers them). |

The scores of judges become an attribute of a roster, so the judge techniques
use them like any other: `code_panels` adds `panel_jcs` (the mean score of
each panel), and `add_biography` and `cases_to_votes` add `judge_jcs` (and
`colleagues_jcs`). The files that they are computed from (Voteview's NOMINATE
scores, the dates of senators' service, Wikipedia's lists of circuit judges'
duty stations, and the justices' Martin-Quinn scores) are downloaded into
courtpy's data folder the first time. `martin_quinn = True` also adds each
appointment to the Supreme Court's Martin-Quinn scores (`mq_first`,
`mq_last`, `mq_mean`, and `mq_terms`); pass the path of a "justices.csv" that
you saved in a browser if the Martin-Quinn page refuses the download:

```python
roster = courtpy.judges.Roster.from_fjc(jcs = True, martin_quinn = True)
roster.save()
```

`medians` has a row for each year, so it can be added to cases by "year" with
the `merge_keys` technique of `amos`, or be a part of `build_table` (`build_table(common_space = True)`), whose
columns already start with "jcs_". judicial-common-space downloads the
published archive of scores (about 100 kilobytes) the first time it is
needed, and keeps its CSV files in "jcs" in courtpy's data folder
(`courtpy.jcs.download(overwrite = True)` downloads it again).

## The Supreme Court Database

The [Supreme Court Database](https://scdb.la.psu.edu) codes every case that
the Supreme Court has decided since its 1946 term: the issue, the direction
of the decision, what the court did with the decision below, which party won,
and how each justice voted. `add_scdb` (a merger) adds its coding to parsed
cases of the Supreme Court, with "scdb_" before the database's names for its
columns:

```ini
[load_court_listener_parameters]
courts = scotus
coders = code_parties, code_case_type, code_outcome, add_scdb
```

A case is matched by the database's id for it, which CourtListener records
for cases of the Supreme Court (the `scdb_id` column), or else by one of its
citations (the `citation` column), such as "347 U.S. 483". Rather than guess,
a case whose citations are those of more than one case of the database (as
short orders on one page of a reporter are) is not matched. The history
records how many cases were matched and the release of the database that was
used.

The latest release is downloaded from the database's
[data page](https://scdb.la.psu.edu/data/) the first time, and kept in "scdb"
in courtpy's data folder (`courtpy.scdb.download(overwrite = True)` looks for
a newer one). As a technique of the wrangler, `add_scdb` takes a merger's
parameters: `source` (a file of the database that you downloaded yourself),
`columns` (such as "issueArea, decisionDirection, partyWinning"), `prefix`,
and `indicator`, and `on`, `other_on`, and `citations` for the columns to
match by. The database's
[online codebook](https://scdb.la.psu.edu/online-codebook/) explains each
variable.

In Python, `courtpy.scdb.cases` returns the database's table with a row for
each case, and `courtpy.scdb.votes` its table with a row for each justice in
each case. The Martin-Quinn and Judicial Common Space scores of
`courtpy.politics.justices` use the database's numbers for the justices, so a
merger adds each justice's scores to each vote:

```python
import amos
import courtpy

votes = amos.mergers.MergeKeys().apply(
    courtpy.scdb.votes(),
    source = courtpy.politics.justices(),
    on = ["term", "justice"])
print(votes.data[["caseName", "justiceName", "vote", "martin_quinn", "jcs"]].head())
print(votes.history[-1]["matched"])
```

## The Federal Judicial Center's Integrated Database

The Federal Judicial Center's [Integrated Database](https://www.fjc.gov/research/idb)
(IDB) has a record of each appeal in the federal courts of appeals since the
2008 fiscal year, taken from the courts' own dockets: the type of appeal, the
parties, the court and judge appealed from, the dates of each step (docketed,
briefed, heard, decided), the judges of the panel and the opinions each
wrote, how the appeal ended, whether the decision was published, and whether
a party was pro se, among much else. It covers the twelve regional circuits,
not the Federal Circuit. courtpy reads it with
[fjc-idb](https://github.com/WithPrecedent/fjc_idb), whose
[codebooks](https://WithPrecedent.github.io/fjc_idb) explain each column.

`add_idb` (a merger) adds the database's record of each appeal, with "idb_"
before fjc-idb's names for the columns. The database has a record for each
docket, and a case that consolidated several appeals has several docket
numbers, so add it to `Dockets` (after `cases_to_dockets`), whose rows each
have one docket number ("docket"), and each appeal gets its own record.
Added to `Cases`, a case gets the record of the first of its docket numbers
that the database has. `dockets_to_cases` makes the dockets cases again
(with the first docket's record), and `dockets_to_votes` makes a row for
each judge on each docket. Use them as techniques of the wrangler, after the
loader:

```ini
[wrangler]
techniques = load_court_listener, cases_to_dockets, add_idb

[add_idb_parameters]
columns = appeal_type, pro_se_party, in_forma_pauperis, appeal_date, judgment_date, notice_to_judgment
indicator = in_idb
```

A case is matched by its circuit (the `court_num` column that the federal
rules make, or else CourtListener's court id in `court`) and its docket
number (`docket_numbers`, or else `docket_number`), so cases from
Lexis-Nexis are matched too. "17-1234-cv", "No. 17-1234", and "17-01234" are
the same docket. A case with several docket numbers (consolidated appeals) is
matched by the first one that the database has. An appeal that was reopened,
or remanded by the Supreme Court, has a record for each time it ended under
the same docket number, so the record whose judgment is nearest the date of
the decision is used, and never the record of an appeal docketed after the
decision. Cases of other courts, and of years before 2008, are not matched.

Without a `source`, the records are those of the years of the cases: from
the year of the earliest decision to the year after the latest, since the
database's years are fiscal years that end on September 30. `start_year` and
`stop_year` set others. The yearly files that are missing are downloaded
from the Federal Judicial Center (about 10 to 20 MB a year) and kept in
"fjc_idb" in courtpy's data folder, in fjc-idb's layout. Set `folder` to use
files you already have, or `download = false` to download nothing.
`district = true` also adds the district court's record of the case that
was appealed (in columns that begin with "idb_district_", which fjc-idb's
`merge_district` finds), from the district courts' files of civil cases and
criminal defendants, which are about 400 MB a year.

Reading the yearly files takes a few seconds a year. To read them once, save
the table and name the file as the `source` (a parquet file, as here, keeps
the types of its columns):

```python
import courtpy

courtpy.fjc_idb.appeals(2008, 2026).to_parquet("data/appeals.parquet")
```

```ini
[add_idb_parameters]
source = appeals.parquet
```

The CSV file that the `fjc-idb` command makes is a `source` too:

```bash
fjc-idb appellate --start-year 2008 --download --data-folder data/fjc_idb
```

In Python, `courtpy.fjc_idb.appeals` returns the database's table of appeals
for a range of years, and `courtpy.fjc_idb.download` downloads the yearly
files that are missing (with `overwrite = True`, the current year's file
again, which the Federal Judicial Center updates during the year). fjc-idb's
own functions (such as `fjc_idb.run` and `fjc_idb.merge_district`) work on
the same folder.

### Comparing a study with the database

`compare_with_idb` (an explorer) asks two questions of a study of the courts
of appeals. Do its variables agree with the database's? And how do the
appeals it lacks differ from the ones it has? It works on `Cases` or
`Dockets`. Cases are compared as dockets (see `cases_to_dockets`), but the
dataset stays as it was, and each docket is matched to its record as
`add_idb` matches it. It takes `add_idb`'s parameters for finding the
database (`source`, `start_year`, `folder`, and so on).

```ini
[explorer]
techniques = compare_with_idb

[compare_with_idb_parameters]
source = appeals.parquet
by = circuit
visualize = true
```

The first table, `tables["compare_with_idb"]`, has a row for each variable
that both have, among the dockets that were matched:

| Variable | The study's column | The database's column |
| --- | --- | --- |
| `criminal` | `type_criminal` | `appeal_type` is a criminal appeal |
| `civil` | `type_civil` | `appeal_type` is not a criminal appeal |
| `reversal` | `outcome_reversal` | `disposition` is reversed (in whole or part) or remanded |
| `published` | `published` | `published` |
| `dissent` | `dissents` (more than 0) | `dissents` (more than 0) |
| `us_appellant` | a party is `united_states` and `appellant` | `us_appellant` |
| `pro_se_appellant` | `pro_se_appellant` | `pro_se_appellant` |
| `prisoner_appeal` | `prisoner_appeal` | `prisoner_appeal` |

A variable whose column the study lacks is left out. The table counts the
dockets with both values ("compared") and those that agree ("matches",
"match_share", and Cohen's "kappa", which discounts the agreement that chance
would give). It also counts the disagreements in each direction:
"data_only" is true in the study and false in the database, and "idb_only"
is the reverse. `variables` picks some of them by name (such as
`variables = criminal, reversal`). In Python, it can also add others, each
as a column of the study and a column of the database:

```python
import courtpy

cases = courtpy.parse("data/courtlistener")
dockets = courtpy.code(cases, ["cases_to_dockets"])
compare = courtpy.fjc_idb.CompareWithIdb()
table = compare.describe(
    dockets, source = "appeals.parquet",
    variables = {"en_banc": ("en_banc", "enbanc")})
```

The second table, `tables["compare_with_idb_missing"]`, starts from the
database, which has every appeal, so the study always lacks some. It keeps
the appeals of the study's circuits that were judged between the study's
first and last decisions. Unless `merits_only = false`, it keeps only those
decided on the merits, since procedural terminations rarely have opinions.
Then, for each circuit (or each district court appealed from, with
`by = district`) and for all of them ("All"), and for each variable of
`report`, it reports:

- "appeals", "in_data", and "coverage": how many appeals there are, how many
  the study has, and the share it has.
- "share_in_data" and "share_missing": the share that are true among the
  appeals the study has and among those it lacks.
- "difference" and "p_value": the first share minus the second, and the
  p value of a two-proportion z test of that difference.

So a positive "difference" in reversals means the study's appeals were
reversed more often than the ones it lacks, as studies of published
opinions usually are.

With `visualize`, `idb_confusion_matrices` draws a confusion matrix for each
variable of the first table. `idb_missing_differences` draws the second
table as a grid of groups and variables, shaded by the difference, with a
star where the p value is below `alpha` (0.05 unless set). The figures are in
`figures` under the tables' names.

## Figures and checks

courtpy's plots, evaluators, and inferer are `amos` techniques for the
"artist" and "critic" stages, so a settings file names them as it names
`amos`'s own. The plots need the packages of the `analysis` extra
(`pip install courtpy[analysis]`); the checks need none.

Courts are labeled with their `feature_name` in "courts.csv" (such as "Tenth
Circuit"), in the order of the table. A rate in a plot is the share of the
cases that have a flag (or the mean of a number), measured from the cases
themselves, so it has no confidence interval; each bar says how many cases
it counts. The column of a rate is the dataset's label unless "column" is
set.

| Technique | Draws or checks | Needs |
| --- | --- | --- |
| `court_rates` | The rate of a column in each court, with the rate of all the courts as a line. | `Cases`. |
| `cases_over_time` | The number of cases of each court in each year, a panel for each court in the data. | `Cases`, with `year`. |
| `issues_over_time` | The number of cases with each issue in "issues" (columns of flags, such as `criminal_firearm` or `type_immigration`) in each court in each year, a panel for each court in the data. | `Cases`, with `year`. |
| `panel_composition` | The rate of a column for each composition of the panel by the parties of the presidents who appointed its judges ("DDD" to "RRR"), split by "by" (such as `type_criminal`). | `Cases`, after `add_biography` or `code_panels`. |
| `lower_court_rates` | The rate of a column for each court below (`lower_court_name`), grouped by the court that reviewed it. | `Cases`. |
| `trends_by_administration` | The yearly rate of a column in each court, with the terms of Democratic and Republican presidents shaded. | `Cases`, with `year`. |
| `judge_network` | The judges, joined by how often they sat together (or, with "dissents", how often one dissented from the other), colored by party. | `Votes`. |
| `audit_random_assignment` | Whether the traits of cases that a panel cannot change (such as `type_criminal` and `review_agency`) are balanced across panel compositions within each court and year, with a permutation test. | `Cases`, after `add_biography` or `code_panels`. |
| `audit_parsing` | How many cases lack a court, a court below, judges, a year, or an outcome, have panels of another size, or have a header's disposition that disagrees with the opinion's stated decision, with examples to read. | `Cases`. |
| `audit_coverage` | The cases of each court and year against the appeals that the Integrated Database records, and the share that the data has (and of published opinions). | `Cases`, and the database (downloaded, or "source"). |
| `validate_coding` | How often courtpy's coding agrees with another source's ("pairs", such as `published = idb_published` after `add_idb`), with Cohen's kappa. | `Cases`. |
| `panel_effects` | The effect of the colleagues' party on a judge's vote, with the judge's party and their product, a fixed effect for each court and year, standard errors clustered by case, and a randomization test that reassigns colleagues within each court and year. | `Votes`. |

```toml
[study_project]
study_workers = "wrangler, artist, critic"

[wrangler]
techniques = "load_court_listener, add_biography"

[artist]
techniques = "court_rates, cases_over_time, issues_over_time, panel_composition"

[issues_over_time_parameters]
issues = "criminal_firearm, type_immigration"

[panel_composition_parameters]
by = "type_criminal"

[critic]
techniques = "audit_parsing, audit_random_assignment"
```

## Loaders

`amos` loads a project's data with loaders, the first techniques of the
wrangler, so a project with a loader needs no `item`. courtpy's loaders are a
genre of `amos` loaders, `CaseLoader`. `load_court_listener` and
`load_lexis_nexis` are `SourceLoader`s, which download cases (if asked) and
parse a folder of them; a study can add its own sources, ways to download,
and loaders (see [Building a Study](studies.md#sources-of-your-own)):

| Loader | Source | Does |
| --- | --- | --- |
| `load_court_listener` | A folder of saved CourtListener cases. Defaults to "courtlistener". | Downloads cases into the folder (if "download" is set), parses them, and codes them. |
| `load_lexis_nexis` | A folder of Lexis-Nexis cases, one per text file. Defaults to "lexis_nexis". | Divides any "batches" into the folder, parses the cases, and codes them. |
| `load_cases` | A dataset saved by `Cases.save` (or `courtpy parse`): its joblib file or its table. | Loads the dataset (a joblib file of `Votes` is `Votes` again), or the table as `Cases`, with its types. It applies no coders unless "coders" names some. |

Their parameters go in a "{loader}_parameters" section of the settings:

| Parameter | Loaders | Meaning |
| --- | --- | --- |
| `source` | all | The folder (or, for `load_cases`, the file) to load. |
| `coders` | all | Techniques to apply after parsing. Defaults to "code_parties, code_case_type, code_outcome" ("none" for `load_cases`). Use "none" for none. |
| `save` | all | File to save the coded table to (".csv", ".parquet", or ".xlsx"), with the whole dataset beside it in a joblib file of the same name. |
| `reuse` | all | Whether to load the saved dataset, if there is one, instead of collecting, parsing, and coding again. |
| `label`, `task`, `groups` | all | As in `amos`. They default to those in the "general" section. |
| `download` | `load_court_listener` | "bulk" to extract cases from the bulk data, "api" to download them with the API, a way that a study adds, or "none" (the default) to use the cases already in the folder. Any parameter that the loader does not know is an option of the way to download. |
| `courts` | `load_court_listener` | CourtListener court ids (such as "ca1, ca2") or groups (`federal_appellate`, `federal_circuits`, or `scotus`). |
| `start_date`, `end_date` | `load_court_listener` | Dates filed (YYYY-MM-DD). |
| `max_cases`, `overwrite` | `load_court_listener` | Most cases to download, and whether to download cases saved before. |
| `dockets` | `load_court_listener` | For "api", whether to download each case's docket too (one more request per case). |
| `bulk_folder`, `bulk_date`, `stream` | `load_court_listener` | For "bulk", where to keep the bulk files, which date's files to use, and whether to read them from CourtListener without saving them. |
| `batches` | `load_lexis_nexis` | Files (or folders) of many cases to divide into the source folder first. |
| `rulebooks` | `load_court_listener`, `load_lexis_nexis` | Rules to parse with: built-in names ("federal", or any of "citations", "civil", "constitutional", "criminal", and "agencies") or CSV files or folders. The source's header rules and "general" are always applied. Defaults to "federal". |
| `keep_text`, `limit`, `workers` | `load_court_listener`, `load_lexis_nexis` | Whether to keep the opinions' text, most cases to parse, and processes to parse with. |

The loaders work through the project's clerk, as `amos` loaders do. A folder
or file named by a relative path is looked for in the current folder and
then in the clerk's input folder (the "input_folder" of the "files" section),
where downloads save their cases, and "save" is in the clerk's interim folder
("interim_folder"). The label is checked after the coders run, so it can be a
column that a coder makes (such as `outcome_reversal`), and the dataset's
history records the loader and then each coder.

A loader can also be used without a project. `apply` takes the dataset so far,
or `None` to start a new one, and returns an `amos.Dataset`:

```python
dataset = courtpy.loaders.LoadCourtListener().apply(
    None, source = "courtlistener", label = "outcome_reversal")
```

### Reference tables

Some studies are not of cases: of how the justices vote, of the appeals in
the Integrated Database, or of the judges themselves. Reference loaders (a
genre of `amos` loaders, `ReferenceLoader`) start such a study with a table
of reference data. Each "load_" technique loads the files that courtpy keeps
outside of projects (or a file named as its `source`), downloading them first
if they are missing, and each "download_" technique downloads them into the
folder named as its `source` (or courtpy's own), again if `refresh` is true,
and then loads them. Without a `source`, the history records it as "current".

| Loader | Table | Other parameters |
| --- | --- | --- |
| `load_roster` | A saved roster of judges (see `courtpy.judges.Roster`). | |
| `download_biographies` | A roster made from the Federal Judicial Center's files. | `refresh`, `jcs`, `martin_quinn`, `scores`, `rulebook`, and `save` (true, or a path, to save the roster). |
| `load_scdb`, `download_scdb` | The Supreme Court Database's cases or, with `kind = votes`, each justice's vote in each case. | `kind`, and `refresh` and `session` to download. |
| `load_idb`, `download_idb` | The Integrated Database's appeals. | `start_year`, `stop_year`, `district`, `fix_city_spellings`, and `download` (to load) or `refresh` (to download). |
| `load_politics`, `download_politics` | The political context of each year (see `courtpy.politics.build_table`), or a saved table of years. | `supreme_court`, `congress`, `score`, and `common_space`, and `refresh` and `session` to download. |
| `download_jcs` | The Judicial Common Space medians of each year or, with `kind`, the scores of each judge or justice. | `kind`, `refresh`, and `session`. |

```ini
[wrangler]
techniques = load_scdb

[load_scdb_parameters]
kind = votes
label = majority
```

To add a reference table's columns to cases instead, use its merger
(`add_biography`, `add_scdb`, `add_idb`, or `add_executive`).

## The CourtListener API

A free CourtListener account can make 5 requests a minute, 50 an hour, and 125
a day (as of 2026); members have more. `CourtListener` asks for 20 cases (one
page of opinion clusters) in one request and their opinions in one more, so a
free account can download roughly a thousand cases a day.

* Requests are at least `min_interval` seconds apart (1 by default).
* When CourtListener asks for a pause (an HTTP 429 response), the client waits
  as long as it is asked, up to `max_wait` seconds (an hour by default), which
  rides out the minute and hour limits. A longer pause (the daily limit)
  raises a `RateLimitError`.
* The place in each court's list of cases is saved in a ".courtpy" folder
  inside the download folder, so running the same download again resumes it.
  Running a finished download again takes one request for each court and
  saves any cases added since.
* `download_case` downloads one case by its cluster id.

## The bulk data

CourtListener publishes its whole database every three months, at
<https://com-courtlistener-storage.s3-us-west-2.amazonaws.com/list.html?prefix=bulk-data/>.
`BulkData.extract` reads five files, in this order: courts, dockets (about 5 GB),
opinion clusters (about 2.5 GB), citations, and opinions (about 55 GB). It keeps
only the cases of the courts and dates asked for, so it needs little memory,
but reading the opinions file takes hours. The dockets file is read a second
time after the opinion clusters, to save each case with its whole docket.
Extract every court and year you may need at once.

The files are read with amos's `read_chunks`, which decompresses and parses
them on every core and drops the rows of other courts and cases before they
become Python objects. `BulkData.chunks` yields those chunks as tables, with
the columns and values to keep, for studies that need other parts of the
bulk data.

By default, the files are downloaded (resuming an interrupted download) and
kept in "bulk" in courtpy's data folder, outside of any project, so they can
be used again. Set `folder` to keep them elsewhere, `date` to use older files
(`available()` lists the dates), or `stream = True` to read them from
CourtListener without saving them.

## Secrets and folders

### Keeping your API key secret

Your API key, if you use one, is never written in a project's files or in
`courtpy` itself. Store it once:

```sh
courtpy key set
```

That asks for the key (without showing it) and stores it in your computer's
keyring (Windows Credential Manager, the macOS Keychain, or the Secret Service
on Linux), or, if there is none, in a private file in your user folder (the
secrets file, at `courtpy.secrets.secrets_path()`). From then on, `courtpy`
finds it whenever it is needed. `courtpy key show` says where it was found
(with most of it hidden), and `courtpy key delete` removes it.

`courtpy` looks for the key in this order: the `COURTLISTENER_API_KEY`
environment variable, the keyring, the secrets file, and a `.env` file in the
current folder (with a line such as `COURTLISTENER_API_KEY=your-key`; keep
such a file out of version control). In Python, use
`courtpy.secrets.set_api_key(...)` and `courtpy.secrets.get_api_key()`.
`set_api_key` stores the key in the keyring if there is one and in the secrets
file otherwise (or where its `store` argument says).

### Folders

| Folder | Holds | Default | Changed with |
| --- | --- | --- | --- |
| Configuration | The secrets file. | "courtpy" in `%APPDATA%` (Windows) or `~/.config` | `COURTPY_CONFIG_DIR` |
| Data | Bulk data files, the roster of judges and the files it is made from, and the files of Martin-Quinn scores, NOMINATE scores, Judicial Common Space scores, and the Supreme Court Database. | "courts" in the data folder of the `amos` workspace (`courtpy.options._DATA_SUBFOLDER`), where every `amos` project keeps its data: with projects in "projects/code", it is "projects/data/courts". The workspace is the folder named by `AMOS_WORKSPACE`, or else the folder that holds the nearest "code" folder above the current folder | `COURTPY_DATA_DIR` |

## Options

`courtpy.options` holds defaults as module-level constants, which a project can
change before they are used. For example, to wait at least two seconds between
requests to the API, or to add a group of courts:

```python
import courtpy

courtpy.options._MIN_INTERVAL = 2.0
courtpy.options._COURT_GROUPS["new_england"] = ("ca1", "mad", "nhd", "med", "rid")
```

## Errors you may see

| Error | Cause |
| --- | --- |
| `MissingAPIKeyError: no CourtListener API key was found` | The API needs a key. Run `courtpy key set`, or use the bulk data. |
| `CourtListenerError: CourtListener rejected the request (401)` | The key is wrong. Check it with `courtpy key show`. |
| `RateLimitError: CourtListener asked courtpy to wait ... hours` | The account's daily limit was reached. Run the same download again later. |
| `ValueError: ... row N: the pattern ... is not valid` | A rule's regular expression has an error. `courtpy rules file.csv` checks a file. |
| `KeyError: 'code_outcome' needs the columns [...]` | A coder needs columns made by the federal rules. |
| `ValueError: no courtlistener cases were found in ...` | The loader's source folder has no saved cases. Set "download" or "source". |
| `ModuleNotFoundError: No module named 'statsmodels'` | `logit_sm` (and the other statsmodels models) need statsmodels. Use `logit` for scikit-learn's logistic regression, or `pip install amos[statistics]`. |
| `KeyError: the label 'outcome_reversal' is not a column of the data` | The label is made by a coder that was not run. Check the "coders" setting. |
| `FileNotFoundError: there is no roster of judges at ...` | `add_biography`, `code_panels`, and `cases_to_votes` need a roster. Make and save one with `courtpy.judges.Roster.from_fjc().save()`, or name one with the "source" parameter of `add_biography` or the "roster" parameter of the others. |
| `KeyError: 'add_executive' needs the columns ['date_filed']` | `add_executive`, `add_legislature`, `add_high_court`, and `add_circuit` match each case's date. Set their "date" to the column that has it. |
| `TypeError: 'merge_keys' cannot match 'year', which is text in the data, with 'year', which is numbers in the other table` | The cases' years are not numbers (as they are in a table that was saved and loaded without `courtpy.Cases.load`). Load the table with `Cases.load` (or `load_cases`), or change the column with a cleaner such as `clean_numbers`. |
| `KeyError: 'add_scdb' needs the column 'scdb_id' ... or 'citation'` | `add_scdb` matches cases by the Supreme Court Database's ids, which CourtListener records for cases of the Supreme Court, or by their citations. Set its "on" or "citations" to the columns that have them. |
| `ValueError: '...' changes the rows of the data, so it must come before the data is split` | `cases_to_votes` is a shaper, which came after a splitter. Put it in the wrangler (or among a loader's coders). |
| `ImportError: cannot import 'fairlearn.metrics...'` | A study has "groups" (such as `case_id`, for judges' votes), so the scorecard compares the model across them, which needs fairlearn. Name the scorecard's "metrics", or `pip install amos[fairness]`. |
