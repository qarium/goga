"""The code-derived-facts read view of the codegraph domain hooks zone."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class NodeFacts:
    """The code-derived facts of one node — the per-node read view, identical in every run regardless of filters.

    Args:
        cell: the cell path relative to the project root.
        types: the facade type names of the cell.
        dependencies: the target cell path to its imported facade types.
        children: the nested child cell paths of the node in the complete
            code-derived tree, in tree order.

    Pure facts — the constructing operation passes resolved values; nothing
    is read here. Code-derived projection only — identical in every run
    regardless of filters; never another tool's contributions, generated
    data, or the run's filter parameters. The filters prune delivery, never
    the facts — the child list is the complete code-derived subtree of the
    node and may name cells pruned from the current run's output.
    """

    cell: str
    types: list[str]
    dependencies: dict[str, list[str]]
    children: list[str]

    def __post_init__(self) -> None:
        """Copy every caller-owned container into fresh containers."""
        dependencies = {key: list(value) for key, value in self.dependencies.items()}

        object.__setattr__(self, "types", list(self.types))
        object.__setattr__(self, "dependencies", dependencies)
        object.__setattr__(self, "children", list(self.children))


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
    """The collected verdict of the validation walk — every veto of every subscribed tool in enumeration order.

    Args:
        violations: the collected violations; an empty list means
            approved.

    The verdict is data only — acting on it (the merged error, the exit
    code) belongs to the operation.
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
