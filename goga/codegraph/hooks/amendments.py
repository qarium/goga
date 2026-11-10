"""The amendment view of the codegraph domain hooks zone — the read-and-contribute view."""

from __future__ import annotations

from dataclasses import dataclass, field

from .facts import NodeFacts


@dataclass(kw_only=True)
class NodeAmendment:
    """The read-and-contribute view of one tool for one node.

    Args:
        node: the code-derived facts of the node being amended — read-only
            and identical for every tool; the receiving hook observes
            code-derived facts only, never another tool's contribution.
    """

    node: NodeFacts

    _pending: list = field(init=False, default_factory=list, repr=False)

    def contribute(self, facts: dict[str, object]) -> None:
        """Buffer one fact-mapping contribution of this tool.

        Args:
            facts: the contribution mapping — fact names to JSON-representable values; buffered
                verbatim into this tool's buffer alone and changing nothing until the delivery
                commits it — the buffer merges key-wise, a later write replacing an earlier one
                on key conflict; an empty mapping contributes nothing. The call never cancels,
                redirects, or defers the operation — a contribution extends the node's tools
                area only.
        """

        self._pending.append(facts)
