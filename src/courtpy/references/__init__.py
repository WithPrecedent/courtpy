"""Tables of reference data that describe something other than cases.

Each module downloads, reads, and merges one kind of reference data: the
judges (`judges`), the federal courts (`courts`), the Supreme Court Database
(`scdb`), the Federal Judicial Center's Integrated Database (`fjc_idb`), the
Judicial Common Space (`jcs`), the political context of each case
(`politics`), and scores of judges and courts from training data
(`scores`). Each can also be imported from `courtpy` itself (such as
`courtpy.judges`).

"""

from __future__ import annotations
