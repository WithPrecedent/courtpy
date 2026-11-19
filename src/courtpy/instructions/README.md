# Instructions: the rules that parse court opinions

courtpy finds information in court opinions with rules written in CSV files,
which can be opened and changed in Excel, Google Sheets, or any spreadsheet.
Each row is one rule. You can change these files, or make your own and pass
them to courtpy (`rulebooks = my_rules.csv` in a settings file, or
`courtpy.parse(folder, rulebooks = ["federal", "my_rules.csv"])` in Python).

The rules are in three folders:

* `general` has the rules that fit opinions of any jurisdiction.
* `federal` has the rules that fit only federal opinions. A file here adds
  to the `general` file of the same name and does not repeat its rules. A
  topic with no federal rules (such as citations) has no file here.
* `lexis_nexis` has the rules that divide a Lexis-Nexis case into its parts,
  with a file for each kind of court (`federal_appellate.csv`, for the
  federal courts of appeals).

Two files of `federal` are tables rather than rules:

* `courts.csv` has a row for each federal court: courtpy's number for it,
  its name, its level, its circuit, CourtListener's id for it, and patterns
  of the names that the Federal Judicial Center and opinions use for it (see
  `courtpy.courts`). `add_circuit` finds each case's circuit with it.
* `presidents.csv` has the term of each president, with the president's
  party (-1 for Democratic and 1 for Republican). `add_executive` and
  `courtpy.politics.presidents` read it, so a new president can be added to
  it.

| Topic | Files | What it does |
| --- | --- | --- |
| `lexis_nexis` | `lexis_nexis/federal_appellate.csv` | Divides a Lexis-Nexis case into its header and opinions, and finds each part of the header (the parties, court, docket number, dates, history, counsel, disposition, citation, judges, and author). CourtListener cases do not need it, because CourtListener stores those parts separately. |
| `header` | `general/header.csv` | Finds variables in the parts of the header: the court's number, each party's role, the agency involved, the disposition, the counsel, publication, and the names of the judges. When a case has no roles or judges in its header (as recent CourtListener cases often do not), it reads them from the caption and the "Before ..." line at the start of the opinion. Always applied. |
| `general` | `general/general.csv` | Finds the decision that the opinion states ("AFFIRMED." or "we reverse"), its words about dispositions anywhere, procedure (such as pro se, mandamus, and mootness), and standards of review. Always applied. |
| `citations` | `general/citations.csv` | Finds citations to cases, statutes, regulations, the Constitution, legislative materials, and other sources (`citations_...`). |
| `civil` | `general/civil.csv`, `federal/civil.csv` | Finds the civil issues discussed: general civil issues (`civil_...`), torts (`tort_...`), contracts (`contract_...`), intellectual property (`ip_...`), and writs (`writ_...`). Each prefix is a case type (see `code_case_type`), so a new prefix (such as `immigration_`) is a case type too. |
| `constitutional` | `general/constitutional.csv` | Finds the constitutional issues discussed (`constitutional_...`). |
| `criminal` | `general/criminal.csv`, `federal/criminal.csv` | Finds the criminal issues discussed (`criminal_...`). |
| `review` | `federal/review.csv` | Finds what kind of review an appeal is: from a federal district court (`review_district`), of an agency (`review_agency`), or of the Board of Immigration Appeals or an immigration judge (`review_immigration`). For an appeal from a district court, it finds the district judge as the opening names them (`district_text`) and their name (`district_judges`). |
| `agencies` | `federal/agencies.csv` | Finds every federal agency that the caption, the history, or the opinion names (`agencies`), by its name or a common abbreviation, as the agencies' names separated by "; " (such as "Internal Revenue Service; United States Tax Court"). The agencies are those of the Federal Judicial Center's Integrated Database (as [fjc-idb](https://github.com/WithPrecedent/fjc_idb) lists them), and each rule's note gives fjc-idb's code. |

Each topic's rules are its `general` file and then its `federal` file, in
that order. `header` and `general` are applied to every case, whether or not
they are named. The others can be chosen by name: `rulebooks = civil,
criminal` in a settings file (or `courtpy.parse(folder, rulebooks = ["civil",
"criminal"])` in Python) parses with `header`, `general`, `civil`, and
`criminal`. The "federal" rulebook (the default) is every topic but
`lexis_nexis`, in the order above. A file named more than once is applied
once.

## The columns

The files use the layout of [amos](https://WithPrecedent.github.io/amos)'s
`parse_all` rulebooks, which courtpy uses to apply them. (Files in courtpy's
older layout, with `target`, `variable`, `ignorecase`, and `dotall` columns
and the kinds `flag`, `count`, `label`, `labels`, `section`, `excerpts`, and
`remove`, still work: `amos` reads them as the rules they stand for.)

| Column | Meaning |
| --- | --- |
| `column` | The section of text to search, such as `opinion`, `party1`, or `disposition`. List several, separated by commas, to search each of them. |
| `name` | The name of the column that the rule makes. Rules with the same name are combined. A `split` rule names two or more. |
| `kind` | What the rule does (see below). |
| `pattern` | A [regular expression](https://docs.python.org/3/howto/regex.html) to search for. Plain words work too. |
| `value` | For a `category` or `categories` rule, the value to record. Otherwise leave it blank. |
| `flags` | Any of `ignorecase` (to ignore the difference between capital and lower-case letters), `dotall` (for `.` in the pattern to also match line breaks), `multiline`, and `verbose`, separated by commas. Optional. |
| `separator` | What goes between several values in one cell, for `categories`, `matches`, and `names` rules. Optional: a comma and a space if blank. Every courtpy rule that makes several values uses "; ", since names and agencies can have commas in them. |
| `note` | Anything you want to say about the rule. courtpy ignores it. |

## The kinds of rules

| Kind | Makes | Example |
| --- | --- | --- |
| `flags` | TRUE if the pattern appears, and otherwise FALSE. | `opinion,criminal_firearm,flags,[Pp]ossession of (a )?[Ff]irearm` |
| `counts` | The number of times the pattern appears. | `opinion,habeas_mentions,counts,habeas` |
| `matches` | Every match, separated by the `separator`. | `opinion,citations_case,matches,\d+ (?:F\.(?:[23]d\|4th)\|U\.S\.) \d+,,,; ` |
| `match` | The first match. A later rule can search it as a new section of text. | `header,counsel,match,\nCOUNSEL\:.*?(?=\n\n)` |
| `category` | The rule's `value` if the pattern appears. The first rule for a name that matches is used. | `court,court_num,category,FIRST CIRCUIT,1` |
| `categories` | The `value` of every rule for the name whose pattern appears, once each, in the order of the rules and separated by the `separator` (such as "Internal Revenue Service; United States Tax Court"). A value cannot have the separator. | `opinion,agencies,categories,NLRB\b(?<!\wNLRB),National Labor Relations Board` |
| `names` | The names in the text, found by splitting it wherever the pattern matches, and separated by the `separator`. The pattern should match what comes between names: titles, filler words, and punctuation. | `judges,panel_judges,names,\b(?:BEFORE\|CIRCUIT\|JUDGES?\|AND)\b\|[,;:],,,; ` |
| `split` | New sections, named in `name`: the text before and after the first match. | `party,"party1, party2",split,\Wv\.\W` |
| `replace` | The text with every match replaced by the `value` (a blank `value` removes the matches). Without a `name`, it changes the section for the rules below it. | `party1,,replace,\bET AL\b` |

`amos` has more kinds (such as `fields`, which makes a column for each
labeled part of a text); see its `amos.parsers` module.

## Things to know

* **Rules run from top to bottom.** A rule can search a section made by a rule
  above it (for example, `party1` and `party2` exist only after the `split`
  rule that makes them). Each rule searches every case at once.
* **Text is put on one line first.** Before the `federal` rules run, every
  section except those whose names end in `_lines` has its line breaks and
  extra spaces replaced with single spaces, so that a phrase broken across two
  lines is still found. (The `lexis_nexis` rules run before this, so they can
  use line breaks, written `\n`.)
* **Names are cleaned.** A `names` rule makes the text upper-case and removes
  periods and apostrophes before splitting it, so write its pattern in
  capital letters.
* **Several values are text.** The names, matches, and categories of a case
  are one cell of text, with "; " between them, such as
  "LYNCH; HOWARD; THOMPSON". The `split_values` technique turns them
  into lists or into a column for each value, and `amos`'s `lists_to_rows`
  into a row for each value.
* **Rules that start with letters are fast.** Python finds a pattern that
  begins with letters by searching for them, which is many times faster
  than trying the pattern at every character. A pattern that begins with
  `\b`, a group, or a class, or that ignores case (the `ignorecase` flag), loses
  that. So `agencies.csv` matches with case, writing a name in its
  capitalized form and in capitals (`Federal\s+Trade\s+Commission|FEDERAL\s+TRADE\s+COMMISSION`),
  and puts the check that an abbreviation is a whole word after its letters
  (`NLRB\b(?<!\wNLRB)` rather than `\bNLRB\b`).
* **Missing sections are not errors.** If a case has no section that a rule
  searches (such as `future` in a CourtListener case), a flag is FALSE, a
  count is 0, and the other kinds are blank.
* **A `match` rule does not replace a section made by a rule above it.** So
  two `match` rules for one name are a first choice and a fallback: the
  `federal` rules make `panel_text` from the opinion's "Before ..." line,
  and only otherwise from the header's judges.
* **Three sets of variables record the disposition.** `disposition_...` come
  from the header's disposition, `decision_...` from the decision that the
  opinion states ("AFFIRMED.", "VACATED AND REMANDED.", or "we reverse"),
  and `opinion_...` from those words anywhere in the opinion, which may be
  about an earlier decision or a standard of review ("we will reverse only
  if"). The `code_outcome` coder uses the first of the three that a case has.
* **Check your rules** with `courtpy rules my_rules.csv` in a terminal. It
  reports any row that is not a valid rule, by its row number, and lists the
  columns the rules make.
* **Save files as CSV in UTF-8** ("CSV UTF-8" in Excel), so that symbols such as
  `§` are kept.

## Sections of text

These sections can be targets in the `federal` rules (and your own):

| Section | Lexis-Nexis | CourtListener |
| --- | --- | --- |
| `party` | The caption. | The full case name. |
| `party1`, `party2` | Made by the `split` rule in `general/header.csv`. | The same. |
| `court` | The court's line in the header. | The court's full name. |
| `docket_number` | The docket line. | The docket number (if dockets were downloaded). |
| `citation` | The citation line. | The case's citations. |
| `dates` | Every line with a date, with "; " between them. | (Dates come from CourtListener's data.) |
| `history` | "PRIOR HISTORY". | The procedural history and the court appealed from. |
| `future` | "SUBSEQUENT HISTORY". | (None.) |
| `notice` | "NOTICE". | (None: publication comes from CourtListener's precedential status.) |
| `counsel` | "COUNSEL". | The attorneys. |
| `disposition` | "DISPOSITION". | The disposition (often blank). |
| `judges` | "JUDGES". | The judges. |
| `opinion_by` | "OPINION BY". | The authors of the majority (or lead) opinions. |
| `concurring_lines`, `dissenting_lines` | Lines about concurrences and dissents, with "; " between them. | The authors of concurrences and dissents. |
| `posture`, `syllabus` | (None.) | CourtListener's posture and syllabus. |
| `opinion` | Everything after the line "OPINION". | The text of every opinion, the majority first. |

The `federal` rules make these sections from the opinion, which your own
rules (below them) can search too:

| Section | Holds |
| --- | --- |
| `opening_lines` | The first 4,000 characters of the opinion (not kept in the table). |
| `caption` | The header's caption, if it names an appellant or appellee. Otherwise, the caption in the opinion's opening, from the first party's role through the second's (such as "Plaintiff-Appellee, v. JOHN DOE, Defendant-Appellant"). |
| `caption1`, `caption2` | The caption before and after "v.", in the order of `party1` and `party2`. |
| `panel_text` | The panel as the opinion's opening names it ("Before SMITH, JONES, and BROWN, Circuit Judges"). Otherwise, the `judges` section. |
| `decision` | The decision as the opinion states it. |

## Rules of your own

A file of your own can be named by its path wherever a rulebook can be
named. To name it like a built-in rulebook instead (`rulebooks = federal,
review`), make each file in a folder a rulebook with
`courtpy.rules.register_rulebooks(folder)` when your study's package is
imported. Each file is a rulebook named for its stem, and each rulebook is
also a technique (such as `parse_review`). With several folders, each topic
applies the file of the same name in each folder, in order, as courtpy
applies its `general` and then its `federal` files. See
[Building a Study](https://WithPrecedent.github.io/courtpy/studies/).
