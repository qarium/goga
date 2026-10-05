"""The status scale value model of the statuses cell."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True, kw_only=True)
class Stage:
    """One entry of the scale — a named position anchored to the artifact that marks it.

    Attributes:
        name: The qualified name — bare for built-in entries, ``<tool>.<name>``
            for tool entries.
        filepath: The artifact path relative to the topic directory; nested
            paths allowed. The ``empty`` entry carries the empty string and is
            never marked present.
        before: The qualified name of the entry this one precedes; ``None``
            for built-in entries.
        after: The qualified name of the entry this one follows; ``None`` for
            built-in entries.

    Requirements:
        A tool entry carries at least one anchor; a built-in entry carries
        none — its position is the axis order.
    """

    name: str
    filepath: str
    before: str | None = None
    after: str | None = None


@dataclass(kw_only=True)
class StatusScale:
    """The assembled partially ordered scale of topic statuses.

    Attributes:
        stages: The scale content in scale order.

    Requirements:
        The built-in axis is ordered empty, todo, defined, discovered,
        backlog, prototyped, designed, planned, done by the artifacts
        todo.md, prd.md, adr.md, task.md, arch.md, design.md, plan.md,
        completed/plan.md; a tool status never reorders or replaces a
        built-in one.
    """

    stages: list[Stage]

    def maximal_present(self, paths: list[str]) -> list[str]:
        """Compute the maximal present statuses of one topic.

        Args:
            paths: The artifact paths present in a topic directory, relative
                to it.

        Returns:
            The qualified names of the maximal present statuses, in scale
            order. A topic with no artifact present yields the single
            built-in name ``empty``.

        Algorithm:
            1. Mark every scale entry whose artifact path is present
            2. Drop every marked entry strictly below another marked entry
            3. Return the names of the surviving entries in scale order

        Requirements:
            Every maximal entry is returned — a present entry outranked by
            no other present entry stays visible.

        Constraints:
            Do not probe the filesystem — presence is decided by the
            caller's ``paths`` input alone.
        """
        present = set(paths)
        marked = [stage for stage in self.stages if stage.filepath and stage.filepath in present]

        if not marked:
            return ["empty"]

        above = self._strictly_above()
        marked_names = {stage.name for stage in marked}
        maximal = [stage for stage in marked if not above[stage.name] & marked_names]

        return [stage.name for stage in maximal]

    def resolve_status(self, name: str) -> Stage:
        """Resolve a qualified status name for filter validation.

        Args:
            name: A status name as entered by a consumer — a built-in name
                or a qualified tool name.

        Returns:
            The scale entry carrying the name.

        Raises:
            ValueError: The name matches no entry of the scale.

        Algorithm:
            1. Find the scale entry whose qualified name equals ``name``
               exactly
            2. An unknown name raises a clean error

        Constraints:
            Do not fuzzy-match or fall back — the exact qualified name is
            the contract.
        """
        for stage in self.stages:
            if stage.name == name:
                return stage
        raise ValueError(f"unknown status name: {name!r}")

    def _strictly_above(self) -> dict[str, set[str]]:
        """Map every qualified name to the names of the entries strictly above it.

        Returns:
            The transitive closure of the scale's ``below -> above`` edges:
            the anchor-free built-in axis chained in list order plus one edge
            per anchor; an anchor naming no scale entry adds no edge.
        """
        above: dict[str, set[str]] = {stage.name: set() for stage in self.stages}
        axis = [stage for stage in self.stages if stage.before is None and stage.after is None]

        for below, upper in pairwise(axis):
            above[below.name].add(upper.name)

        for stage in self.stages:
            if stage.after is not None and stage.after in above:
                above[stage.after].add(stage.name)
            if stage.before is not None and stage.before in above:
                above[stage.name].add(stage.before)
        # Close transitively by iterating to a fixed point — the scale is
        # small, and the loop stays safe even on a cyclic hand-built input.
        names = list(above)
        changed = True

        while changed:
            changed = False
            for name in names:
                uppers = above[name]
                inherited = set().union(*(above[upper] for upper in uppers)) if uppers else set()
                missing = inherited - uppers
                if missing:
                    above[name] = uppers | missing
                    changed = True

        return above
