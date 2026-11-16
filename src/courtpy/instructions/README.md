# Instructions: the rules that parse court opinions

courtpy finds information in court opinions with rules written in CSV files,
which can be opened and changed in Excel, Google Sheets, or any spreadsheet.
Each row is one rule. You can change these files, or make your own and pass
them to courtpy (`rulebooks = my_rules.csv` in a settings file, or
`courtpy.parse(folder, rulebooks = ["federal", "my_rules.csv"])` in Python).

| File | What it does |
| --- | --- |
| `lexis_nexis.csv` | Divides a Lexis-Nexis case into its header and opinions, and finds each part of the header (the parties, court, docket number, dates, history, counsel, disposition, citation, judges, and author). CourtListener cases do not need it, because CourtListener stores those parts separately. |
| `federal/header.csv` | Finds variables in the parts of the header: the court's number, each party's role, the agency involved, the disposition, the counsel, publication, and the names of the judges. When a case has no roles or judges in its header (as recent CourtListener cases often do not), it reads them from the caption and the "Before ..." line at the start of the opinion. Always applied. |
| `federal/general.csv` | Finds the decision that the opinion states ("AFFIRMED." or "we reverse"), its words about dispositions anywhere, procedure (such as pro se, mandamus, and mootness), and standards of review. Always applied. |
| `federal/citations.csv` | Finds citations to cases, statutes, regulations, the Constitution, legislative materials, and other sources (`citations_...`). |
| `federal/civil.csv` | Finds the civil issues discussed (`civil_...`). |
| `federal/constitutional.csv` | Finds the constitutional issues discussed (`constitutional_...`). |
| `federal/criminal.csv` | Finds the criminal issues discussed (`criminal_...`). |
| `federal/agencies.csv` | Finds every federal agency that the caption, the history, or the opinion names (`agencies`), by its name or a common abbreviation, as the agencies' names separated by commas (such as "Internal Revenue Service, United States Tax Court"). The agencies are those of the Federal Judicial Center's Integrated Database (as [fjc-idb](https://github.com/WithPrecedent/fjc_idb) lists them), and each rule's note gives fjc-idb's code. |

`header` and `general` are applied to every case, whether or not they are
named. The others can be chosen by name: `rulebooks = civil, criminal` in a
settings file (or `courtpy.parse(folder, rulebooks = ["civil", "criminal"])`
in Python) parses with `header`, `general`, `civil`, and `criminal`. The
"federal" rulebook (the default) is all seven `federal` files, in the order
above. A file named more than once is applied once.

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
| `separator` | What goes between several values in one cell, for `categories`, `matches`, and `names` rules. Optional: a comma and a space if blank. courtpy's `names` and `matches` rules use "; ". |
| `note` | Anything you want to say about the rule. courtpy ignores it. |

## The kinds of rules

| Kind | Makes | Example |
| --- | --- | --- |
| `flags` | TRUE if the pattern appears, and otherwise FALSE. | `opinion,criminal_firearm,flags,[Pp]ossession of (a )?[Ff]irearm` |
| `counts` | The number of times the pattern appears. | `opinion,habeas_mentions,counts,habeas` |
| `matches` | Every match, separated by the `separator`. | `opinion,citations_case,matches,\d+ (?:F\.(?:[23]d\|4th)\|U\.S\.) \d+,,,; ` |
| `match` | The first match. A later rule can search it as a new section of text. | `header,counsel,match,\nCOUNSEL\:.*?(?=\n\n)` |
| `category` | The rule's `value` if the pattern appears. The first rule for a name that matches is used. | `court,court_num,category,FIRST CIRCUIT,1` |
| `categories` | The `value` of every rule for the name whose pattern appears, once each, in the order of the rules and separated by the `separator` (such as "Internal Revenue Service, United States Tax Court"). A value cannot have the separator. | `opinion,agencies,categories,NLRB\b(?<!\wNLRB),National Labor Relations Board` |
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
  are one cell of text, with "; " (or, for `agencies`, ", ") between them,
  such as "LYNCH; HOWARD; THOMPSON". The `split_values` technique turns them
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
| `party1`, `party2` | Made by the `split` rule in `federal/header.csv`. | The same. |
| `court` | The court's line in the header. | The court's full name. |
| `docket_number` | The docket line. | The docket number (if dockets were downloaded). |
| `citation` | The citation line. | The case's citations. |
| `dates` | Every line with a date. | (Dates come from CourtListener's data.) |
| `history` | "PRIOR HISTORY". | The procedural history and the court appealed from. |
| `future` | "SUBSEQUENT HISTORY". | (None.) |
| `notice` | "NOTICE". | (None: publication comes from CourtListener's precedential status.) |
| `counsel` | "COUNSEL". | The attorneys. |
| `disposition` | "DISPOSITION". | The disposition (often blank). |
| `judges` | "JUDGES". | The judges. |
| `opinion_by` | "OPINION BY". | The authors of the majority (or lead) opinions. |
| `concurring_lines`, `dissenting_lines` | Lines about concurrences and dissents. | The authors of concurrences and dissents. |
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
