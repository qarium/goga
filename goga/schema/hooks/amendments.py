"""The amendment view of the schema domain hooks zone — the read-and-contribute view."""

from __future__ import annotations

from dataclasses import dataclass, field

from .facts import CellFacts


@dataclass(kw_only=True)
class CellAmendment:
    """The read-and-contribute view of one tool for one cell.

    Args:
        cell: the authored facts of the cell being built — read-only and
            identical for every tool; the receiving hook observes
            authored facts only, never another tool's contribution.
    """

    cell: CellFacts

    _pending: list = field(init=False, default_factory=list, repr=False)

    def contribute(self, facts: dict[str, object]) -> None:
        """Buffer one fact-mapping contribution of this tool.

        Args:
            facts: the contribution mapping — fact names to JSON-representable values; buffered verbatim,
                merged key-wise and structurally checked at the delivery — later writes replace earlier ones.
        """

        self._pending.append(facts)
