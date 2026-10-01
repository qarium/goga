"""The fact vocabulary of the usages hooks zone.

The entities declared in the cell CODEMANIFEST with ``location: facts.py``:
the eight fact entities of the four run-level moments — the identity
envelope ``UsagesMoment``, the sync-outcome records (``SyncOutcome``,
``SyncDepOutcome``), the drift-projection records (``DriftVerdict``,
``ChangeVerdict``, ``FileChange``, ``DepDrift``), and the terminal marker
``Completion``. Pure data, no behavior: every value mirrors what the
operations themselves observed — nothing is read, derived, or computed
here, and no fact carries a credential-bearing value. This module is a
stdlib-only leaf with no inbound intra-zone imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, kw_only=True)
class UsagesMoment:
    """The identity envelope of every usages moment.

    Attributes:
        operation: The operation kind — sync or status.
        group: The applied group filter; None when no filter was applied.
        dep: The applied dep filter; None when no filter was applied.

    Requirements:
        pure facts — the values mirror the operation's own inputs; a dep
        filtered out by the filters is silently absent from every downstream
        fact — neither an error nor a skipped record.
    """

    operation: str
    group: str | None
    dep: str | None


class SyncOutcome(Enum):
    """Fixed value set of a matched dep's sync outcome.

    Each member's ``value`` is the display string the fact records carry —
    tools string-match the verdicts, so the values are contractual.

    Members:
        synced: The dep was cloned and deployed by the run.
        skipped: The dep's target already existed and force was not applied.
        failed: The dep's sync raised; the record carries the
            credential-free failure message.
    """

    synced = "synced"
    skipped = "skipped"
    failed = "failed"


@dataclass(frozen=True, kw_only=True)
class SyncDepOutcome:
    """The sync outcome of one matched dep.

    Attributes:
        group: The dep's group name.
        dep: The dep name.
        outcome: The dep's outcome — synced, skipped, or failed.
        message: The credential-free failure message when failed; None
            otherwise.

    Requirements:
        the message is set only when the outcome is failed; one record per
        matched dep — filtered-out deps are absent.
    """

    group: str
    dep: str
    outcome: SyncOutcome
    message: str | None = None


class DriftVerdict(Enum):
    """Fixed value set of a changed dep's drift verdict.

    Each member's ``value`` is the display string the fact records carry —
    ``out_of_date`` mirrors ``UsageState.out_of_date = "out of date"``.

    Members:
        new: The declared dep's target directory is absent.
        out_of_date: The local tree differs from the remote-rebuilt tree.
        error: The dep could not be checked.
    """

    new = "new"
    out_of_date = "out of date"
    error = "error"


class ChangeVerdict(Enum):
    """Fixed value set of one file's change between the expected and local trees.

    Members:
        added: Present only in the expected (remote-rebuilt) tree.
        modified: Present in both trees, the content differs.
        removed: Present only in the local tree.
    """

    added = "added"
    modified = "modified"
    removed = "removed"


@dataclass(frozen=True, kw_only=True)
class FileChange:
    """One file's change within a dep.

    Attributes:
        path: The file's relative posix path within the dep.
        change: The file's change verdict — added, modified, or removed.

    Requirements:
        files only — a directory node never appears as a record.
    """

    path: str
    change: ChangeVerdict


class Completion(Enum):
    """The terminal marker of a completed context.

    Members:
        finished: The operation returned through its own paths; the facts
            are the final accounting, success or failure.
        crashed: The operation broke off unexpectedly; the facts are the
            best known at the break-off point and the run is an overall
            failure.
    """

    finished = "finished"
    crashed = "crashed"


@dataclass(frozen=True, kw_only=True)
class DepDrift:
    """One changed-set record of the status check.

    A matched dep whose verdict is not up to date — the record the
    completion context's ``changed`` set carries.

    Attributes:
        group: The dep's group name.
        dep: The dep name.
        verdict: The dep's verdict — new, out of date, or error.
        changes: The per-file change list within the dep; populated for the
            out-of-date verdict, empty for new and error.
        message: The credential-free error message when error; None
            otherwise.

    Requirements:
        directory nodes are absent from the change list — it carries files
        only; the changed set contains no up-to-date dep — an empty changed
        set reads as no drift among the matched deps.
    """

    group: str
    dep: str
    verdict: DriftVerdict
    changes: list[FileChange]
    message: str | None = None
