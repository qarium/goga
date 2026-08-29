"""The tool-status registration surface of the statuses cell.

The entity declared in the cell CODEMANIFEST with ``location: registry.py``:
the controlled registration surface handed to a tool package — the only way
a tool status enters the scale. Pure registration logic: names are qualified
and the content is validated here, while anchor resolution and placement
stay with the scale assembly — a tool may anchor to an entry registered by
another tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .scale import Stage


@dataclass(kw_only=True)
class StatusRegistry:
    """The controlled registration surface handed to a tool package.

    The only way a tool status enters the scale. Registration is add-only —
    a built-in entry is never modified, removed, or re-anchored.

    Attributes:
        builtin_stages: The immutable built-in axis the registry extends.
        tool_prefix: The qualifier applied to every name registered through
            this registry — derived from the package name.

    Requirements:
        Registration is add-only — a built-in entry is never modified,
        removed, or re-anchored.
    """

    builtin_stages: list[Stage]
    tool_prefix: str
    _entries: list[Stage] = field(default_factory=list, init=False, repr=False)

    @property
    def stages(self) -> list[Stage]:
        """The built-in axis plus every accepted tool entry.

        A copy is issued every time — mutating the returned list never
        reaches the registry content.
        """
        return [*self.builtin_stages, *self._entries]

    def register(
        self,
        name: str,
        filepath: str,
        before: str | None = None,
        after: str | None = None,
    ) -> None:
        """Register one tool status.

        Args:
            name: The status name as the tool defines it — stored qualified
                as ``<tool_prefix>.<name>``.
            filepath: The artifact path relative to the topic directory.
            before: Optional anchor — the qualified name of an entry this one
                precedes.
            after: Optional anchor — the qualified name of an entry this one
                follows.

        Raises:
            ValueError: A structural violation — the message names the entry.

        Algorithm:
            1. Qualify ``name`` with the registry's tool prefix
            2. Validate the content: a non-empty name, a non-empty
               ``filepath``, and at least one anchor present
            3. Append the entry to the registry content

        Requirements:
            A structural violation raises a clean registration error naming
            the entry. Both anchors given define a placement range; anchor
            resolution and range validity are decided at scale assembly.

        Constraints:
            Do not resolve anchors here — a tool may anchor to an entry
            registered by another tool. Do not modify built-in entries.
        """
        qualified = f"{self.tool_prefix}.{name}"
        if not isinstance(name, str) or not name:
            raise ValueError(f"status entry {qualified!r}: name must be a non-empty string")
        if not isinstance(filepath, str) or not filepath:
            raise ValueError(f"status entry {qualified!r}: filepath must be a non-empty string")
        if before is None and after is None:
            raise ValueError(f"status entry {qualified!r}: at least one anchor is required")
        if any(entry.name == qualified for entry in self._entries):
            raise ValueError(f"status entry {qualified!r}: already registered in this registry")
        self._entries.append(Stage(name=qualified, filepath=filepath, before=before, after=after))
