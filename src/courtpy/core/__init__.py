"""The parts of courtpy that every other part shares.

These modules hold what is not a source of cases, a step of the wrangler, or
a table of reference data: the case and its tables (`cases`), options,
secrets (the CourtListener API key), and utilities. Each module can also be
imported from `courtpy` itself (such as `courtpy.cases`).

"""

from __future__ import annotations
