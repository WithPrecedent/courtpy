# Recipes

Short answers to common jobs. See the [tutorial](tutorial.md) for the basics
and the [advanced user guide](advanced.md) for every setting.

## Study only criminal appeals

`outcome_criminal_defendant_won` is missing for civil cases, so keep only the
criminal cases (and those whose winner is known) before using it as a label.
This study loads a table of cases saved earlier (with `courtpy parse` or
`Cases.save`):

```ini
[general]
seed = 43
label = outcome_criminal_defendant_won

[criminal_project]
criminal_workers = wrangler, analyst, critic

[wrangler]
techniques = load_cases, filter_rows, drop_missing, drop_text_columns

[load_cases_parameters]
source = cases.csv

[filter_rows_parameters]
query = type_criminal

[drop_missing_parameters]
columns = outcome_criminal_defendant_won

[analyst]
techniques = stratified, logit

[critic]
techniques = scorecard
```

Columns that record the outcome itself (such as `outcome_reversal`,
`disposition_reverse`, and `opinion_reverse`) would give the answer away, so
drop them (with `drop_columns`) or name the features to keep (with
`keep_columns`), as in the example study.

## Study how judges vote

To study judges rather than cases, first make a roster of judges, once (see
[Judges and panels](advanced.md#judges-and-panels)):

```python
import courtpy

courtpy.judges.Roster.from_fjc().save()
```

Then add `code_panels` and `cases_to_votes` to the loader's coders.
`cases_to_votes` is a shaper, which changes what a row is: the table has one row for each
judge on each case, and `vote_reversal` (whether the judge voted to reverse)
can be the label. This is the heart of
[examples/cases_to_votes.ini](https://github.com/WithPrecedent/courtpy/blob/main/examples/cases_to_votes.ini):

```ini
[general]
seed = 43
label = vote_reversal
groups = case_id

[votes_project]
votes_workers = wrangler, analyst, critic

[wrangler]
techniques = load_court_listener, filter_rows, keep_columns, drop_missing

[load_court_listener_parameters]
source = courtlistener
coders = code_parties, code_case_type, code_outcome, code_panels, add_executive, cases_to_votes

[filter_rows_parameters]
query = type_criminal and panel_size == 3 and panel_found == 3

[keep_columns_parameters]
columns = court_num, year, executive_ideology, judge_party, judge_woman, judge_age, colleagues_party, colleagues_woman

[analyst]
techniques = group_split, logit

[critic]
techniques = scorecard

[scorecard_parameters]
metrics = roc_auc, accuracy, balanced_accuracy, f1
```

* The query keeps criminal appeals decided by three judges (so not by a court
  sitting en banc) who were all found in the roster. Compare `panel_found`
  with `panel_size` to see how many panels have a judge who was not found.
* The judges of a case decide it together, so `groups = case_id` and
  `group_split` keep them together when the data is split, and a model is
  tested on cases that it has not seen.
* A scorecard compares a model across a study's groups unless its metrics
  are named. Here the groups are cases, so that comparison would mean nothing
  (and it needs the optional fairlearn package).

To study panels instead, use `code_panels` without `cases_to_votes`. The
table keeps one row for each case, the label can stay `outcome_reversal`, and
the composition of each panel (such as `panel_party` and `panel_woman`) can
be among the features. `votes_to_cases` turns a table of votes back into a
table of cases, so columns added to the votes can be studied by case.

To study the judges themselves, add `cases_to_judges` after
`cases_to_votes` (or in its place, with the roster as its `roster`). It
makes one row for each judge, with how many cases the judge decided
(`cases`), the judge's attributes, and the shares of the judge's votes, such
as `vote_reversal` (the share to reverse) and `judge_dissented` (the share
of the judge's cases with a dissent by the judge):

```ini
[general]
seed = 43
label = judge_dissented

[load_court_listener_parameters]
source = courtlistener
coders = code_parties, code_case_type, code_outcome, cases_to_votes, cases_to_judges
```

## Add what is known about each opinion's author

`add_biography` is a merger: it adds the columns of the roster's row for
the judge that each row names, and never adds or loses a row. To study whether
the author of an opinion matters, name the column with the author's name and
a prefix for the new columns:

```ini
[wrangler]
techniques = load_court_listener, add_biography, filter_rows, keep_columns

[add_biography_parameters]
name = author
prefix = author_
indicator = author_found

[filter_rows_parameters]
query = type_criminal and author_found

[keep_columns_parameters]
columns = outcome_reversal, court_num, year, author_party, author_woman, author_age, author_prosecutor
```

The history of the study's result records how many cases' authors were
found (its "matched"), which belongs in a description of the data.

## Add the politics of the day

`add_executive` adds the president on the day each case was decided and the
president's party, `add_legislature` the median NOMINATE score of each
chamber of the Congress then sitting, `add_high_court` the Martin-Quinn
score of the Supreme Court's median justice in the term then sitting, and
`add_circuit` the makeup of the whole circuit's active judges (courtpy
downloads the scores from their sources the first time):

```ini
[wrangler]
techniques = load_court_listener, add_executive, add_legislature, add_high_court, add_circuit, drop_text_columns
```

Each matches the case's date ("date_filed") to a table of date ranges, so a
table of your own with the same columns (such as a state's governors) can
be its `source`. See [Political context](advanced.md#political-context).

## Score judges and courts from training data

`cases_to_judges` and `cases_to_courts` summarize the cases of a training
set, one row for each judge or court. Save the table, and `add_judge_scores`
and `add_court_scores` add its columns to the cases of a test set, matched by
the judge's or court's number:

```python
import courtpy

training = courtpy.Cases.load("training.csv")
judges = courtpy.code(training, "cases_to_judges")
judges.save("judge_scores.csv")
```

```ini
[wrangler]
techniques = load_cases, code_panels, add_judge_scores

[add_judge_scores_parameters]
source = judge_scores.csv
columns = vote_reversal, judge_dissented
```

In `Cases`, each judge's scores are numbered by the judge's seat
(`judge_score_vote_reversal1`, ...), and `code_panels` (or `add_biography`)
must come first, to find each seat's judge.

## Use the Supreme Court Database's coding

For cases of the Supreme Court, `add_scdb` adds the
[Supreme Court Database](https://scdb.la.psu.edu)'s coding of each case, with
"scdb_" before the database's names for its variables. courtpy downloads the
latest release the first time:

```ini
[general]
label = outcome_reversal

[wrangler]
techniques = load_court_listener, add_scdb, filter_rows, keep_columns

[load_court_listener_parameters]
source = courtlistener
download = bulk
courts = scotus
start_date = 2000-01-01

[add_scdb_parameters]
columns = issueArea, decisionDirection, lcDispositionDirection
indicator = in_scdb

[filter_rows_parameters]
query = in_scdb

[keep_columns_parameters]
columns = outcome_reversal, year, scdb_issueArea, scdb_lcDispositionDirection
```

See [The Supreme Court Database](advanced.md#the-supreme-court-database).

## Add the Federal Judicial Center's record of each appeal

For cases of the courts of appeals, `add_idb` adds the record of each appeal
in the Federal Judicial Center's
[Integrated Database](https://www.fjc.gov/research/idb), which comes from the
courts' dockets: what an opinion does not say, such as whether a party was
pro se and how long the appeal took. The database has a record for each
docket, so `cases_to_dockets` first makes a row for each docket number of
each case (a case that consolidated several appeals has several). courtpy
downloads the years of the cases the first time:

```ini
[general]
label = outcome_reversal
; The dockets of a case are kept together when the data is split.
groups = case_id

[wrangler]
techniques = load_court_listener, cases_to_dockets, add_idb, filter_rows, keep_columns, drop_missing

[load_court_listener_parameters]
source = courtlistener
download = bulk
courts = federal_circuits
start_date = 2015-01-01
end_date = 2019-12-31

[add_idb_parameters]
columns = pro_se_party, notice_to_judgment, criminal_direct_appeal, civil_us_party
indicator = in_idb

[filter_rows_parameters]
query = in_idb

[keep_columns_parameters]
columns = outcome_reversal, year, court_num, idb_pro_se_party, idb_notice_to_judgment, idb_criminal_direct_appeal, idb_civil_us_party
```

`idb_notice_to_judgment` is the number of days from the notice of appeal to
the judgment. See
[The Federal Judicial Center's Integrated Database](advanced.md#the-federal-judicial-centers-integrated-database)
for how cases are matched and how to use files you already have.

## Add your own variables

Write the rules in a CSV file (see [Writing Rules](rules.md)) and parse with
the federal rules and yours:

```text
column,name,kind,pattern,value,flags,separator,note
opinion,cites_chevron,flags,Chevron(?: U\.S\.A\.)?(?:,)? Inc\. v\. Natural Res,,ignorecase,,Chevron deference
opinion,cites_loper_bright,flags,Loper Bright,,ignorecase,,
opinion,chevron_mentions,counts,\bChevron\b,,,,
```

```python
table = courtpy.parse("courtlistener", rulebooks = ["federal", "deference.csv"])
```

or, in a settings file, `rulebooks = federal, deference.csv` in the loader's
parameters (such as the "load_court_listener_parameters" section). Check the
file first with `courtpy rules deference.csv`.

For a quick look without a file of rules, keep the opinions' text and search
it with `amos`'s parsers, such as `parse_flags` and `parse_counts`, after the
loader. `drop_text_columns` then removes the text before the analysis:

```toml
[wrangler]
techniques = "load_court_listener, parse_flags, parse_counts, drop_text_columns"

[load_court_listener_parameters]
keep_text = true

[parse_flags_parameters]
column = "opinion"
name = "cites_loper_bright"
pattern = 'Loper Bright'
flags = "ignorecase"

[parse_counts_parameters]
column = "opinion"
name = "chevron_mentions"
pattern = '\bChevron\b'
```

courtpy's rulebooks are techniques too (`parse_federal`, `parse_civil`,
`parse_criminal`, and so on), which search a dataset's sections of text in
the same way.

## Turn names and citations into lists or columns

The judges, citations, and docket numbers of a case are text, with "; "
between them (such as "LYNCH; HOWARD; THOMPSON"). The `split_values` coder
turns them into lists, or into a column for each (`panel_judges_1`,
`panel_judges_2`, and so on):

```python
listed = courtpy.code(table, ["split_values"]).data
wide = courtpy.code(
    table, ["split_values"],
    parameters = {"split_values": {"columns": "panel_judges", "into": "columns"}}).data
```

To make a row for each judge instead, use `amos`'s `lists_to_rows` with
`separator = ";"`.

## Keep a set of recent cases up to date

A download with the API saves its place, and running it again saves only the
cases added since. Run the same command each week (for example, with Windows
Task Scheduler or cron):

```sh
courtpy download api --courts federal_circuits --start 2026-01-01 --folder courtlistener
```

## Parse cases downloaded from Lexis-Nexis

```sh
courtpy split downloads --folder lexis_nexis
courtpy parse lexis_nexis --source lexis_nexis --output lexis_cases.csv
```

The second command also codes the parties, case types, and outcomes (add
`--no-code` to skip that).

## Look at what the rules found in one case

```python
import courtpy

case = courtpy.courtlistener.read_case("courtlistener/ca1/4567890.json")
print(case.sections["judges"])
parser = courtpy.Parser.create("federal", keep_text = True)
row = parser.parse(case)
print(row["panel_judges"], row["disposition"], row["disposition_reverse"])
```

## Use the table in Stata or R

The CSV file that `Cases.save` writes can be read by Stata
(`import delimited cases.csv`), R (`read.csv("cases.csv")`), and most other
programs. Lists (such as the judges) are written as text, with "; " between
the items.
