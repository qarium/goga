"""Facade tests of the drift hooks zone — the assembled run surface.

``goga/drift/hooks/__init__.py`` re-exports the contract names of the
zone. This suite pins the facade rule: the alphabetical ``__all__`` list,
each name resolving to the implementing class or function of its declaring
module, and the cheap construction of ``DriftHooks`` — no
installed-packages enumeration happens at construction.
"""

from __future__ import annotations

import goga.drift.hooks as zone
from goga.drift.hooks.amendments import EntryAmendment, ReportAmendment
from goga.drift.hooks.events import DriftHooks
from goga.drift.hooks.facts import DriftFilters, EntryFacts, ReportEntry, RunCompletion, RunOutcome
from goga.drift.hooks.overlay import ToolContribution, merge_entry_contributions

_IMPLEMENTING = {
    "DriftFilters": DriftFilters,
    "DriftHooks": DriftHooks,
    "EntryAmendment": EntryAmendment,
    "EntryFacts": EntryFacts,
    "ReportAmendment": ReportAmendment,
    "ReportEntry": ReportEntry,
    "RunCompletion": RunCompletion,
    "RunOutcome": RunOutcome,
    "ToolContribution": ToolContribution,
    "merge_entry_contributions": merge_entry_contributions,
}
"""The contract names mapped to the entity of the declaring module."""


def test_zone_facade_reexports_the_contract_names(pin_package_environment) -> None:
    """The facade exposes exactly the contract names, alphabetically.

    Each name resolves to the implementing class or function of its
    declaring module, and ``DriftHooks()`` constructs without
    enumerating the installed-packages environment.
    """
    boundary = pin_package_environment({"goga_tool_demo": ["demo"]})

    assert zone.__all__ == [
        "DriftFilters",
        "DriftHooks",
        "EntryAmendment",
        "EntryFacts",
        "ReportAmendment",
        "ReportEntry",
        "RunCompletion",
        "RunOutcome",
        "ToolContribution",
        "merge_entry_contributions",
    ]

    for name, entity in _IMPLEMENTING.items():
        exported = getattr(zone, name)

        assert exported is entity

        if name == "merge_entry_contributions":
            assert callable(exported)
        else:
            assert isinstance(exported, type)

    zone.DriftHooks()

    assert boundary.called is False
