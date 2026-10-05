"""Hooks zone of the config domain — the amendment checkpoint surface."""

from .amendments import ConfigAmendment, PathAmendment
from .events import ConfigHooks
from .overlay import AppliedAmendment, ConfigOverlay, ToolAmendment, merge_config_amendments

__all__: list[str] = [
    "AppliedAmendment",
    "ConfigAmendment",
    "ConfigHooks",
    "ConfigOverlay",
    "PathAmendment",
    "ToolAmendment",
    "merge_config_amendments",
]
