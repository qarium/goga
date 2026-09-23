"""Facade tests of the schema hooks zone — the assembled cell surface.

``goga/schema/hooks/__init__.py`` re-exports exactly the six contract
names of the zone. This suite pins the facade rule: the alphabetical
``__all__`` list, each name resolving to the implementing class or
function of its declaring module, and the cheap construction of
``SchemaHooks`` — no installed-packages enumeration happens at
construction.
"""

from __future__ import annotations

import goga.schema.hooks as zone
from goga.schema.hooks.amendments import CellAmendment
from goga.schema.hooks.events import SchemaHooks
from goga.schema.hooks.facts import CellFacts, DependencyFacts
from goga.schema.hooks.overlay import ToolContribution, merge_cell_contributions

_IMPLEMENTING = {
    "CellAmendment": CellAmendment,
    "CellFacts": CellFacts,
    "DependencyFacts": DependencyFacts,
    "SchemaHooks": SchemaHooks,
    "ToolContribution": ToolContribution,
    "merge_cell_contributions": merge_cell_contributions,
}
"""The six contract names mapped to the entity of the declaring module."""


def test_zone_facade_reexports_six_contract_names(pin_package_environment) -> None:
    """The facade exposes exactly the six contract names, alphabetically.

    Each name resolves to the implementing class or function of its
    declaring module, and ``SchemaHooks()`` constructs without enumerating
    the installed-packages environment.
    """
    boundary = pin_package_environment({"goga_tool_demo": ["demo"]})

    assert zone.__all__ == [
        "CellAmendment",
        "CellFacts",
        "DependencyFacts",
        "SchemaHooks",
        "ToolContribution",
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
