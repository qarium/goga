"""Hooks zone of the schema domain — the cell-amendment and validation-gate checkpoint surface."""

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
