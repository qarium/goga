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

        Args:
            reason: the human-readable violation reason; a later call replaces the earlier reason — the
                veto takes effect only through the collected verdict, never directly.
        """
        self._veto = reason
