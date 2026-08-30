"""The scale assembly routine of the statuses cell.

The routine declared in the cell CODEMANIFEST with ``location: assembly.py``:
the full status scale — the built-in axis extended by every installed tool
package. The assembly runs at every command start that needs the scale; the
scale is never cached across runs. A registration problem never aborts the
command — a package import failure is the only fatal case.
"""

from __future__ import annotations

import sys
from importlib import import_module
from importlib.metadata import packages_distributions
from types import ModuleType

from .registry import StatusRegistry
from .scale import Stage, StatusScale

_BUILTIN_AXIS: list[Stage] = [
    Stage(name="empty", filepath=""),
    Stage(name="new", filepath="title.txt"),
    Stage(name="defined", filepath="prd.md"),
    Stage(name="discovered", filepath="adr.md"),
    Stage(name="backlog", filepath="task.md"),
    Stage(name="designed", filepath="arch.md"),
    Stage(name="specified", filepath="design.md"),
    Stage(name="planned", filepath="plan.md"),
    Stage(name="done", filepath="completed/plan.md"),
]


def assemble_status_scale() -> StatusScale:
    """Assemble the full status scale — the built-in axis extended by every installed tool package.

    Returns:
        scale: The assembled scale.

    Algorithm:
        1. Build the built-in axis of nine entries
        2. Enumerate the installed goga_tool_* packages in alphabetical
           order of package name
        3. Import each package — a broken import is a clean error naming
           the package
        4. A package without the callback of the ``registration`` practice
           is skipped silently
        5. Call the callback with a registry scoped to the package
        6. Any exception from the callback — a registration content error
           or a crashed callback — skips that registration with a warning
           to stderr; the package import failure of step 3 remains the
           only fatal case
        7. Resolve anchors and validate placement ranges; an unresolvable
           anchor or an invalid range skips the registration with a
           warning to stderr
        8. Assemble and return the scale

    Requirements:
        The scale assembles from the surviving registrations alone — one
        broken registration never cancels the rest. Package enumeration
        mirrors goga/connect: ``importlib.metadata.packages_distributions()``
        filtered to top-level module names starting with ``goga_tool_``,
        sorted alphabetically by top-level module name.

    Constraints:
        Do not cache the scale across command runs. Do not let a
        registration problem abort the command.

    Placement follows the anchors of each surviving entry, resolved against
    the list assembled by the moment the entry is processed — the built-in
    axis plus the entries of the earlier packages and the earlier entries of
    the current one. Entries sharing an anchor form one continuous block in
    registration order: an ``after``-anchored entry lands at the end of its
    anchor's block, a ``before``-anchored entry right in front of its anchor,
    and both anchors given define a range the entry must fit into.
    """
    stages = list(_BUILTIN_AXIS)
    for package_name in _tool_packages():
        module = _import_tool_package(package_name)
        callback = getattr(module, "register_topic_statuses", None)
        if not callable(callback):
            continue
        registry = StatusRegistry(
            builtin_stages=list(_BUILTIN_AXIS),
            tool_prefix=package_name.removeprefix("goga_tool_"),
        )
        try:
            callback(registry)
        except Exception as exc:
            print(f"Warning: skipping status registration in {package_name}: {exc}", file=sys.stderr)
        for entry in registry.stages[len(_BUILTIN_AXIS) :]:
            try:
                index = _placement_index(stages, entry)
            except ValueError as exc:
                print(f"Warning: skipping status registration in {package_name}: {exc}", file=sys.stderr)
                continue
            stages.insert(index, entry)
    return StatusScale(stages=stages)


def _tool_packages() -> list[str]:
    """The installed ``goga_tool_*`` top-level names in alphabetical order."""
    return sorted(name for name in packages_distributions() if name.startswith("goga_tool_"))


def _import_tool_package(name: str) -> ModuleType:
    """Import one tool package — a broken import is a clean error naming the package.

    Raises:
        ImportError: The package failed to import.
    """
    try:
        return import_module(name)
    except Exception as exc:
        raise ImportError(f"package {name} failed to import: {exc}") from exc


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
