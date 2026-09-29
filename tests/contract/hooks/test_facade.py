"""Facade tests of the contract hooks zone — the assembled checkpoint surface.

``goga/contract/hooks/__init__.py`` re-exports exactly the eight contract
names of the zone. This suite pins the facade rule: the sorted ``__all__``
list, each name resolving to the entity of its declaring module.
"""

from __future__ import annotations

import goga.contract.hooks as facade
import goga.contract.hooks.events
from goga.contract.hooks.amendments import ContractAmendment
from goga.contract.hooks.events import ContractHooks
from goga.contract.hooks.facts import CellFacts, FormFacts, MemberFacts, TypeFacts
from goga.contract.hooks.overlay import ToolContribution, merge_type_contributions

_IMPLEMENTING = {
    "CellFacts": CellFacts,
    "ContractAmendment": ContractAmendment,
    "ContractHooks": ContractHooks,
    "FormFacts": FormFacts,
    "MemberFacts": MemberFacts,
    "ToolContribution": ToolContribution,
    "TypeFacts": TypeFacts,
    "merge_type_contributions": merge_type_contributions,
}
"""The eight contract names mapped to the entity of the declaring module."""


def test_facade_reexports_the_zone_contract_names() -> None:
    """The facade exposes exactly the eight contract names, sorted.

    Each name resolves to the entity of its declaring module — the facade
    re-exports, it never defines.
    """
    assert sorted(facade.__all__) == [
        "CellFacts",
        "ContractAmendment",
        "ContractHooks",
        "FormFacts",
        "MemberFacts",
        "ToolContribution",
        "TypeFacts",
        "merge_type_contributions",
    ]

    assert facade.ContractHooks is goga.contract.hooks.events.ContractHooks

    for name, entity in _IMPLEMENTING.items():
        exported = getattr(facade, name)

        assert exported is entity

        if name == "merge_type_contributions":
            assert callable(exported)
        else:
            assert isinstance(exported, type)

    assert facade.__all__ == sorted(facade.__all__)
