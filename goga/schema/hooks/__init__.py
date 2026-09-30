"""Hooks zone of the schema domain — the cell-amendment and validation-gate checkpoint surface.

The zone owns the per-cell authored-facts read view (``CellFacts`` /
``DependencyFacts``), the per-tool read-and-contribute view
(``CellAmendment``), the deterministic tools-area composition
(``ToolContribution`` / ``merge_cell_contributions``), and the
``SchemaHooks`` checkpoint surface delivering the hard ``schema/amend_cell``
action over the platform facade. The validation gate completes the
surface with the final-tree facts — ``SchemaNode`` / ``Violation`` /
``GateVerdict`` — delivered through the per-tool view
``SchemaValidation``: ``SchemaHooks.validate_schema`` carries the hard
``schema/validate_schema`` action with the walk-to-completion refinement
— every subscribed tool's hooks run, one violation is collected per
non-approving tool, and the verdict is data. The contract names of the
zone are re-exported here.
"""

from .amendments import CellAmendment
from .contexts import SchemaValidation
from .events import SchemaHooks
from .facts import CellFacts, DependencyFacts, GateVerdict, SchemaNode, Violation
from .overlay import ToolContribution, merge_cell_contributions

__all__: list[str] = [
    "CellAmendment",
    "CellFacts",
    "DependencyFacts",
    "GateVerdict",
    "SchemaHooks",
    "SchemaNode",
    "SchemaValidation",
    "ToolContribution",
    "Violation",
    "merge_cell_contributions",
]
