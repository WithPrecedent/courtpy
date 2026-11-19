"""courtpy's steps of the `amos` wrangler, which turn opinions into a table.

`loaders` collect cases into a project, `rules` and `parsers` find
variables in their text, `coders` code what the rules found (such as
who won), and `shapers` summarize cases by court, case type, and party
type. Each can also be imported from `courtpy` itself (such as
`courtpy.parsers`).

"""

from __future__ import annotations
