"""The amendment view of the schema domain hooks zone — the
read-and-contribute view.

``CellAmendment`` is the context one tool receives at the hard
``schema/amend_cell`` checkpoint: the authored facts of the cell being
built — read-only and identical for every tool — plus the buffer of that
one tool's contributions. The view is read-and-contribute: reads deliver
the authored facts (a tool never sees another tool's contribution), and
:meth:`contribute` is the only write channel, buffering one
fact-mapping contribution until the delivery commits it.
"""

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

        The call buffers into the buffer of this tool alone and changes
        nothing until the delivery commits it; the buffer merges
        key-wise — a later write replaces an earlier one on key
        conflict; an empty mapping contributes nothing. No validation
        and no interpretation live here — the payload is stored
        verbatim and the structural check of the merged buffer belongs
        to the delivery, so a payload not representable in the JSON map
        fails there, naming this tool. A contribution extends the cell
        node's tools area only — the operation is never cancelled,
        redirected, or deferred from here.

        Args:
            facts: the contribution mapping — fact names to
                JSON-representable values.
        """

        self._pending.append(facts)
