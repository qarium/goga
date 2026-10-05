"""The amendment view of the contract domain hooks zone — the read-and-contribute view."""

from __future__ import annotations

from dataclasses import dataclass, field

from .facts import CellFacts


@dataclass(kw_only=True)
class ContractAmendment:
    """The read-and-contribute view of one tool for one cell.

    Args:
        cell: the comparison facts of the cell being amended —
            read-only and identical for every tool; the receiving hook
            observes the comparison facts only, never another tool's
            contribution.
    """

    cell: CellFacts

    _pending: list = field(init=False, default_factory=list, repr=False)

    def contribute(self, facts: dict[str, dict[str, object]]) -> None:
        """Buffer one type-addressed contribution of this tool.

        Args:
            facts: the type-addressed mapping — declared type name to
                the tool's fact mapping for that type.
        """

        self._pending.append(facts)
