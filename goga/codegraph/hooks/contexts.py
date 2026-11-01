"""The delivered view of the codegraph validation gate."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..facts import CodegraphNode


@dataclass(kw_only=True)
class GraphValidation:
    """The gate's delivered view of one tool — the read-only final tree plus the veto buffer of this tool alone.

    Args:
        tree: the final assembled tree in tree order — the tools overlay included;
            read-only for the receiving hook (a fresh copy per tool).
    """

    tree: list[CodegraphNode]

    _veto: str | None = field(init=False, default=None, repr=False)

    def veto(self, reason: str) -> None:
        """Buffer this tool's veto of the final tree.

        Args:
            reason: the human-readable violation reason; the replacement is whole — a later call
                replaces the earlier reason, and an empty or whitespace-only reason is stored as
                given. The view records no hook identity — the walk attributes the veto by
                observing the buffer change around each call — and the veto stops the generation
                through the collected verdict only, never directly.
        """

        self._veto = reason
