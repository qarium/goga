"""Facade tests of the codegraph hooks zone — the assembled node surface.

``goga/codegraph/hooks/__init__.py`` re-exports the contract names of the
zone. This suite pins the facade rule: the alphabetical ``__all__`` list,
each name resolving to the implementing class or function of its declaring
module, and the cheap construction of ``CodegraphHooks`` — no
installed-packages enumeration happens at construction.
"""

from __future__ import annotations

import goga.codegraph.hooks as zone
from goga.codegraph.hooks.amendments import NodeAmendment
from goga.codegraph.hooks.contexts import GraphValidation
from goga.codegraph.hooks.events import CodegraphHooks
from goga.codegraph.hooks.facts import GateVerdict, NodeFacts, Violation
from goga.codegraph.hooks.overlay import ToolContribution, merge_node_contributions

_IMPLEMENTING = {
    "CodegraphHooks": CodegraphHooks,
    "GateVerdict": GateVerdict,
    "GraphValidation": GraphValidation,
    "NodeAmendment": NodeAmendment,
    "NodeFacts": NodeFacts,
    "ToolContribution": ToolContribution,
    "Violation": Violation,
    "merge_node_contributions": merge_node_contributions,
}
"""The contract names mapped to the entity of the declaring module."""


def test_zone_facade_reexports_the_contract_names(pin_package_environment) -> None:
    """The facade exposes exactly the contract names, alphabetically.

    Each name resolves to the implementing class or function of its
    declaring module, and ``CodegraphHooks()`` constructs without
    enumerating the installed-packages environment.
    """
    boundary = pin_package_environment({"goga_tool_demo": ["demo"]})

    assert zone.__all__ == [
        "CodegraphHooks",
        "GateVerdict",
        "GraphValidation",
        "NodeAmendment",
        "NodeFacts",
        "ToolContribution",
        "Violation",
        "merge_node_contributions",
    ]

    for name, entity in _IMPLEMENTING.items():
        exported = getattr(zone, name)

        assert exported is entity

        if name == "merge_node_contributions":
            assert callable(exported)
        else:
            assert isinstance(exported, type)

    zone.CodegraphHooks()

    assert boundary.called is False
