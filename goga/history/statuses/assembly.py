"""The scale assembly routine of the statuses cell.

The routine declared in the cell CODEMANIFEST with ``location: assembly.py``:
the full status scale — the built-in axis extended by every tool subscribed
to the status action of the hooks platform. The cell emits the action and
places the registrations delivered through it; the tool packages are carried
by the platform. The assembly runs at every command start that needs the
scale; the scale is never cached across runs. A broken package import is the
only fatal case — it surfaces through the emission.
"""

from __future__ import annotations

import sys

from ...hooks import HookRegistry, emit_hook_event
from .registry import StatusRegistry
from .scale import Stage, StatusScale

_BUILTIN_AXIS: list[Stage] = [
    Stage(name="empty", filepath=""),
    Stage(name="todo", filepath="todo.md"),
    Stage(name="defined", filepath="prd.md"),
    Stage(name="discovered", filepath="adr.md"),
    Stage(name="backlog", filepath="task.md"),
    Stage(name="designed", filepath="arch.md"),
    Stage(name="specified", filepath="design.md"),
    Stage(name="planned", filepath="plan.md"),
    Stage(name="done", filepath="completed/plan.md"),
]

_ACTION_DOMAIN = "statuses"
_ACTION_NAME = "register_statuses"


def assemble_status_scale() -> StatusScale:
    """Assemble the full status scale — the built-in axis extended by every subscribed tool.

    Returns:
        scale: The assembled scale.

    Algorithm:
        1. Build the built-in axis of nine entries
        2. Create the run registry via ``HookRegistry``
        3. Emit the status action through the platform: the context view of
           one receiving tool is a ``StatusRegistry`` over the axis,
           qualified by the tool identity — at most one registry per tool
           identity, all hooks of the tool share it
        4. Collect the delivered registries in enumeration order
        5. Resolve the anchors of each surviving entry against the list
           assembled by the moment the entry is processed — the built-in
           axis plus the entries of the earlier tools and the earlier
           entries of the current one; an unresolvable anchor or an invalid
           range skips the registration with a warning to stderr
        6. Assemble and return the scale

    Requirements:
        The scale assembles from the surviving registrations alone — one
        broken registration never cancels the rest. The emission performs
        the single build of the run; a broken package import surfacing
        through it is the only fatal case.

    Constraints:
        Do not enumerate the installed tool packages and do not import their
        facades — the platform carries the tool packages. Do not cache the
        scale across command runs.

    Placement follows the anchors of each surviving entry, resolved against
    the list assembled by the moment the entry is processed. Entries sharing
    an anchor form one continuous block in registration order: an
    ``after``-anchored entry lands at the end of its anchor's block, a
    ``before``-anchored entry right in front of its anchor, and both anchors
    given define a range the entry must fit into.
    """
    registry = HookRegistry()
    registries: dict[str, StatusRegistry] = {}

    def context_for(tool: str) -> StatusRegistry:
        """Build the context view of one receiving tool — at most one registry per tool identity."""
        if tool not in registries:
            registries[tool] = StatusRegistry(builtin_stages=list(_BUILTIN_AXIS), tool_prefix=tool)

        return registries[tool]

    emit_hook_event(registry, _ACTION_DOMAIN, _ACTION_NAME, context_for)

    stages = list(_BUILTIN_AXIS)

    for status_registry in registries.values():
        for entry in status_registry.stages[len(_BUILTIN_AXIS) :]:
            try:
                index = _placement_index(stages, entry)
            except ValueError as exc:
                print(f"Warning: skipping status registration {entry.name}: {exc}", file=sys.stderr)
                continue
            stages.insert(index, entry)

    return StatusScale(stages=stages)


def _placement_index(stages: list[Stage], entry: Stage) -> int:
    """Resolve the anchors of one accepted entry to an insertion index.

    Args:
        stages: The list assembled by the moment the entry is processed.
        entry: The accepted tool entry to place.

    Returns:
        The index the entry is inserted at.

    Raises:
        ValueError: An anchor names no entry of the list, or the two
            anchors define an invalid range.
    """
    positions = {stage.name: index for index, stage in enumerate(stages)}
    after = entry.after
    before = entry.before

    if after is not None and after not in positions:
        raise ValueError(f"status entry {entry.name!r}: unknown after anchor {after!r}")
    if before is not None and before not in positions:
        raise ValueError(f"status entry {entry.name!r}: unknown before anchor {before!r}")
    if after is None:
        return positions[before]
    if before is None:
        # The end of the anchor's block — every entry already inserted
        # with the same ``after`` anchor sits between the anchor and this
        # index, keeping the block in registration order.
        block = sum(1 for stage in stages if stage.after == after)
        return positions[after] + 1 + block
    if not positions[after] < positions[before]:
        raise ValueError(f"status entry {entry.name!r}: anchor range {after!r}..{before!r} is invalid")

    return positions[before]
