# Changelog

All notable changes to this project will be documented in this file.

<!-- insertion marker -->

## Unreleased

* The README shows the courtpy logo (`docs/images/logo.webp`).
* "Keeping your API key secret" moved from the README to the Advanced User
  Guide's "Secrets and folders" section, and the README links to it.
* Every process of courtpy is an `amos`/`chrisjen` technique. The techniques
  are renamed for what they do, and the old names are removed (settings that
  use them must be updated):
  * `merge_judges` (`MergeJudges`) is `merge_biographies`
    (`MergeBiographies`)
  * `code_judges` (`CodeJudges`) is `code_panels` (`CodePanels`)
  * `judge_votes` (`JudgeVotes`) is `reshape_by_votes` (`ReshapeByVotes`),
    and `examples/judge_votes.ini` is `examples/reshape_by_votes.ini`
  * `code_politics` (`CodePolitics`) is `add_politics` (`AddPolitics`)
  * `code_scdb` (`CodeScdb`) is `merge_scdb` (`MergeScdb`)
  * `code_idb` (`CodeIdb`) is `merge_idb` (`MergeIdb`)
* `reshape_by_panel` (`judges.ReshapeByPanel`, an `amos.Shaper`) undoes
  `reshape_by_votes`: the table of votes becomes the table of cases again,
  labeled by "case_id", without the columns about each judge
* `reshape_by_judge` (`judges.ReshapeByJudge`, an `amos.Shaper`) makes a table
  with one row for each judge, labeled by "judge_nid", with the number of the
  judge's votes ("cases"), the judge's attributes, and the means (shares) of
  the other numbers and booleans, as `group_rows` takes them. Given a table of
  cases, it makes the table of votes first
* `tidy_cases` (`coders.TidyCases`, an `amos.Munger`) is `cases.tidy` as a
  technique
* `loaders.ReferenceLoader` is a genre of `amos` loaders that load a table of
  reference data, needing no "source": `load_roster` and
  `download_biographies` (`courtpy.judges`), `load_scdb` and `download_scdb`
  (`courtpy.scdb`), `load_idb` and `download_idb` (`courtpy.fjc_idb`),
  `load_politics` and `download_politics` (`courtpy.politics`), and
  `download_jcs` (`courtpy.jcs`). The "download_" techniques download the
  files first, again if "refresh" is true
* Requires `amos` 0.9.0 or later, and courtpy's rules are `amos` rulebooks.
  The `Rule` and `Rulebook` classes of `courtpy.rules` (and `courtpy.Rule`,
  `courtpy.Rulebook`, `rules.split_names`, and `rules.find_instructions`)
  are removed: `amos.parsers.Rulebook` and `amos.parsers.Rule` take their
  place, and parsing applies each rule to a whole chunk of cases at once.
  * The built-in CSV files are in `amos`'s layout (`column`, `name`, `kind`,
    `pattern`, `value`, `flags`, `separator`, and `note`, with the kinds
    `flags`, `counts`, `category`, `categories`, `match`, `matches`,
    `names`, and `split`). Files in the older layout still work, since
    `amos` reads them.
  * Each rulebook is an `amos.parsers.ParseAll` technique of its own
    (`parse_federal`, `parse_header`, `parse_general`, `parse_citations`,
    `parse_civil`, `parse_constitutional`, `parse_criminal`,
    `parse_agencies`, and `parse_lexis_nexis`), and its name (such as
    "federal") can be a rulebook of `parse_all` or of another rulebook.
  * **Breaking:** columns with several values in a case ("panel_judges",
    "authors", "concurring", "dissenting", "docket_numbers", and the
    "citations_" columns) are text with "; " between the values (such as
    "LYNCH; HOWARD; THOMPSON") rather than lists. A case with none has a
    missing value rather than an empty list. `split_values`
    (`coders.SplitValues`, an `amos.Munger`) turns them into lists or into a
    column for each value ("panel_judges_1", "panel_judges_2", and so on).
    The Lexis-Nexis sections of lines ("dates", "concurring_lines", and
    "dissenting_lines") also separate their lines with "; ", so that no rule
    file has a line break in a cell (which a checkout on Windows made
    "\r\n", failing the tests there).
  * `courtpy rules` lists the columns that the rules search and make.
  * The recipe and test that searched kept text with `amos`'s
    `flag_patterns` and `count_patterns` (removed from `amos`) use
    `parse_flags` and `parse_counts`.
* A loader's label that no coder makes is
  now pending, as in `amos`, instead of raising a `KeyError`: a later
  technique (such as "derive_columns") can still make it
* `coders.code` passes the coders' parameters to `amos` as they are, now that
  `amos.Operation` takes string keys
* Updated to the `snickerdoodle` 0.4.3 template
* The version is read from `__version__` in `src/courtpy/__init__.py` instead
  of being repeated in `pyproject.toml`, and the license is the SPDX
  expression "Apache-2.0" (PEP 639)
* The `ci` Action uploads test coverage to Codecov, tests each Python version
  in its matrix with that version, runs the `pre-commit` hooks once instead of
  in every test job, and only runs on pushes to `main` and pull requests
* GitHub releases are made with the GitHub CLI, only from `main` after the
  tests and linters pass, and their notes are the released version's section
  of this changelog
* The documentation has a coverage report page
* `dependabot` checks the `uv` dependencies and GitHub Actions weekly
* `.python-version` (3.11) is kept in the repository
* The federal rules are divided into `header`, `general`, `citations`,
  `civil`, `constitutional`, and `criminal` (in the "federal" folder of
  `instructions`), replacing `federal/opinion.csv`. `header` and `general` are
  always applied; the others can be named alone (`rulebooks = civil,
  criminal`), and "federal" (still the default) is all six. A file named more
  than once is applied once
* The citation variables are named `citations_...` instead of
  `references_...`, and the constitutional ones `constitutional_...` instead
  of `general_...`. A rule for the Third Amendment (`constitutional_amend3`)
  is added
* The Federal Judicial Center's biographies, the Martin-Quinn scores, and the
  Judicial Common Space scores come from
  [fjc-biographies](https://github.com/WithPrecedent/fjc_biographies) and
  [judicial-common-space](https://github.com/WithPrecedent/judicial_common_space),
  now dependencies, instead of courtpy's own code:
  * `judges.download` downloads the center's files with fjc-biographies, into
    the "raw" folder of "judges" in the data folder, and no longer takes a
    `session`. `judges.build_roster` is fjc-biographies' roster with courtpy's
    `aliases` and `court_num`, so it also has `sequence`, the dates of each
    appointment, the ways of writing each name (`name_...`), and `career`.
    Unknown names are missing instead of blank. The careers are coded by
    fjc-biographies' "judges" rulebook (the same rules), so
    `instructions/judges.csv` is removed and `rulebook` takes a rulebook of
    fjc-biographies.
  * `Roster.from_fjc(jcs = True)` adds each appointment's Judicial Common
    Space score as computed by judicial-common-space (for district judges
    too), instead of matching the published scores of the judges of the
    courts of appeals by name. `Roster.from_fjc(martin_quinn = True)` (or the
    path of a saved "justices.csv") adds the justices' Martin-Quinn scores
    (`mq_first`, `mq_last`, `mq_mean`, and `mq_terms`).
  * `politics.download` downloads the Martin-Quinn and NOMINATE files with
    judicial-common-space, into "politics" in the data folder as before, and
    its `folder` is now the data folder. The Martin-Quinn "court" file is no
    longer used: `politics.martin_quinn` summarizes the justices' scores in
    each term (their median, lowest, and highest), and takes the "justices"
    file.
  * `politics.justices` reads the scores with judicial-common-space, which
    adds `jcs` (the score on the Common Space scale) in place of
    `martin_quinn_sd`.
  * `jcs.download` downloads the published files with judicial-common-space,
    and its `folder` is now the data folder. `jcs.judges` and `jcs.justices`
    are removed: use `Roster.from_fjc(jcs = True)` and `politics.justices`.
  * The options for these sources' files and addresses (`_FJC_FILES`,
    `_FJC_URL`, `_JCS_FILES`, `_JCS_PAGE`, `_MQ_FILES`, `_MQ_PAGE`,
    `_VOTEVIEW_FILES`, and `_VOTEVIEW_URL`) are removed.
* `Roster.match` matches a name by how much of it the opinion gives: first a
  full name (any of fjc-biographies' `name_...` forms, or an alias), then
  initials and the last name ("S. Lynch", "S. L. Lynch") or the middle and
  last names, and then the last name alone. Each is narrowed by the years of
  service and then by court, as before: the case's court, a district court of
  its circuit, and then any other court (a judge sitting by designation). A
  full name no longer counts as ambiguous because another judge's initials or
  middle name fit it, and a suffix ("SMITH, JR.") is part of a name.
  `name_forms` takes the suffix and returns the forms grouped by level
  (`full`, `initials`, and `last`) instead of one list.
* The `reference` folder is removed, since its data now come from
  fjc-biographies, judicial-common-space, and the other sources' current
  files. The tables that are still needed are dictionaries in `options`:
  `_PRESIDENTS` (the party of the president in each year since 1933, which
  `politics.presidents` reads in place of the years in which the party
  changed), `_COURTS` (a number and folder name for each court, by a pattern
  of the Federal Judicial Center's name for it), and `_TRIAL_COURTS` (each
  district court's name, by a pattern of how opinions name it). The last two
  are not yet used. Their patterns escape the periods and parentheses that
  the old files left as regular-expression syntax, and the District of
  Columbia's name is no longer "DISTRICT OF DISTRICT OF COLUMBIA".
  `politics.presidents`' `start` defaults to the first year it knows, and its
  `president_party` is a nullable whole number.
  `utilities.instructions_folder` returns the folder of rulebooks.
* `code_judges` adds `judge1`, `judge1_nid`, `judge2`, `judge2_nid`, and so
  on: the Federal Judicial Center's name and `nid` of the judge that each
  name in `panel_judges` refers to, numbered by the name's place in the list.
  A name that is not matched leaves its place missing, so the judges after
  it keep theirs.
* A `labels` kind of rule, which lists the value of every rule for its
  variable whose pattern appears, once each and separated by commas.
* `federal/agencies.csv` (part of the "federal" rulebook, which is now seven
  files) makes `agencies`: every federal agency that a case's caption,
  history, or opinion names, by its name or a common abbreviation (such as
  "ATF", which fjc-idb calls "BATF"), as their names separated by commas.
  The agencies are the Integrated Database's, as fjc-idb lists them. An
  abbreviation that is also something else is not counted when the case
  names the other thing (such as "EPA" in a case about the Equal Pay Act,
  or "DOT" in one that cites the Dictionary of Occupational Titles), and a
  department that states also have needs "the", "U.S.", "United States", or
  "federal" right before its name.

## 0.3.1

* `parse` with more than one worker gives each process a chunk of cases at a
  time (`options._CHUNK_SIZE`, 1,000 by default) instead of one task for each
  case. With about 900,000 cases on Windows, the pool of processes stopped
  handing out work while its manager thread used a whole CPU. Progress is now
  logged after each chunk ("%d of %d cases parsed") with one worker or
  several. The results and the table are unchanged
* The package's version in `pyproject.toml` is 0.3.1. The first commit of
  0.3.1 changed only `__version__`, so the package built from it was 0.3.0

## 0.3.0

Updated to [amos](https://github.com/WithPrecedent/amos) 0.4.0, whose
techniques write `apply` instead of `implement`. courtpy now adds the Federal
Judicial Center's Integrated Database to cases of the courts of appeals, and
the Judicial Common Space scores to judges, justices, and courts. Every case
from the bulk data keeps CourtListener's whole docket.

### Added

* A `fjc_idb` module, which adds the Federal Judicial Center's Integrated
  Database (IDB) to cases with the
  [fjc-idb](https://github.com/WithPrecedent/fjc_idb) package, now a
  dependency. `code_idb` (an amos merger) adds the database's record of each
  appeal to its case in the courts of appeals, with "idb_" before fjc-idb's
  names for the columns. A case is matched by its circuit (`court_num`, or
  CourtListener's court id) and the first of its docket numbers that the
  database has, and an appeal that ended more than once (because it was
  reopened or remanded) is matched by the record whose judgment is nearest
  the decision. Without a `source`, it reads the years of the cases from the
  database's yearly files, which are downloaded if they are missing, and with
  `district = true` it also adds the district court's record of the case
  that was appealed (with fjc-idb's `merge_district`). `appeals` returns the
  database's table of appeals for a range of years, and `download` downloads
  its yearly files.
* A `jcs` module, which downloads the Judicial Common Space scores from
  https://epstein.wustl.edu/jcs (into "jcs" in the data folder) and reads
  them: `judges` (each judge of a court of appeals, matched to the Federal
  Judicial Center's `nid` by name and circuit), `justices` (by term and the
  Supreme Court Database's `justiceName`), and `medians` (by year).
  `Roster.from_fjc(jcs = True)` adds each judge's score as the "jcs"
  attribute, and `politics.build_table(common_space = True)` adds the
  medians.
* A `CITATION.cff` file and a citation section in the README.

### Changed

* Updated to [amos](https://github.com/WithPrecedent/amos) 0.4.0 and
  `chrisjen` 0.3.0, the oldest versions that courtpy now accepts. A technique
  of either writes `apply` instead of `implement`, so courtpy's loaders,
  coders, and mergers (`CaseLoader`, `DropText`, `CodeIdb`, `MergeJudges`,
  `CodePolitics`, and `CodeScdb`) do too. Calling `apply` works as before,
  except that its item is now required: a loader called outside a project
  takes `None` to start a new dataset (`LoadCourtListener().apply(None,
  source = ...)`). amos now declares the item of `apply` as a `Dataset`, so
  courtpy passes its tables to mergers as datasets.
* Module docstrings no longer list private names, which the API reference
  leaves out.
* Every case from the bulk data is saved with CourtListener's whole docket
  (such as `docket_number_core`, `pacer_case_id`, `appeal_from_id`,
  `appellate_case_type_information`, `appellate_fee_status`, and
  `idb_data_id`) instead of twelve of its fields. `BulkData.extract` reads
  the dockets file a second time to do so, and holds only the court of each
  docket in memory until the cases are known. The API client's "dockets"
  option saves the whole docket too.
* `options._DOCKET_FIELDS` (the fields that were kept) is replaced by
  `options._DOCKET_SKIPPED` (the fields that are not).
* `judges.clean_name` leaves out accents, so "Gelpí" in one source matches
  "Gelpi" in another.
* The Judicial Common Space file of the earlier version
  (`reference/biographies/federal/jcs.csv`) is moved out of the repository,
  to "jcs" in the data folder.
* When courtpy runs from its repository, its data folder is
  `options._DATA_FOLDER`, "data/courts" two folders above the repository (as
  fjc-idb's is), so the IDB's yearly files that fjc-idb downloads are shared.
  An installed courtpy still uses "courtpy" in the user's local application
  data folder, and `COURTPY_DATA_DIR` still overrides both.

## 0.2.3

* Updated to the `snickerdoodle` 0.4.0 template
* Made `ruff` prefer single quotes

## 0.2.2

Updated to [amos](https://github.com/WithPrecedent/amos) 0.2.6, whose mergers
and shapers join tables whose rows are different things. courtpy uses them to
add judges, the politics of each year, and the Supreme Court Database to
cases, and downloads other researchers' data from its sources.

The federal rules now read what recent CourtListener cases have only in the
text of their opinions. CourtListener's full case name, judges, and
disposition are blank for about nine in ten of the federal appellate cases
filed since 2025, so the parties' roles and the panel were unknown, and
reversals were coded from the opinion's words anywhere. In a sample of 1,500
such criminal appeals, the roles are now found in 97%, and a panel of three
judges in 99%.

### Added

* The federal rules find the caption in the opinion's opening (`caption`,
  `caption1`, and `caption2`) when the header's caption names no appellant
  or appellee, and code `party1_appellant`, `party1_appellee`,
  `party2_appellant`, and `party2_appellee` from it. A caption is a role
  before "v." ("Plaintiff-Appellee, v."), or parties in capital letters
  with one role, so a citation in the opinion's words is not mistaken for
  one.
* The federal rules find the decision that an opinion states (`decision`:
  "AFFIRMED.", "VACATED AND REMANDED.", "Affirmed by unpublished per
  curiam opinion", or "we reverse", but not "we will reverse only if") and
  code `decision_affirm`, `decision_reverse`, `decision_vacate`,
  `decision_remand`, and `decision_dismiss` from it.
* `courtpy.judges` identifies the judges on each case, which the earlier,
  unreleased courtpy did and this version had not rebuilt. A `Roster`
  (`Roster.from_fjc()`) is made from the Federal Judicial Center's files of
  judges' service, demographics, and careers, which `download` gets, and
  matches a name in an opinion to a judge of the case's court, or else of a
  district court in its circuit, or else of another court, among the judges
  serving in the case's year. The careers are coded by the rules in
  `instructions/judges.csv`. Unlike the earlier version, a name that fits
  more than one judge is left unmatched instead of being given to one of
  them, no judge is matched outside the judge's years of service, a judge
  who was reassigned to another court keeps the appointment of the judge's
  own earlier service, a rating or vote that is not recorded is missing
  instead of zero, the district courts of Vermont are in the Second Circuit,
  and a clerkship at a district court does not make a judge a prosecutor.
* `merge_judges` (an `amos.Merger`) adds what the roster says about the
  judge that each row names, such as the author of each opinion, with a
  prefix: the judge's attributes, and the judge's age, senior status, and
  whether the judge sat by designation in the case's year and court. Like
  every merger, it takes "source", "columns", "prefix", and "indicator",
  never adds or removes a row, and records how many rows it matched.
* `code_judges` (a munger) adds the judges of each panel who were found
  (`panel_names` and `panel_found`) and the panel's composition: the mean of
  each attribute of its judges, such as `panel_party`, `panel_woman`,
  `panel_age`, and `panel_designated`. It is built from the `lists_to_rows`
  shaper of amos, `merge_judges`, and the `merge_summary` merger.
* `judge_votes` (an `amos.Shaper`) and `courtpy.judges.vote_table` make a
  table with one row for each judge on each case, with the judge's
  attributes (`judge_{attribute}`), those of the other judges of the panel
  (`colleagues_{attribute}`), and the judge's vote on each outcome
  (`vote_reversal` and so on: the outcome, or its opposite for a judge who
  dissented). Like every shaper, it takes "label", "task", and "groups" for
  the table that it makes, and must come before the data is split. It can be
  one of a loader's coders, so a vote can be the label of a study, and
  `load_cases` reads the `case_id` column of a saved table of votes as text,
  so a study splits its cases the same way when the table is reused.
* `courtpy.politics` and `code_politics` add the political context of each
  case's year: the party of the president and, from a table that
  `build_table` makes, the Supreme Court's Martin-Quinn scores and the
  median NOMINATE scores of each chamber of Congress. `code_politics` is the
  `merge_keys` merger of amos with the year as its key, so it takes that
  merger's parameters ("source", "on", "other_on", "columns", "prefix",
  "indicator", and "duplicates"), and a table with a year twice stops a
  study instead of quietly using one of its rows. A term of the court that
  the scores divide in two (as 2005 is) is one year, which the earlier
  version's table had twice.
* `courtpy.politics.download` gets the current files of Martin-Quinn scores
  (from the links of https://mqscores.wustl.edu/measures.php) and of the
  ideology of members of Congress (the "Member Ideology" data of
  https://voteview.com/data), and `build_table`, `martin_quinn`, and
  `nominate` use them when they are given no files.
  `courtpy.politics.justices` returns the Martin-Quinn score of each justice
  in each term.
* `courtpy.scdb` adds the Supreme Court Database. `download` gets the latest
  release from https://scdb.la.psu.edu/data/, `cases` and `votes` return its
  case centered and justice centered tables, and `code_scdb` (an
  `amos.Merger`) adds its coding to parsed cases of the Supreme Court
  (`scdb_issueArea`, `scdb_decisionDirection`, and so on), matched by the
  database's id of each case or else by a citation. CourtListener cases of
  the Supreme Court have that id as `scdb_id`.
* `examples/judge_votes.ini` is a study of how judges vote in criminal
  appeals.

### Changed

* Requires amos 0.2.6.
* The repository is "courtpy" (in lower case, like the package), so the
  links to it and to the documentation, which had stopped working, are
  https://github.com/WithPrecedent/courtpy and
  https://WithPrecedent.github.io/courtpy.
* `panel_judges` comes from the panel that the opinion's opening names
  ("Before SMITH, Chief Judge, and JONES and BROWN, Circuit Judges", or
  "Present:"), including a judge sitting by designation, and only
  otherwise from the source's list of judges, which in CourtListener may
  name only the author or be blank. The text that was used is `panel_text`.
* `code_outcome` uses the decision that the opinion states when the header
  has no disposition, and the opinion's words anywhere (`opinion_reverse`,
  `opinion_vacate`, and `opinion_remand`) only when there is neither. Those
  words are often about an earlier decision or a standard of review ("we
  will reverse only if"): in the sample, they coded 17% of defendants'
  appeals as reversals, and the stated decisions 9%.

### Fixed

* A judge's middle initial "J." is no longer read as "Justice", which
  divided "LAWRENCE J. VILARDO" into two judges, and initials such as
  "S.R." before a name are no longer read as "Sr.", which left "S.R.
  THOMAS" as "THOMAS". "J.", "JR.", and "SR." are still removed when no
  name follows them.

## 0.2.1

Updated to [amos](https://github.com/WithPrecedent/amos) 0.2.5.

### Changed

* Requires amos 0.2.5.
* `code_parties`, `code_case_type`, and `code_outcome` are now mungers
  (`amos.Munger`, new in amos 0.2.4), since they change and add columns
  without adding or removing rows. Their names in settings are unchanged, and
  the dataset's history now lists the columns that each one changed and
  created. `drop_text`, which removes columns, is still a cleaner.
* The example study and the documentation use `logit` for scikit-learn's
  logistic regression, which amos 0.2.4 renamed from `sk_logit`. (Its
  statsmodels model is now `logit_sm`.) Settings that name `sk_logit` must use
  `logit`.

### Added

* A recipe for searching the opinions' text with amos's `flag_patterns` and
  `count_patterns` mungers, without a file of rules.

## 0.2.0

Updated to [amos](https://github.com/WithPrecedent/amos) 0.2.3, whose loaders
replace the "cases" section of a project's settings. Settings written for
0.1.0 need the changes below.

### Added

* Loaders, a genre of `amos` loaders (`CaseLoader`) in the new `loaders`
  module: `load_court_listener` downloads (if asked), parses, and codes
  CourtListener cases; `load_lexis_nexis` divides, parses, and codes
  Lexis-Nexis cases; and `load_cases` loads a table saved by `save_cases`.
  Named first in the wrangler, a loader makes the project's data, so a
  project needs no `item`. Loaders work through the project's clerk: sources
  are found (and downloads saved) in its input folder, and a "save"d table is
  kept in its interim folder. The label is checked after the coders run, so
  it can be a column that a coder makes, and the dataset's history records
  the loader and each coder.

### Changed

* Requires amos 0.2.3 (and pandas 3).
* `courtpy.Project` is now `amos.Project` itself, which runs a workflow with a
  loader without an `item`.
* `code` moved to the `coders` module (it is still `courtpy.code`).
* The example study and the documentation use `sk_logit`, scikit-learn's
  logistic regression, because amos 0.2.3 gave the name `logit` to the
  statsmodels model (which needs `pip install amos[statistics]`).

### Removed

* The "cases" section of a project's settings, `courtpy.build`,
  `courtpy.collect`, and the `interface` module. Move the settings of a
  "cases" section to a "load_court_listener_parameters" (or
  "load_lexis_nexis_parameters") section, add the loader to the start of the
  wrangler's techniques, and rename "folder" to "source". Relative paths are
  now in the clerk's input folder ("save" in its interim folder) rather than
  its root folder.

## 0.1.0

The first release, and the first on PyPI. It is a complete rewrite of the
earlier, unreleased courtpy, which was built on siMpLify. The analysis is now
done with [amos](https://github.com/WithPrecedent/amos) (and its workflows
with [chrisjen](https://github.com/WithPrecedent/chrisjen)). The changes below
are from that earlier code.

### Added

* Downloads from CourtListener, now the main source of opinions:
  * `BulkData` extracts cases from CourtListener's quarterly bulk data, which
    needs no API key and has no limits. It downloads the files (resuming an
    interrupted download) or streams them.
  * `CourtListener` downloads cases with the REST API (version 4). It spaces
    its requests, waits when CourtListener asks it to, and saves its place so
    that a download stopped by an account's limit resumes where it stopped.
  * Both save each case as a JSON file, which `courtlistener.read_case` reads.
    CourtListener's header information comes from its data, so no rules are
    needed to find it.
* `courtpy.secrets` keeps the CourtListener API key outside of any project:
  in the system keyring, in a private file in the user's configuration folder,
  in the `COURTLISTENER_API_KEY` environment variable, or in a `.env` file.
* A single rule engine (`Rule` and `Rulebook`) for every CSV file of rules,
  with one set of columns (`target`, `variable`, `kind`, `pattern`, `value`,
  `ignorecase`, `dotall`, and `note`) and nine kinds of rules. See
  `src/courtpy/instructions/README.md`.
* The coders `code_parties`, `code_case_type`, `code_outcome`, and `drop_text`,
  which are `amos` techniques and can be named in any `amos` settings.
* `courtpy.Project`, an `amos.Project` whose "cases" section collects, parses,
  and codes the cases before the analysis.
* The `courtpy` command (`key`, `download`, `split`, `parse`, `rules`, and
  `run`).
* Tests, and an example study (`examples/federal_appeals.ini`).
* The parts of the [snickerdoodle](https://github.com/WithPrecedent/snickerdoodle)
  template: GitHub Actions (tests on Linux, macOS, and Windows with Python
  3.11 to 3.14, linting, type checking, documentation deployed to GitHub
  Pages, releases, publishing to PyPI, and validating the Codecov settings),
  dependabot, issue templates, pre-commit hooks, an editor configuration, a
  code of conduct, a contribution guide, and documentation built with MkDocs
  (a tutorial, an advanced user guide, a guide to writing rules, recipes, and
  the API reference).

### Changed

* The package uses a `src` layout and is built with hatchling and uv.
* The old instruction files were converted to the new columns:
  `organizer_lexis_nexis.csv` and `separate_opinions.csv` became
  `lexis_nexis.csv`, `keywords_federal.csv` became `federal/header.csv`, and
  `parser_opinions_federal.csv` became `federal/opinion.csv` (and is now
  saved in UTF-8). Some variables were renamed to be easier to read, such as
  `party_appnt1` to `party1_appellant`, `counsel_us_atty` to
  `counsel_us_attorney`, `notice_unpub_rule` to `notice_unpublished`, and
  `disposition_op_reversed` to `opinion_reverse`.
* A decision is coded as a reversal from its stated disposition when it has
  one, and only otherwise from the opinion's words. (Before, either one was
  enough, so "we will not reverse" in an affirmed case counted as a
  reversal.)
* Which party won an appeal is now coded from the party's role: an appellant
  wins a reversal, and an appellee wins an affirmance. (The old code had the
  two reversed.) Outcomes that cannot be known are missing values rather than
  false.
* Judges' names are split at whole words only, so names such as "Kirby" and
  "Holland" are no longer cut at "BY" and "AND".

### Fixed in the rules

* `Fed_App_P`, `Fed_Civ_P`, `Fed_Crim_P`, and `Fed_Evid` required a "§" sign,
  which is not used when federal rules are cited, so they never matched. The
  evidence rule's pattern was also malformed.
* `references_case` now includes the Federal Reporter, Fourth Series (F.4th).
* `amend8` searched for the Seventh Amendment's numeral ("VII").
* `titlevii` required the text "Title VII.," followed by a space.
* `alcohol` searched for "ddistilled".
* The opinion's dispositions (`opinion_reverse`, `opinion_vacate`,
  `opinion_remand`, and `opinion_dismiss`) only matched "We willreverse" (with
  no space) or a capitalized "Dismiss".
* The variables `criminal_manslaugther` and `general_aritcleiv` are now
  `criminal_manslaughter` and `general_articleiv`.
* Non-breaking spaces in patterns now match any space.
* Lexis-Nexis header sections that end the header (such as a "JUDGES:"
  paragraph just before "OPINION") are now found.
* Agencies are matched from the longest name down, so "Postal Service Board of
  Contract Appeals" is no longer labeled "Postal Service".

### Removed

* The siMpLify-based modules (`almanac`, `cookbook`, `entities`, `implements`,
  `cases.py`, and `controller.py`) and the settings files that went with them.
* The `federal_archive` instruction files, which the combined files had
  replaced.
* The external data used to add judges' biographies and political context is
  kept in `reference/`, but is not yet used by the new version.
