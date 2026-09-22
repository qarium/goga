"""Facade tests of the config hooks zone — the assembled cell surface.

``goga/config/hooks/__init__.py`` re-exports exactly the seven contract
names of the zone. This suite pins the facade rule: the alphabetical
``__all__`` list, each name resolving to the implementing class or function
of its declaring module, and the cheap construction of ``ConfigHooks`` —
no installed-packages enumeration happens at construction.
"""

from __future__ import annotations

import goga.config.hooks as zone
from goga.config.hooks.amendments import ConfigAmendment, PathAmendment
from goga.config.hooks.events import ConfigHooks
from goga.config.hooks.overlay import (
    AppliedAmendment,
    ConfigOverlay,
    ToolAmendment,
    merge_config_amendments,
)

_IMPLEMENTING = {
    "AppliedAmendment": AppliedAmendment,
    "ConfigAmendment": ConfigAmendment,
    "ConfigHooks": ConfigHooks,
    "ConfigOverlay": ConfigOverlay,
    "PathAmendment": PathAmendment,
    "ToolAmendment": ToolAmendment,
    "merge_config_amendments": merge_config_amendments,
}
"""The seven contract names mapped to the entity of the declaring module."""


def test_facade_all_exactly_seven_names(pin_package_environment) -> None:
    """The facade exposes exactly the seven contract names, alphabetically.

    Each name resolves to the implementing class or function of its
    declaring module, and ``ConfigHooks()`` constructs without enumerating
    the installed-packages environment.
    """
    boundary = pin_package_environment({})

    assert zone.__all__ == [
        "AppliedAmendment",
        "ConfigAmendment",
        "ConfigHooks",
        "ConfigOverlay",
        "PathAmendment",
        "ToolAmendment",
        "merge_config_amendments",
    ]

    for name, entity in _IMPLEMENTING.items():
        exported = getattr(zone, name)

        assert exported is entity

        if name == "merge_config_amendments":
            assert callable(exported)
        else:
            assert isinstance(exported, type)

    zone.ConfigHooks()

    assert boundary.called is False
