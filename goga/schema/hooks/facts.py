"""The authored-facts read view of the schema domain hooks zone.

``CellFacts`` is the per-cell read view delivered to every subscribed hook
of the hard ``schema/amend_cell`` checkpoint: the authored facts of one
cell as resolved by the calling walk. ``DependencyFacts`` is the imported
facts of one dependency — the source path with its imported type names and
usage names. Both are pure facts: the constructing operation passes
resolved values and nothing is read inside either record — the authored
projection only, identical in every run regardless of filters; never
another tool's contributions, generated data, or the run's filter
parameters.

``SchemaNode``, ``Violation``, and ``GateVerdict`` serve the validation
gate: one node of the final assembled tree — the committed tools overlay
included — as the read-only delivered view of the gate, one collected veto
of the walk, and the collected verdict with its derived ``approved``
property. The gate facts carry the final result, the tools overlay
included — a recorded exception to the authored-facts-only delivery rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class CellFacts:
    """The authored facts of one cell — the per-cell read view.

    Pure facts: the constructing operation (the schema walk) passes
    resolved values, nothing is read inside. The record is the authored
    projection only — identical in every run regardless of filters; never
    another tool's contributions, generated data, or the run's filter
    parameters.

    Args:
        path: the normalized cell path.
        description: the footer description of the cell manifest.
        types: the entity and routine names of the cell body.
        usages: the usages file names of the cell.
        dependencies: the cell's imports grouped per source path.
        children: the authored children paths of the document tree.
    """

    path: str
    description: str
    types: list[str]
    usages: list[str]
    dependencies: list[DependencyFacts]
    children: list[str]


@dataclass(frozen=True, kw_only=True)
class DependencyFacts:
    """The imported facts of one dependency — pure data.

    Constructed by the caller from the document's imports; nothing is read
    inside.

    Args:
        path: the source path of the import.
        types: the imported type names.
        usages: the imported usage names.
    """

    path: str
    types: list[str]
    usages: list[str]


@dataclass(frozen=True, kw_only=True)
class SchemaNode:
    """One node of the final assembled tree — the read-only delivered view of the validation gate.

    Pure facts: the constructing operation (the schema walk) passes the
    assembled values, nothing is read inside. The node carries the final
    result, the tools overlay included — a recorded exception to the
    authored-facts-only delivery rule: a validator observes and vetoes,
    and the tree is never modified by a validator.

    Args:
        path: the normalized cell path.
        description: the footer description of the cell manifest.
        types: the entity and routine names of the cell body.
        usages: the usages file names of the cell.
        dependencies: the cell's imports grouped per source path.
        children: the children of the node, in tree order.
        tools: the committed tools overlay of the node; empty when no
            tool contributed.
    """

    path: str
    description: str
    types: list[str]
    usages: list[str]
    dependencies: list[DependencyFacts]
    children: list[SchemaNode]
    tools: dict[str, dict[str, object]] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class Violation:
    """One collected veto of the validation walk.

    Args:
        tool: the tool identity assigned by the platform.
        hook: the hook name that vetoed or crashed.
        reason: the veto reason — a hook-authored message or the crash
            reason; never a raw traceback.
    """

    tool: str
    hook: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class GateVerdict:
    """The collected verdict of the validation walk.

    Every veto of every subscribed tool, in enumeration order — the
    verdict is data only; acting on it (the merged error, the exit code)
    belongs to the operation.

    Args:
        violations: the collected violations; an empty list means
            approved.
    """

    violations: list[Violation]

    @property
    def approved(self) -> bool:
        """Report whether the gate approved the generation.

        Returns:
            ``True`` when no violation was collected — the generation may
            proceed.
        """
        return not self.violations
