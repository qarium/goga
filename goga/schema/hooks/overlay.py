"""The tools-area composition of the schema domain hooks zone."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ToolContribution:
    """The committed contribution of one tool for one cell — constructed by the checkpoint delivery alone.

    Args:
        tool: the tool identity assigned by the platform.
        facts: the committed contribution of the tool — its merged
            buffer of fact-mapping contributions.
    """

    tool: str
    facts: dict[str, object]


def merge_cell_contributions(contributions: list[ToolContribution]) -> dict[str, dict[str, object]]:
    """Compose the tools area of one cell node from the committed contributions.

    Args:
        contributions: the committed contributions, in enumeration
            order.

    Returns:
        The tools area of the cell node — each non-empty mapping under
        its tool identity key, in enumeration order; empty when nothing
        contributed.
    """
    return {contribution.tool: contribution.facts for contribution in contributions if contribution.facts}
