"""The delivered view of the schema validation gate."""

from __future__ import annotations

from dataclasses import dataclass, field

from .facts import SchemaNode


@dataclass(kw_only=True)
class SchemaValidation:
    """The gate's delivered view of one tool — the read-only final tree plus the veto buffer of this tool alone.

    Args:
        tree: the final assembled tree in tree order — the tools overlay included;
            read-only for the receiving hook (a fresh copy per tool).
    """

    tree: list[SchemaNode]

    _veto: str | None = field(init=False, default=None, repr=False)

    def veto(self, reason: str) -> None:
        """Buffer this tool's veto of the final tree.

        The replacement is whole — a later call replaces the earlier reason.
        The view records no hook identity: the walk attributes the veto by
        observing the buffer change around each call. The call changes nothing
        until the walk collects it; it does not cancel, redirect, or defer the
        operation — a veto stops the generation through the collected verdict
        only. An empty or whitespace-only reason is stored as given; the merged
        error renders it verbatim.

        Args:
            reason: the human-readable violation reason.
        """
        self._veto = reason
