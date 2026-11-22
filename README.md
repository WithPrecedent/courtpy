<p align="center">
  <img src="https://raw.githubusercontent.com/WithPrecedent/courtpy/main/docs/images/logo.webp" alt="courtpy logo" width="300">
</p>

# courtpy

| | |
| --- | --- |
| Version | [![PyPI Latest Release](https://img.shields.io/pypi/v/courtpy.svg?style=plastic&color=cornflowerblue&label=PyPI&logo=PyPI&logoColor=yellow)](https://pypi.org/project/courtpy/) [![GitHub Latest Release](https://img.shields.io/github/v/tag/WithPrecedent/courtpy?style=plastic&color=forestgreen&label=GitHub&logo=github)](https://github.com/WithPrecedent/courtpy/releases) |
| Status | [![Build Status](https://img.shields.io/github/actions/workflow/status/WithPrecedent/courtpy/ci.yml?style=plastic&branch=main&color=cadetblue&label=Tests&logo=pytest)](https://github.com/WithPrecedent/courtpy/actions/workflows/ci.yml?query=branch%3Amain) [![Code Coverage](https://img.shields.io/codecov/c/github/WithPrecedent/courtpy/main?style=plastic&color=cadetblue&label=Coverage&logo=codecov)](https://app.codecov.io/gh/WithPrecedent/courtpy) [![Development Status](https://img.shields.io/badge/Development-Active-seagreen?style=plastic&logo=git)](https://www.repostatus.org/#active) [![Project Stability](https://img.shields.io/pypi/status/courtpy?style=plastic&logo=pypi&label=Stability&logoColor=yellow)](https://pypi.org/project/courtpy/) |
| Documentation | [![Hosted By](https://img.shields.io/badge/Hosted_by-Github_Pages-blue?style=plastic&color=forestgreen&logo=github)](https://WithPrecedent.github.io/courtpy) |
| Tools | [![Documentation](https://img.shields.io/badge/MkDocs-magenta?style=plastic&color=deepskyblue&logo=markdown&labelColor=gray)](https://squidfunk.github.io/mkdocs-material/) [![Linter](https://img.shields.io/endpoint?style=plastic&url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![Type Checker](https://img.shields.io/badge/mypy-steelblue?style=plastic&logo=python&logoColor=white&labelColor=gray)](https://mypy-lang.org/) [![Dependency Manager](https://img.shields.io/badge/uv-mediumpurple?style=plastic&logo=uv&labelColor=gray)](https://docs.astral.sh/uv/) [![Pre-commit](https://img.shields.io/badge/pre--commit-darkolivegreen?style=plastic&logo=pre-commit&logoColor=white&labelColor=gray)](https://pre-commit.com/) [![CI](https://img.shields.io/badge/GitHub_Actions-forestgreen?style=plastic&logo=githubactions&labelColor=gray&logoColor=white)](https://github.com/features/actions) [![Repository Template](https://img.shields.io/badge/snickerdoodle-bisque?style=plastic&logo=cookiecutter&labelColor=gray)](https://www.github.com/WithPrecedent/snickerdoodle) [![Dependency Maintainer](https://img.shields.io/badge/dependabot-forestgreen?style=plastic&logo=dependabot&logoColor=white&labelColor=gray)](https://github.com/dependabot) |
| Compatibility | [![Compatible Python Versions](https://img.shields.io/pypi/pyversions/courtpy?style=plastic&color=cornflowerblue&label=Python&logo=python&logoColor=yellow)](https://pypi.org/project/courtpy/) [![Linux](https://img.shields.io/badge/Linux-lightseagreen?style=plastic&logo=linux&labelColor=gray&logoColor=white)](https://www.linux.org/) [![MacOS](https://img.shields.io/badge/MacOS-antiquewhite?style=plastic&logo=apple&labelColor=gray)](https://www.apple.com/macos/) [![Windows](https://img.shields.io/badge/Windows-blue?style=plastic)](https://www.microsoft.com/en-us/windows?r=1) |
| Stats | [![PyPI Download Rate (per month)](https://img.shields.io/pypi/dm/courtpy?style=plastic&color=cornflowerblue&label=Downloads%20💾&logo=pypi&logoColor=yellow)](https://pypi.org/project/courtpy/) [![GitHub Stars](https://img.shields.io/github/stars/WithPrecedent/courtpy?style=plastic&color=forestgreen&label=Stars%20⭐&logo=github)](https://github.com/WithPrecedent/courtpy/stargazers) [![GitHub Contributors](https://img.shields.io/github/contributors/WithPrecedent/courtpy?style=plastic&color=forestgreen&label=Contributors%20🙋&logo=github)](https://github.com/WithPrecedent/courtpy/graphs/contributors) [![GitHub Issues](https://img.shields.io/github/issues/WithPrecedent/courtpy?style=plastic&color=forestgreen&label=Issues%20📘&logo=github)](https://github.com/WithPrecedent/courtpy/issues) [![GitHub Forks](https://img.shields.io/github/forks/WithPrecedent/courtpy?style=plastic&color=forestgreen&label=Forks%20🍴&logo=github)](https://github.com/WithPrecedent/courtpy/forks) |
| | |

-----

## What is courtpy?

`courtpy` collects court opinions, turns them into data, and analyzes them. It
is designed for empirical legal research, where the data has to be explained
and the results reproduced. You don't need to know how to code to use `courtpy`.
Everything is described in a simple settings files and parsing instructions are
located in CSV files (of which many are included out of the box). But if you do
code, `courtpy` is highly extensible to allow easy data munging, creation of
new fields, and wrapping custom tools.

* **Collect** opinions from [CourtListener](https://www.courtlistener.com),
  from its free bulk data or its API, or use opinions you downloaded from
  Lexis-Nexis.
* **Parse** them into a table, one row for each case, with rules written in
  spreadsheets (CSV files) that anyone can read and change: the parties and
  their roles, the court, the judges, the disposition, the issues discussed,
  the citations, and more.
* **Study** the judges on each case, with integration of the Federal Judicial Center's
  biographical data and Judicial Common Space Scores (from
  [fjc-biographies](https://github.com/WithPrecedent/fjc_biographies) and
  [judicial-common-space](https://github.com/WithPrecedent/judicial_common_space)). Data about the overall
  political and judicial context can also be easily added, including Martin-Quinn scores, NOMINATE scores of Congress, the Supreme Court Database, and the Federal Judicial Center's Integrated Database.
* **Analyze** the data with [amos](https://github.com/WithPrecedent/amos) (which is built into `courtpy`),
  which compares models, preprocessing, and statistical methods, and records
  everything needed to reproduce the results.

## Why use courtpy?

* **Transparent.** What `courtpy` finds in an opinion comes from rules in CSV
  files, not from code, so a study's methods can be read, reported, and
  changed by anyone who can use a spreadsheet. The rules are part of the
  study, so others can check them.
* **Reproducible.** A whole study (which cases, how they were parsed and coded,
  and how they were analyzed) fits in one settings file, and `amos` records
  every step and the version of every package.
* **Fast.** `courtpy` uses vectorized methods and compiled regular expressions to parse and munge the court data.

## Techniques and datasets

`courtpy` is built on [amos](https://github.com/WithPrecedent/amos). A study is an `amos` project,
described in one settings file that names **techniques** in **steps** of the
project's **workers**. `courtpy` adds these techniques to those of `amos`, and
a settings file can name them like any other:

<table>
<thead>
<tr><th>Stage</th><th>Steps</th><th>Techniques</th></tr>
</thead>
<tbody>
<tr><td rowspan="6" valign="middle">wrangler</td><td>Loaders</td><td><a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/judges/#courtpy.references.judges.DownloadBiographies"><code>download_biographies</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/loaders/#courtpy.wrangler.loaders.DownloadCourtlistener"><code>download_courtlistener</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/fjc_idb/#courtpy.references.fjc_idb.DownloadIdb"><code>download_idb</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/jcs/#courtpy.references.jcs.DownloadJcs"><code>download_jcs</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/politics/#courtpy.references.politics.DownloadPolitics"><code>download_politics</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/scdb/#courtpy.references.scdb.DownloadScdb"><code>download_scdb</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/loaders/#courtpy.wrangler.loaders.LoadCases"><code>load_cases</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/loaders/#courtpy.wrangler.loaders.LoadCourtlistener"><code>load_courtlistener</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/fjc_idb/#courtpy.references.fjc_idb.LoadIdb"><code>load_idb</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/loaders/#courtpy.wrangler.loaders.LoadLexisNexis"><code>load_lexis_nexis</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/politics/#courtpy.references.politics.LoadPolitics"><code>load_politics</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/judges/#courtpy.references.judges.LoadRoster"><code>load_roster</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/scdb/#courtpy.references.scdb.LoadScdb"><code>load_scdb</code></a></td></tr>
<tr><td>Parsers</td><td><a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/rules/#courtpy.wrangler.rules.ParseAgencies"><code>parse_agencies</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/parsers/#courtpy.wrangler.parsers.ParseAll"><code>parse_all</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/rules/#courtpy.wrangler.rules.ParseCitations"><code>parse_citations</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/rules/#courtpy.wrangler.rules.ParseCivil"><code>parse_civil</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/rules/#courtpy.wrangler.rules.ParseConstitutional"><code>parse_constitutional</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/rules/#courtpy.wrangler.rules.ParseCriminal"><code>parse_criminal</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/rules/#courtpy.wrangler.rules.ParseFederal"><code>parse_federal</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/rules/#courtpy.wrangler.rules.ParseGeneral"><code>parse_general</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/rules/#courtpy.wrangler.rules.ParseHeader"><code>parse_header</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/rules/#courtpy.wrangler.rules.ParseLexisNexis"><code>parse_lexis_nexis</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/rules/#courtpy.wrangler.rules.ParseReview"><code>parse_review</code></a></td></tr>
<tr><td>Cleaners</td><td><a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/coders/#courtpy.wrangler.coders.DropTextColumns"><code>drop_text_columns</code></a></td></tr>
<tr><td>Mungers</td><td><a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/coders/#courtpy.wrangler.coders.CodeCaseType"><code>code_case_type</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/coders/#courtpy.wrangler.coders.CodeOutcome"><code>code_outcome</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/judges/#courtpy.references.judges.CodePanels"><code>code_panels</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/coders/#courtpy.wrangler.coders.CodeParties"><code>code_parties</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/coders/#courtpy.wrangler.coders.SplitValues"><code>split_values</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/coders/#courtpy.wrangler.coders.TidyCases"><code>tidy_cases</code></a></td></tr>
<tr><td>Mergers</td><td><a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/judges/#courtpy.references.judges.AddBiography"><code>add_biography</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/judges/#courtpy.references.judges.AddCircuit"><code>add_circuit</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/scores/#courtpy.references.scores.AddCourtScores"><code>add_court_scores</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/politics/#courtpy.references.politics.AddExecutive"><code>add_executive</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/politics/#courtpy.references.politics.AddHighCourt"><code>add_high_court</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/fjc_idb/#courtpy.references.fjc_idb.AddIdb"><code>add_idb</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/judges/#courtpy.references.judges.AddJcs"><code>add_jcs</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/scores/#courtpy.references.scores.AddJudgeScores"><code>add_judge_scores</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/politics/#courtpy.references.politics.AddLegislature"><code>add_legislature</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/scdb/#courtpy.references.scdb.AddScdb"><code>add_scdb</code></a></td></tr>
<tr><td>Shapers</td><td><a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/shapers/#courtpy.wrangler.shapers.CasesToCaseTypes"><code>cases_to_case_types</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/shapers/#courtpy.wrangler.shapers.CasesToCourts"><code>cases_to_courts</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/shapers/#courtpy.wrangler.shapers.CasesToDockets"><code>cases_to_dockets</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/judges/#courtpy.references.judges.CasesToJudges"><code>cases_to_judges</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/shapers/#courtpy.wrangler.shapers.CasesToPartyTypes"><code>cases_to_party_types</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/judges/#courtpy.references.judges.CasesToVotes"><code>cases_to_votes</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/wrangler/shapers/#courtpy.wrangler.shapers.DocketsToCases"><code>dockets_to_cases</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/judges/#courtpy.references.judges.DocketsToVotes"><code>dockets_to_votes</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/judges/#courtpy.references.judges.VotesToCases"><code>votes_to_cases</code></a></td></tr>
<tr><td valign="middle">explorer</td><td>Describers</td><td><a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/references/fjc_idb/#courtpy.references.fjc_idb.CompareWithIdb"><code>compare_with_idb</code></a></td></tr>
<tr><td rowspan="2" valign="middle">critic</td><td>Evaluators</td><td><a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/critic/audits/#courtpy.critic.audits.AuditCoverage"><code>audit_coverage</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/critic/audits/#courtpy.critic.audits.AuditParsing"><code>audit_parsing</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/critic/audits/#courtpy.critic.audits.AuditRandomAssignment"><code>audit_random_assignment</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/critic/audits/#courtpy.critic.audits.ValidateCoding"><code>validate_coding</code></a></td></tr>
<tr><td>Inferers</td><td><a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/critic/inferers/#courtpy.critic.inferers.PanelEffects"><code>panel_effects</code></a></td></tr>
<tr><td valign="middle">artist</td><td>Plots</td><td><a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/artist/plots/#courtpy.artist.plots.CasesOverTime"><code>cases_over_time</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/artist/plots/#courtpy.artist.plots.CourtRates"><code>court_rates</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/artist/plots/#courtpy.artist.plots.IdbConfusionMatrices"><code>idb_confusion_matrices</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/artist/plots/#courtpy.artist.plots.IdbMissingDifferences"><code>idb_missing_differences</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/artist/plots/#courtpy.artist.plots.IssuesOverTime"><code>issues_over_time</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/artist/plots/#courtpy.artist.plots.JudgeNetwork"><code>judge_network</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/artist/plots/#courtpy.artist.plots.LowerCourtRates"><code>lower_court_rates</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/artist/plots/#courtpy.artist.plots.PanelComposition"><code>panel_composition</code></a>, <a href="https://WithPrecedent.github.io/courtpy/reference/courtpy/artist/plots/#courtpy.artist.plots.TrendsByAdministration"><code>trends_by_administration</code></a></td></tr>
</tbody>
</table>

Each of `courtpy`'s datasets is an `amos.Dataset`. The loaders make `Cases`, and the shapers turn one form of the dataset into another:

| Dataset | One row for each | Made by |
| --- | --- | --- |
| `Cases` | Case, with its information and the text of its sections. | the loaders, `votes_to_cases`, `dockets_to_cases` |
| `Dockets` | Docket number of each case (a case that consolidated several appeals has a row for each), with the case's columns. | `cases_to_dockets` |
| `Votes` | Judge on each case (or on each docket), with the case's columns and the judge's vote. | `cases_to_votes`, `dockets_to_votes` |
| `Judges` | Judge, with what is known about the judge and summaries of the judge's votes. | `cases_to_judges` |
| `Courts` | Court, with summaries of its cases and judges. | `cases_to_courts` |
| `CaseTypes` | Case type (such as criminal, civil, tort, or contract), with summaries of its cases. | `cases_to_case_types` |
| `PartyTypes` | Party type, with summaries of the cases of parties of that type. | `cases_to_party_types` |

`Cases`, `Dockets`, and `Votes` can be made from each other. The others
summarize many cases and keep nothing about any one of them (such as its
docket number or date), so a researcher can see, for example, the mix of
case types that each court decides, but there is no going back. Every dataset can be saved and
loaded whole (with `save` and `load`), as `amos`'s `save_data` saves it.

## Getting started

### Installation

To install `courtpy`, use `pip`:

```sh
pip install courtpy
```

To install the latest development version from GitHub instead:

```sh
pip install git+https://github.com/WithPrecedent/courtpy
```

### Usage

#### Collecting opinions from CourtListener

CourtListener offers its opinions in two ways, and `courtpy.CourtListener`
downloads with both: its "method" is `"bulk"` (the default) or `"api"`. Both
save each case as a JSON file in a folder named for its court (such as
`courtlistener/ca1/4567890.json`), and the parser reads them the same way.

**The bulk data** is the whole CourtListener database, published as compressed
CSV files every three months. It needs no API key and has no limits, so it is
the best way to collect many cases. The files are large (the opinions file is
more than 50 GB), so extracting cases takes a few hours. The files are kept
outside your project so that they can be used again:

```python
import courtpy

courtpy.CourtListener().download(
    courts = "federal_geographic_circuits",
    start_date = "2019-01-01",
    end_date = "2019-12-31",
    folder = "courtlistener")
```

**The API** is best for small or very recent sets of cases. It needs an API
key: sign in to CourtListener and open the "API" page of your profile. A free
account can make 5 requests a minute, 50 an hour, and 125 a day (as of 2026).
`courtpy` asks for 20 cases at a time, waits when CourtListener asks it to, and
saves its place, so a download stopped by the daily limit resumes where it
stopped when it is run again:

```python
courtpy.CourtListener().download(
    "ca1", "2026-09-01", "2026-09-30", "courtlistener", method = "api")
```

Courts are named by their CourtListener ids (such as `ca1`, `cadc`, `cafc`,
and `scotus`) or by groups: `federal_appellate`, `federal_geographic_circuits`
(the twelve regional circuits, without the Federal Circuit), and `scotus`.

Store your API key once with `courtpy key set`. See
[Keeping your API key secret](https://WithPrecedent.github.io/courtpy/advanced/#keeping-your-api-key-secret)
for where it is kept and how `courtpy` finds it.

#### Using opinions from Lexis-Nexis

Lexis-Nexis downloads many cases into one text file. Divide such files into
one file for each case, and then parse them as the source "lexis_nexis":

```python
courtpy.lexis.split("downloads", folder = "lexis_nexis")
table = courtpy.parse("lexis_nexis", source = "lexis_nexis")
```

#### Parsing and coding

`courtpy.parse` reads a folder of saved cases and returns a
`pandas.DataFrame`, one row for each case, labeled by its id. `courtpy.code`
codes it and makes it `Cases`:

```python
table = courtpy.parse("courtlistener")
cases = courtpy.code(table)  # parties, case types, and outcomes
cases.save("cases.csv")  # and the whole dataset in "cases.joblib"
cases = courtpy.Cases.load("cases.csv")
```

The rules are in the CSV files in `courtpy`'s
[instructions folder](https://github.com/WithPrecedent/courtpy/tree/main/src/courtpy/instructions),
with a guide to writing your own. For example, the rules for federal cases may make more than 250
variables, including:

| Variables | Meaning |
| --- | --- |
| `party1`, `party2` | The parties on each side of "v." |
| `party1_appellant`, `party2_respondent`, `party1_united_states`, ... | Each party's role, and whether it is the United States. |
| `court_num`, `court_name` | courtpy's number and name for the court in "instructions/federal/courts.csv" (such as 10 and "tenth_circuit"): for a court of appeals, its number is its circuit (1 to 11, 12 for the D.C. Circuit, 13 for the Federal Circuit), and 99 for the Supreme Court. |
| `lower_court_num`, `lower_court_name` | The same for the court whose decision is reviewed (such as "district_of_colorado"), from the history (or CourtListener's docket). Missing for a review of an agency. |
| `panel_judges`, `panel_size`, `author`, `concurring`, `dissenting` | The judges. |
| `disposition_reverse`, `decision_reverse`, `opinion_reverse`, ... | The disposition: from the header, from the decision that the opinion states ("AFFIRMED."), and from the opinion's words anywhere. |
| `party1_agencies`, `party2_agencies`, `history_agencies` | The federal agencies that each party and the history name, separated by "; " (from "instructions/federal/agencies.csv"). |
| `agencies` | Every federal agency that the case names, separated by "; " (such as "Internal Revenue Service; United States Tax Court"). |
| `civil_...`, `constitutional_...`, `criminal_...`, `procedure_...`, `standard_...` | Issues discussed in the opinion (such as `criminal_firearm`, `civil_titlevii`, and `standard_de_novo`). |
| `review_district`, `review_agency`, `review_immigration`, `district_judges` | The kind of review, and the district judge of an appeal from a district court. |
| `citations_case`, `citations_statute`, ... | Citations in the opinion. |
| `published`, `year`, `date_filed`, `word_count` | Other information. |

The coders (which are `amos` techniques) add each party's role in the appeal
and in the case (such as `party2_criminal_defendant`), the case types
(`type_criminal`, `type_civil`, and one for each other prefix of the civil,
criminal, and constitutional rules, and the outcomes: `outcome_reversal`, `outcome_party1_won`,
`outcome_criminal_defendant_won`, and others.

#### Adding the judges and the politics of the day

The rules find the judges' names as an opinion writes them ("LYNCH"). To
study the judges, make a roster once from the Federal Judicial Center's
[biographical directory](https://www.fjc.gov/history/judges/biographical-directory-article-iii-federal-judges-export)
(three small files, which [fjc-biographies](https://github.com/WithPrecedent/fjc_biographies)
downloads and parses), and more coders can use it. `jcs = True` adds each
judge's Judicial Common Space score, computed by
[judicial-common-space](https://github.com/WithPrecedent/judicial_common_space):

```python
courtpy.judges.Roster.from_fjc(jcs = True).save()
votes = courtpy.code(table, [
    "code_parties", "code_case_type", "code_outcome", "code_panels",
    "add_executive", "add_legislature", "add_circuit", "cases_to_votes"])
```

Cases, judges, years, and other researchers' data are tables whose rows are
different things, so these coders are the mergers and shapers of
[amos](https://WithPrecedent.github.io/amos/advanced/#merging-data): a merger
adds the columns of another table to the rows that it matches, without ever
adding or losing a row, and records how many rows it matched.

| Coder | Adds |
| --- | --- |
| `add_biography` | What the roster says about each judge. In `Cases`, the columns are numbered by each judge's seat on the panel (`judge_name1`, `judge_party1`, `judge_woman1`, ..., `judge_name2`, ...); in `Votes`, each row has its judge's (`judge_party`, ...). A function can take the place of the roster. |
| `add_jcs` | Each judge's [Judicial Common Space](https://epstein.wustl.edu/jcs) score, numbered in the same way (`judge_jcs1`, ...). |
| `code_panels` | The judges of each panel who were found in the roster (`panel_names` and `panel_found`, and each judge's Federal Judicial Center name and number in `judge_name1` and `judge_nid1`, `judge_name2` and `judge_nid2`, and so on) and the panel's composition, such as `panel_party` (the mean party of the presidents who appointed its judges, from -1 for Democrats to 1 for Republicans), `panel_woman`, `panel_age`, and `panel_prosecutor`. |
| `add_executive` | The executive (president for federal cases) on the day the case was decided (`executive_name`) and their political party (`executive_ideology`, -1 or 1). |
| `add_legislature` | For federal cases, the median [NOMINATE](https://voteview.com/data) score of each chamber of the Congress then sitting (`senate_ideology` and `house_ideology`). |
| `add_high_court` | For federal cases, [Martin-Quinn score](https://mqscores.wustl.edu/measures.php) of the median justice in the Supreme Court's term then sitting (`high_court_ideology`). |
| `add_circuit` | The makeup of the whole circuit on the day the case was decided (for a district court, the circuit that hears its appeals): the median and total of the parties of the presidents who appointed its active judges (`circuit_median_party`, `circuit_total_party`) and of their Judicial Common Space scores (`circuit_median_jcs`, `circuit_total_jcs`). Senior judges, who do not sit en banc, are left out. |
| `add_judge_scores`, `add_court_scores` | Behavioral scores of each judge or court computed from training data (such as a table of `Judges` or `Courts` made from the training cases), matched by the judge's or court's number. |
| `cases_to_votes` | `Votes`: a table with one row for each judge on each case, with the judge's attributes (`judge_party`, ...), the other judges' (`colleagues_party`, ...), and the judge's vote (`vote_reversal`, the outcome or its opposite for a judge who dissented). |
| `votes_to_cases` | Undoes `cases_to_votes`: `Votes` become `Cases` again. |
| `cases_to_judges` | `Judges`: a table with one row for each judge, with how many cases the judge decided (`cases`), the judge's attributes, and the shares of the judge's votes (`vote_reversal`, `judge_dissented`, ...) and of the judge's cases of each type (`type_criminal`, ...). |
| `cases_to_courts`, `cases_to_case_types`, `cases_to_party_types` | `Courts`, `CaseTypes`, and `PartyTypes`: a row for each court, case type, or party type, with the number of cases and the means of their columns. |
| `add_scdb` | For cases of the Supreme Court, the coding of the [Supreme Court Database](https://scdb.la.psu.edu/data/), such as `scdb_issueArea`, `scdb_decisionDirection`, and `scdb_partyWinning`. |
| `cases_to_dockets`, `dockets_to_cases`, `dockets_to_votes` | `Dockets`: a row for each docket number of each case, as records kept by docket need, and `Cases` or `Votes` (a row for each judge on each docket) made from them. |
| `add_idb` | For cases of the courts of appeals (best added to `Dockets`, so each docket of a consolidated case gets its own record), the record of the appeal in the Federal Judicial Center's [Integrated Database](https://www.fjc.gov/research/idb), which [fjc-idb](https://github.com/WithPrecedent/fjc_idb) reads, such as `idb_appeal_type`, `idb_judgment_date`, `idb_pro_se_party`, and `idb_district_judge` (and, if asked, the district court's record of the case appealed). |

`compare_with_idb` (an explorer) checks a study against the Integrated
Database. It compares the study's cases as `Dockets`, since the database has a
record for each docket. One table shows how often the variables both have
(such as whether an appeal is criminal, was reversed, or was published) agree,
with the disagreements in each direction and Cohen's kappa. A second table
compares the database's appeals that the study lacks with those it has, by
circuit or district, with a test of each difference. A study never has every
appeal, so what matters is whether the missing ones differ, such as in how
often they were reversed. `idb_confusion_matrices` and `idb_missing_differences`
draw the two tables.

`courtpy` downloads the scores and the databases from their sources the first
time they are needed. To study one of these tables by itself (such as each
justice's vote in each case), start with its loader instead: `load_roster`,
`load_scdb`, `load_idb`, or `load_politics`, or their "download_" twins
(`download_biographies`, `download_scdb`, `download_idb`,
`download_politics`, and `download_jcs`), which download the latest files
first. See
[examples/cases_to_votes.ini](https://github.com/WithPrecedent/courtpy/blob/main/examples/cases_to_votes.ini)
for a study of judges' votes.

#### Describing a whole study in one file

A study is an [amos](https://github.com/WithPrecedent/amos) project, described
in one settings file. `courtpy` adds loaders to amos: `download_courtlistener`,
`load_courtlistener`, `load_lexis_nexis`, and `load_cases`. Named first in the
wrangler, a loader collects the cases (`download_courtlistener` downloads them
first), parses them, and codes them, so the project needs no other data. See
[examples/federal_appeals.ini](https://github.com/WithPrecedent/courtpy/blob/main/examples/federal_appeals.ini):

```ini
[general]
seed = 43
label = outcome_reversal

[files]
input_folder = data
interim_folder = data

[appeals_project]
appeals_workers = wrangler, analyst, critic

[wrangler]
techniques = download_courtlistener, filter_rows, keep_columns, drop_missing

[download_courtlistener_parameters]
source = courtlistener
method = bulk
courts = federal_geographic_circuits
start_date = 2019-01-01
end_date = 2019-12-31
save = cases.csv
reuse = true

[analyst]
design = experiment
criterion = roc_auc
steps = split, model
split_techniques = stratified
model_techniques = baseline, logit, random_forest

[critic]
techniques = scorecard
```

The loader finds (and saves) the cases in the input folder ("data") and saves
the coded table in the interim folder, with the whole dataset beside it
("cases.joblib"). With `reuse = true`, later runs load that dataset instead of
parsing the cases again.

Run it from a terminal with `courtpy run federal_appeals.ini --export`, or in
Python:

```python
project = courtpy.Project.create("federal_appeals.ini")
print(project.result.tables["scorecard"])
project.export()
```

`courtpy.Project` is `amos.Project`, so everything in the amos documentation
works.

#### Commands

| Command | Does |
| --- | --- |
| `courtpy key set`, `show`, `delete` | Manages your CourtListener API key. |
| `courtpy download --courts ca1 --start 2019-01-01 --end 2019-12-31` | Extracts cases from the bulk data. |
| `courtpy download --method api --courts ca1 --start 2026-09-01` | Downloads cases with the API. |
| `courtpy split FILES --folder lexis_nexis` | Divides Lexis-Nexis files of many cases. |
| `courtpy parse FOLDER --output cases.csv` | Parses and codes saved cases into a table. |
| `courtpy rules my_rules.csv` | Checks a file of rules and lists the variables it makes. |
| `courtpy run study.ini --export` | Runs a whole study. |
| `courtpy judges` | Makes the roster of judges from the Federal Judicial Center's files. |

Add `--help` to any command for its options. See the
[documentation](https://WithPrecedent.github.io/courtpy) for a tutorial, the
advanced user guide, a guide to writing rules, a guide to building a study on
courtpy, a catalog of its techniques and variables, and recipes.

## Contributing

Contributors are always welcome. Feel free to grab an [issue](https://www.github.com/WithPrecedent/courtpy/issues) to work on or make a suggested improvement. If you wish to contribute, please read the [Contribution Guide](https://www.github.com/WithPrecedent/courtpy/blob/main/CONTRIBUTING.md) and [Code of Conduct](https://www.github.com/WithPrecedent/courtpy/blob/main/CODE_OF_CONDUCT.md).

## Similar Projects

* [CourtListener](https://www.courtlistener.com) and the Free Law Project's
  tools, including [eyecite](https://github.com/freelawproject/eyecite) (which
  finds and resolves legal citations in text) and
  [juriscraper](https://github.com/freelawproject/juriscraper) (which collects
  opinions from court websites).
* [amos](https://github.com/WithPrecedent/amos), which `courtpy` uses to analyze
  the cases it parses.

## Citation

If you use `courtpy` in your research, please cite it. GitHub's "Cite this
repository" button reads the same information from
[`CITATION.cff`](https://www.github.com/WithPrecedent/courtpy/blob/main/CITATION.cff).

```bibtex
@software{yung_courtpy,
  author  = {Yung, Corey Rayburn},
  title   = {courtpy: Accessible tools for collecting, parsing, and analyzing court opinions},
  version = {0.6.1},
  year    = {2026},
  url     = {https://github.com/WithPrecedent/courtpy},
  license = {Apache-2.0}
}
```

## License

Use of this repository is authorized under the [Apache Software License 2.0](https://www.github.com/WithPrecedent/courtpy/blob/main/LICENSE).
