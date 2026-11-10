"""Hooks zone of the codegraph domain — the node-amendment and validation-gate checkpoint surface."""

from .amendments import NodeAmendment
from .contexts import GraphValidation
from .events import CodegraphHooks
from .facts import GateVerdict, NodeFacts, Violation
from .overlay import ToolContribution, merge_node_contributions

__all__: list[str] = [
    "CodegraphHooks",
    "GateVerdict",
    "GraphValidation",
    "NodeAmendment",
    "NodeFacts",
    "ToolContribution",
    "Violation",
    "merge_node_contributions",
]
