"""The amendment view of the contract domain hooks zone — the
read-and-contribute view.

``ContractAmendment`` is the context one tool receives at the hard
``contract/amend_contract`` checkpoint: the comparison facts of the
cell being amended — read-only and identical for every tool — plus
the buffer of that one tool's type-addressed contributions. The view
is read-and-contribute: reads deliver the comparison facts (a tool
never sees another tool's contribution), and :meth:`contribute` is
the only write channel, buffering one type-addressed contribution
until the delivery commits it.
"""

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

        The call buffers into the buffer of this tool alone and
        changes nothing until the delivery commits it; the buffer
        merges key-wise — for one type, a later write replaces an
        earlier one on fact-name conflict; a repeated type address
        merges its facts; an empty outer mapping contributes nothing.
        No validation and no interpretation live here — the payload
        is stored verbatim and the structural check of the merged
        buffer belongs to the delivery, so a payload not
        representable in the JSON map or an address naming a type the
        cell does not declare fails there, naming this tool. A
        contribution extends the addressed type nodes' tools areas
        only — the operation is never cancelled, redirected, or
        deferred from here.

        Args:
            facts: the type-addressed mapping — declared type name to
                the tool's fact mapping for that type.
        """

        self._pending.append(facts)
