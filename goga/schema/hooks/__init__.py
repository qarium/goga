"""Hooks zone of the schema domain — the cell-amendment checkpoint surface.

The zone owns the per-cell authored-facts read view (``CellFacts`` /
``DependencyFacts``), the per-tool read-and-contribute view
(``CellAmendment``), the deterministic tools-area composition
(``ToolContribution`` / ``merge_cell_contributions``), and the
``SchemaHooks`` checkpoint surface delivering the hard ``schema/amend_cell``
action over the platform facade. The six contract names of the zone are
re-exported here.
"""

from .amendments import CellAmendment
from .events import SchemaHooks
from .facts import CellFacts, DependencyFacts
from .overlay import ToolContribution, merge_cell_contributions

__all__: list[str] = [
    "CellAmendment",
    "CellFacts",
    "DependencyFacts",
    "SchemaHooks",
    "ToolContribution",
    "merge_cell_contributions",
]
