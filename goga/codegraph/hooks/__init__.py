"""Hooks zone of the codegraph domain — the node-amendment and validation-gate checkpoint surface.

The zone is built incrementally — each entity task of the extension adds its
module and its names to the facade.
"""

from .amendments import NodeAmendment
from .contexts import GraphValidation
from .facts import GateVerdict, NodeFacts, Violation

__all__: list[str] = [
    "GateVerdict",
    "GraphValidation",
    "NodeAmendment",
    "NodeFacts",
    "Violation",
]
