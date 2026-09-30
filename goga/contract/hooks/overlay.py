"""The per-type tools-area composition of the contract domain hooks zone.

Two pure entities make up the overlay layer of the zone:
``ToolContribution`` (the committed contribution of one tool for one
cell — the pairing of the tool identity with its type-addressed fact
mappings, constructed by the checkpoint delivery alone) and
``merge_type_contributions`` (the deterministic, pure composition of
the committed contributions into the tools area of each addressed type
node). Structural validation is not here — it happened at the tool
commit point of the delivery.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ToolContribution:
    """The committed contribution of one tool for one cell.

    Pure data — constructed by the checkpoint delivery alone.

    Args:
        tool: the tool identity assigned by the platform.
        facts: the committed type-addressed contributions of the tool.
    """

    tool: str
    facts: dict[str, dict[str, object]]


def merge_type_contributions(contributions: list[ToolContribution]) -> dict[str, dict[str, dict[str, object]]]:
    """Compose the tools area of every addressed type node.

    The deterministic per-type tools-area composition:

    1. Take the contributions in enumeration order.
    2. Skip a contribution whose mapping is empty — a tool exists on
       a type iff that tool wrote at least one fact for that type.
    3. For each type name the contribution addresses, place the tool's
       fact mapping under the tool identity inside that type's area.
    4. A type name absent from every committed contribution is absent
       from the result.
    5. Return the composed mapping — empty when every contribution was
       empty or none committed.

    Structural validation is not here — it happened at the tool commit
    point of the delivery.

    Args:
        contributions: the committed contributions, in enumeration
            order.

    Returns:
        The tools area per addressed type name — each contributing
        tool's fact mapping under its tool identity inside that type's
        area, in enumeration order; empty when nothing contributed.
    """

    tools: dict[str, dict[str, dict[str, object]]] = {}
    for contribution in contributions:
        for type_name, facts in contribution.facts.items():
            if facts:
                tools.setdefault(type_name, {})[contribution.tool] = facts
    return tools
