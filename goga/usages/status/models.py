"""Data-model entities for the cell-level usages status domain.

The four contract entities (`UsageState`, `FolderStatus`, `DepStatus`,
`UsageStatusReport`) are defined in this internal module — NOT in `status.py` —
to break the `status.py` <-> `compare.py` import cycle: `status()` calls
`compute_dep_status` (compare.py) while `compute_dep_status` constructs these
models. ``status.py`` re-exports every name from here so the entities stay
importable from their contract location ``status.py``. This module is a pure
stdlib leaf (no inbound intra-cell imports), so importing it from either side
introduces no cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UsageState(Enum):
    """Fixed value set of a cell-level usages synchronization status.

    Each member's ``value`` is the display string the renderer prints.
    """

    new = "new"
    up_to_date = "up to date"
    out_of_date = "out of date"
    error = "error"


@dataclass(frozen=True, kw_only=True)
class FolderStatus:
    """Status of one folder within a dep, used to expand a dep under ``--info``.

    Attributes:
        path: Relative path of the folder within the dep (``""`` for root-level
            files).
        state: Folder status, restricted to ``up_to_date`` / ``out_of_date``.
    """

    path: str
    state: UsageState


@dataclass(frozen=True, kw_only=True)
class DepStatus:
    """Status of one declared group/dep.

    Attributes:
        group: Group name.
        dep: Dep name.
        state: Status value (``new`` / ``up_to_date`` / ``out_of_date`` / ``error``).
        folders: Per-folder statuses; empty when ``state`` is ``new`` or
            ``error``, populated when ``up_to_date`` or ``out_of_date``.
        error: Credential-free message describing the failure when ``state`` is
            ``error``; ``None`` otherwise.
    """

    group: str
    dep: str
    state: UsageState
    folders: list[FolderStatus]
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
