"""The authored-facts read view of the schema domain hooks zone."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class CellFacts:
    """The authored facts of one cell — the per-cell read view, identical in every run regardless of filters.

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
    """The imported facts of one dependency — constructed by the caller from the document's imports.

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
    """The collected verdict of the validation walk — the violations of every subscribed tool in enumeration order.

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
