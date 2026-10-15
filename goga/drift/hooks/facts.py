"""The fact vocabulary of the drift domain hooks zone."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True, kw_only=True)
class DriftFilters:
    """The start-moment facts — the filters the run was asked to apply.

    Args:
        cells: the cell paths requested to scope the report.
        max_depth: the requested nesting limit; None — no limit.
        depends_on: the requested dependency-scoping paths.

    Pure facts — the values mirror the run's own inputs; nothing is
    read or derived here. Identical on every run with the same
    arguments.
    """

    cells: list[str]
    max_depth: int | None
    depends_on: list[str]

    def __post_init__(self) -> None:
        """Copy every caller-owned container into fresh containers."""
        object.__setattr__(self, "cells", list(self.cells))
        object.__setattr__(self, "depends_on", list(self.depends_on))


@dataclass(frozen=True, kw_only=True)
class EntryFacts:
    """The entry facts record — the delivered read view of one report entry.

    Args:
        kind: the direction — schema_only or codegraph_only.
        cell: the normalized cell path of the subject.
        types: the sorted type names; None marks a cell-level entry.

    Pure facts — the caller projects the values; nothing is read here.
    Tools-free — the record never carries contributions; the delivered
    views of both amendments read these facts only. ``kind`` is one of
    the comparison's entry kinds; the shape is exactly kind, cell,
    types.
    """

    kind: str
    cell: str
    types: list[str] | None

    def __post_init__(self) -> None:
        """Copy the caller-owned type list into a fresh container."""
        if self.types is not None:
            object.__setattr__(self, "types", list(self.types))


@dataclass(frozen=True, kw_only=True)
class ReportEntry:
    """The completion-moment report entry — the projection of one entry of the carried report stage.

    Args:
        kind: the direction — schema_only or codegraph_only.
        cell: the normalized cell path of the subject.
        types: the sorted type names; None marks a cell-level entry.
        tools: the committed tools overlay of the entry; empty when no
            tool contributed.

    Pure facts — the caller projects the values. On failure-carried
    stages the tools mapping is empty — no facts areas were computed.
    """

    kind: str
    cell: str
    types: list[str] | None = None
    tools: dict[str, dict[str, object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Copy the caller-owned containers into fresh containers.

        The ``tools`` copy runs to every nesting level: the record is the
        completion-moment projection of an already-committed overlay, and
        the copy keeps an in-place write of an observing hook inside the
        delivered view — never the caller's own report.
        """
        if self.types is not None:
            object.__setattr__(self, "types", list(self.types))
        object.__setattr__(self, "tools", copy.deepcopy(self.tools))


class RunOutcome(Enum):
    """Fixed value set of a drift run's terminal outcome — member values are contractual display strings.

    Attributes:
        finished: the run reached its natural terminal state; the final
            report was produced.
        crashed: the run failed before the final report was produced.
    """

    finished = "finished"
    crashed = "crashed"


@dataclass(frozen=True, kw_only=True)
class RunCompletion:
    """The completion-moment facts — the terminal state of one drift run.

    Args:
        report: the last computed report stage — the final report with
            facts areas on finished runs, the scoped pre-amendment
            report when a later stage failed, None when the run failed
            before the report was computed.
        outcome: the terminal outcome marker.
        reason: a credential-free crash reason on crashed runs — no
            tokens, keys, passwords, or other secrets; empty on
            finished runs.

    Pure facts — the caller projects the values; no fact carries a
    credential-bearing value.
    """

    report: list[ReportEntry] | None
    outcome: RunOutcome
    reason: str
