"""Facade tests of the schema hooks zone — the assembled cell surface.

``goga/schema/hooks/__init__.py`` re-exports the contract names of the
zone. This suite pins the facade rule: the alphabetical ``__all__`` list,
each name resolving to the implementing class or function of its declaring
module, and the cheap construction of ``SchemaHooks`` — no installed-packages
enumeration happens at construction.
"""

from __future__ import annotations

from dataclasses import is_dataclass

import goga.schema.hooks as zone
from goga.schema.hooks.amendments import CellAmendment
from goga.schema.hooks.contexts import SchemaValidation
from goga.schema.hooks.events import SchemaHooks
from goga.schema.hooks.facts import (
    CellFacts,
    DependencyFacts,
    GateVerdict,
    SchemaNode,
    Violation,
)
from goga.schema.hooks.overlay import ToolContribution, merge_cell_contributions

from tests.conftest import is_kw_only_dataclass

_IMPLEMENTING = {
    "CellAmendment": CellAmendment,
    "CellFacts": CellFacts,
    "DependencyFacts": DependencyFacts,
    "GateVerdict": GateVerdict,
    "SchemaHooks": SchemaHooks,
    "SchemaNode": SchemaNode,
    "SchemaValidation": SchemaValidation,
    "ToolContribution": ToolContribution,
    "Violation": Violation,
    "merge_cell_contributions": merge_cell_contributions,
}
"""The contract names mapped to the entity of the declaring module."""


def test_zone_facade_reexports_the_contract_names(pin_package_environment) -> None:
    """The facade exposes exactly the contract names, alphabetically.

    Each name resolves to the implementing class or function of its
    declaring module, and ``SchemaHooks()`` constructs without enumerating
    the installed-packages environment.
    """
    boundary = pin_package_environment({"goga_tool_demo": ["demo"]})

    assert zone.__all__ == [
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

    for name, entity in _IMPLEMENTING.items():
        exported = getattr(zone, name)

        assert exported is entity

        if name == "merge_cell_contributions":
            assert callable(exported)
        else:
            assert isinstance(exported, type)

    zone.SchemaHooks()

    assert boundary.called is False


def test_facade_reexports_schema_gate_surface() -> None:
    """The five gate names import from the zone facade as one surface.

    Each name resolves to the entity of its declaring module and sits in
    ``__all__``, and the three fact records — ``SchemaNode``,
    ``Violation``, ``GateVerdict`` — are frozen ``kw_only`` dataclasses:
    the delivered tree facts and the collected verdict are read-only
    records, never writable buffers (the buffer lives on
    ``SchemaValidation`` alone).
    """
    from goga.schema.hooks import GateVerdict, SchemaHooks, SchemaNode, SchemaValidation, Violation

    implementing = {
        "GateVerdict": GateVerdict,
        "SchemaHooks": SchemaHooks,
        "SchemaNode": SchemaNode,
        "SchemaValidation": SchemaValidation,
        "Violation": Violation,
    }

    for name, entity in implementing.items():
        exported = getattr(zone, name)

        assert exported is entity
        assert name in zone.__all__

    for facts in (SchemaNode, Violation, GateVerdict):
        assert is_dataclass(facts)
        assert facts.__dataclass_params__.frozen is True
        assert is_kw_only_dataclass(facts)
