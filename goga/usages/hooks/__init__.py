"""Hooks zone of the usages domain — the run-level moments of sync and status.

The zone owns the fact vocabulary of the four run-level moments (the
``UsagesMoment`` identity envelope, the sync-outcome records, the
drift-projection records, the ``Completion`` marker), the read-only contexts
a subscribed hook receives, and the ``UsagesHooks`` checkpoint surface
delivering the four soft notifications ``usages/sync_started``,
``usages/sync_completed``, ``usages/status_started``, and
``usages/status_completed`` over the platform facade.

Built incrementally: each entity task added its module. With the facts, the
contexts, and the checkpoint surface landed, the thirteen contract names of
the zone are re-exported here. Importing the package imports no tool package
and enumerates nothing — the run registry builds lazily inside
``UsagesHooks``.
"""

from .contexts import StatusCompleted, StatusStarted, SyncCompleted, SyncStarted
from .events import UsagesHooks
from .facts import (
    ChangeVerdict,
    Completion,
    DepDrift,
    DriftVerdict,
    FileChange,
    SyncDepOutcome,
    SyncOutcome,
    UsagesMoment,
)

__all__: list[str] = [
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
