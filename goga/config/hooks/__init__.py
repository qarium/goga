"""Hooks zone of the config domain — the amendment checkpoint surface.

The zone owns the per-tool read-and-amend view of the project-configuration
load moment (``ConfigAmendment`` with its buffered ``PathAmendment``
entries), the deterministic in-memory amendment merge
(``merge_config_amendments`` composing ``ToolAmendment`` contributions into
a ``ConfigOverlay`` of ``AppliedAmendment`` records), and the
``ConfigHooks`` checkpoint surface delivering the hard
``config/amend_config`` action over the platform facade.

Built incrementally: each entity task added its module. With the amendment
view, the overlay merge, and the checkpoint surface landed, the seven
contract names of the zone are re-exported here.
"""

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
