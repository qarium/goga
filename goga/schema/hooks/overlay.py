"""The tools-area composition of the schema domain hooks zone.

Two pure entities make up the overlay layer of the zone:
``ToolContribution`` (the committed contribution of one tool for one
cell — the pairing of the tool identity with its merged fact mapping,
constructed by the checkpoint delivery alone) and
``merge_cell_contributions`` (the deterministic, pure composition of the
committed contributions into the ``tools`` mapping of one cell node).
Structural validation is not here — it happened at the tool commit point
of the delivery.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ToolContribution:
    """The committed contribution of one tool for one cell.

    Pure data — constructed by the checkpoint delivery alone.

    Args:
        tool: the tool identity assigned by the platform.
        facts: the committed contribution of the tool — its merged
            buffer of fact-mapping contributions.
    """

    tool: str
    facts: dict[str, object]


def merge_cell_contributions(contributions: list[ToolContribution]) -> dict[str, dict[str, object]]:
    """Compose the tools area of one cell node from the committed contributions.

    The deterministic tools-area composition:

    1. Take the contributions in enumeration order.
    2. Skip a contribution whose mapping is empty — a tool's key exists
       iff that tool wrote at least one fact.
    3. Place each remaining mapping under its tool identity key.
    4. Return the composed mapping — empty when every contribution was
       empty or none committed.

    Structural validation is not here — it happened at the tool commit
    point of the delivery.

    Args:
        contributions: the committed contributions, in enumeration
            order.

    Returns:
        The tools area of the cell node — each non-empty mapping under
        its tool identity key, in enumeration order; empty when nothing
        contributed.
    """
    return {contribution.tool: contribution.facts for contribution in contributions if contribution.facts}
