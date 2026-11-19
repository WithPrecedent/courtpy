"""Tables of reference data that describe something other than cases.

Each module downloads, reads, and merges one kind of reference data: the
judges (`judges`), the Supreme Court Database (`scdb`), the Federal Judicial
Center's Integrated Database (`fjc_idb`), the Judicial Common Space
(`jcs`), and the political context of each year (`politics`). Each can also
be imported from `courtpy` itself (such as `courtpy.judges`).

"""

from __future__ import annotations
