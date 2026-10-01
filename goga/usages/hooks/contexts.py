"""The read-only contexts of the usages hooks zone.

The entities declared in the cell CODEMANIFEST with ``location:
contexts.py``: the four context entities a subscribed hook receives —
``SyncStarted``, ``StatusStarted``, ``SyncCompleted``,
``StatusCompleted``. Facts only, no methods: every context is built by
``UsagesHooks`` from the values the emitting operation passes, and the
platform's delivery proxy closes attribute writes — a hook observes and
cannot alter anything. The crash invariants (``success`` False whenever
crashed, ``reason`` present exactly when crashed) are guaranteed by the
emitting operations, not enforced here — facts, not police.
"""

from __future__ import annotations

from dataclasses import dataclass

from .facts import Completion, DepDrift, SyncDepOutcome, UsagesMoment


@dataclass(frozen=True, kw_only=True)
class SyncStarted:
    """The read-only context of the sync start — what the sync run was asked to do.

    Attributes:
        moment: The identity envelope of the run.
        force: The force flag as applied by the run.

    Requirements:
        read-only facts of a starting operation — a hook observes and
        cannot alter anything.
    """

    moment: UsagesMoment
    force: bool


@dataclass(frozen=True, kw_only=True)
class StatusStarted:
    """The read-only context of the status start — what the status run was asked to do.

    Attributes:
        moment: The identity envelope of the run.

    Requirements:
        read-only facts of a starting operation — a hook observes and
        cannot alter anything.
    """

    moment: UsagesMoment


@dataclass(frozen=True, kw_only=True)
class SyncCompleted:
    """The read-only context of the sync completion — the per-dep outcomes of the run.

    Attributes:
        moment: The identity envelope of the run.
        deps: One outcome record per matched dep, in iteration order;
            empty on a no-op run.
        success: The run's overall success; False whenever the marker is
            crashed.
        completion: The terminal marker — finished or crashed.
        reason: The credential-free crash reason; present exactly when
            the marker is crashed.

    Requirements:
        read-only facts of a completed operation — a hook observes the
        outcome and cannot alter it; ``success`` is False whenever the
        marker is crashed — a crash is an overall failure; ``reason`` is
        present exactly when the marker is crashed; on a crash the
        outcome records are the best facts known at the break-off point.
    """

    moment: UsagesMoment
    deps: list[SyncDepOutcome]
    success: bool
    completion: Completion
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class StatusCompleted:
    """The read-only context of the status completion — the changed-set records of the check.

    Attributes:
        moment: The identity envelope of the run.
        changed: One changed-set record per matched dep whose verdict is
            not up to date; empty when no matched dep drifted.
        success: The check's overall outcome; no drift exactly when the
            changed set is empty; False whenever the marker is crashed.
        completion: The terminal marker — finished or crashed.
        reason: The credential-free crash reason; present exactly when
            the marker is crashed.

    Requirements:
        read-only facts of a completed check; ``success`` is False
        whenever the marker is crashed; ``reason`` is present exactly
        when the marker is crashed.
    """

    moment: UsagesMoment
    changed: list[DepDrift]
    success: bool
    completion: Completion
    reason: str | None = None
