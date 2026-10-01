"""Facade tests of the usages hooks zone — the assembled cell surface.

``goga/usages/hooks/__init__.py`` re-exports exactly the thirteen contract
names of the zone. This suite pins the facade rule: the alphabetical
``__all__`` list, each name resolving to the implementing class or enum of
its declaring module, and the cheap construction of ``UsagesHooks`` — no
installed-packages enumeration happens at construction.
"""

from __future__ import annotations

import goga.usages.hooks as zone
from goga.usages.hooks.contexts import StatusCompleted, StatusStarted, SyncCompleted, SyncStarted
from goga.usages.hooks.events import UsagesHooks
from goga.usages.hooks.facts import (
    ChangeVerdict,
    Completion,
    DepDrift,
    DriftVerdict,
    FileChange,
    SyncDepOutcome,
    SyncOutcome,
    UsagesMoment,
)

_IMPLEMENTING = {
    "ChangeVerdict": ChangeVerdict,
    "Completion": Completion,
    "DepDrift": DepDrift,
    "DriftVerdict": DriftVerdict,
    "FileChange": FileChange,
    "StatusCompleted": StatusCompleted,
    "StatusStarted": StatusStarted,
    "SyncCompleted": SyncCompleted,
    "SyncDepOutcome": SyncDepOutcome,
    "SyncOutcome": SyncOutcome,
    "SyncStarted": SyncStarted,
    "UsagesHooks": UsagesHooks,
    "UsagesMoment": UsagesMoment,
}
"""The thirteen contract names mapped to the entity of the declaring module."""


def test_zone_facade_exposes_the_thirteen_contract_names(pin_package_environment) -> None:
    """The facade exposes exactly the thirteen contract names, alphabetically.

    Each name resolves on the zone object to the implementing class or enum
    of its declaring module, and ``UsagesHooks()`` constructs without
    enumerating the installed-packages environment.
    """
    boundary = pin_package_environment({})

    assert zone.__all__ == [
        "ChangeVerdict",
        "Completion",
        "DepDrift",
        "DriftVerdict",
        "FileChange",
        "StatusCompleted",
        "StatusStarted",
        "SyncCompleted",
        "SyncDepOutcome",
        "SyncOutcome",
        "SyncStarted",
        "UsagesHooks",
        "UsagesMoment",
    ]

    assert zone.UsagesHooks is not None
    assert callable(zone.UsagesHooks)

    for name, entity in _IMPLEMENTING.items():
        exported = getattr(zone, name)

        assert exported is entity

        assert isinstance(exported, type)

    zone.UsagesHooks()

    assert boundary.called is False
