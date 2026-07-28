"""Data-model entities for the cell-level usages status domain.

The contract entities (`UsageState`, `EntryChange`, `EntryKind`, `EntryStatus`,
`DepStatus`, `UsageStatusReport`) are defined in this internal module — NOT in
`status.py` — to break the `status.py` <-> `compare.py` import cycle: `status()`
calls `compute_dep_status` (compare.py) while `compute_dep_status` constructs
these models. ``status.py`` re-exports every name from here so the entities stay
importable from their contract location ``status.py``. This module is a pure
stdlib leaf (no inbound intra-cell imports), so importing it from either side
introduces no cycle.

Two status vocabularies coexist:

* :class:`UsageState` is the **dep-level** summary (one value per dep):
  ``new`` / ``up_to_date`` / ``out_of_date`` / ``error``. It stays a fixed
  four-member set; the renderer maps it onto a tree marker.
* :class:`EntryChange` is the **per-node** diff verdict (one value per file or
  directory within a dep): ``unchanged`` / ``modified`` / ``added`` / ``removed``.
  It distinguishes, for example, a remote-only folder (``added``) from a
  differing file (``modified``) — the distinction the roll-up model collapsed
  into a single ``out_of_date``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UsageState(Enum):
    """Fixed value set of a cell-level usages synchronization status (dep-level).

    Each member's ``value`` is the display string the renderer prints.
    """

    new = "new"
    up_to_date = "up to date"
    out_of_date = "out of date"
    error = "error"


class EntryChange(Enum):
    """Per-node (file or directory) diff verdict between expected and local trees.

    Members:

    * ``unchanged`` — present in both trees with identical content.
    * ``modified`` — present in both trees but the content differs.
    * ``added`` — present only in the expected (remote-rebuilt) tree.
    * ``removed`` — present only in the local (synced) tree.
    """

    unchanged = "unchanged"
    modified = "modified"
    added = "added"
    removed = "removed"


class EntryKind(Enum):
    """Whether a status entry is a file or a directory (drives the trailing ``/``)."""

    file = "file"
    dir = "dir"


@dataclass(frozen=True, kw_only=True)
class EntryStatus:
    """Status of one node (file or directory) within a dep.

    Directories are derived from the ancestor prefixes of every file path and
    carry an aggregated verdict over the files beneath them; files carry their
    own verdict. The flat, path-sorted list of entries is the renderer's source
    of truth for drawing the per-dep tree under ``--info``.

    Attributes:
        path: Relative posix path of the node within the dep (``""`` is never
            used — the dep root itself is the ``DepStatus``, not an entry).
        kind: ``EntryKind.file`` or ``EntryKind.dir``.
        change: Per-node verdict.
    """

    path: str
    kind: EntryKind
    change: EntryChange


@dataclass(frozen=True, kw_only=True)
class DepStatus:
    """Status of one declared group/dep.

    Attributes:
        group: Group name.
        dep: Dep name.
        state: Dep-level status value (``new`` / ``up_to_date`` / ``out_of_date``
            / ``error``).
        entries: Per-node diff tree (files and directories) sorted by path; empty
            when ``state`` is ``new`` or ``error``, populated when ``up_to_date``
            or ``out_of_date``.
        error: Credential-free message describing the failure when ``state`` is
            ``error``; ``None`` otherwise.
    """

    group: str
    dep: str
    state: UsageState
    entries: list[EntryStatus]
    error: str | None = None


@dataclass(frozen=True, kw_only=True)
class UsageStatusReport:
    """Aggregate status result over all checked deps; carries the exit code.

    The exit code is derived from ``deps`` — there is no separate exit-code
    field.

    Attributes:
        deps: Per-dep status records, in iteration order.
    """

    deps: list[DepStatus]

    @property
    def exit_code(self) -> int:
        """Derived exit code: 0 iff every dep is up to date, else 1.

        Returns:
            ``0`` when ``deps`` is empty or every dep has state
            ``up_to_date``; ``1`` otherwise (covers ``new``, ``out_of_date``,
            ``error``).
        """
        if all(dep.state is UsageState.up_to_date for dep in self.deps):
            return 0

        return 1
