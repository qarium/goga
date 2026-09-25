"""The checkpoint surface of the schema domain — the events cell of the zone.

The entity declared in the cell CODEMANIFEST with ``location: events.py``:
``SchemaHooks`` — the staged per-tool delivery of the hard
``schema/amend_cell`` action over the platform facade. Construction is
cheap and every context is built from the values the caller passes; one
lazily-built run registry carries every checkpoint of a walk, so the
package enumeration happens once per run whatever the number of cells.
Every tool reads a fresh copy of the same authored facts — no tool's
in-place write reaches another tool's view or the caller's facts — and a
tool's contribution commits only after every hook of the tool succeeded:
its buffer merged key-wise and validated against the JSON-map shape. The
action is hard — the first failing tool stops the walk with a clean error
naming the tool, the action, and the failing cell — and the zone never
prints: the tools area is data the caller places on the node.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from ...hooks import (
    HookRegistry,
    build_hook_arguments,
    declared_actions,
    wrap_context,
)
from .amendments import CellAmendment
from .facts import CellFacts, DependencyFacts
from .overlay import ToolContribution, merge_cell_contributions


def _read_only_view(cell: CellFacts) -> CellFacts:
    """Build the delivery view of one cell's facts — fresh containers at every level.

    The frozen record closes field writes, but the list-valued fields
    would otherwise reach the hook as the caller's live lists: an
    in-place ``types.append(...)`` would mutate the caller's facts and
    become visible to every later tool. The fresh copy closes that
    channel: every list is rebuilt and every dependency re-recorded, so
    a write stays local to the tool's own view and dies with it — reads,
    equality, and iteration are unchanged. It is not an optimization:
    it is the mutual-blindness guarantee between tools.

    Args:
        cell: the authored facts handed over by the calling walk.

    Returns:
        The fresh delivery view of ``cell``.
    """
    return CellFacts(
        path=cell.path,
        description=cell.description,
        types=list(cell.types),
        usages=list(cell.usages),
        dependencies=[
            DependencyFacts(path=dependency.path, types=list(dependency.types), usages=list(dependency.usages))
            for dependency in cell.dependencies
        ],
        children=list(cell.children),
    )


def _nested_scope(value: object, where: str, ancestors: frozenset[int]) -> frozenset[int]:
    """Guard one container node of the buffer against cycles — its nested scope.

    Args:
        value: the container node about to be descended into.
        where: the human-readable path of ``value`` within the buffer,
            carried into the failure detail.
        ancestors: the identities of the containers on the current
            recursion path.

    Returns:
        The scope of the values inside ``value`` — ``ancestors`` plus
        the identity of ``value`` itself.

    Raises:
        ValueError: ``value`` is one of its own ancestors — a container
            referencing itself is not JSON-representable.
    """
    if id(value) in ancestors:
        raise ValueError(f"circular reference at {where}")

    return ancestors | {id(value)}


def _check_json_map(value: object, where: str, ancestors: frozenset[int] = frozenset()) -> None:
    """Validate one node of a merged contribution buffer — the JSON-map shape.

    An explicit recursive validator, not a ``json.dumps`` probe: dumps
    coerces non-string keys into strings and accepts ``nan`` /
    ``infinity`` literals, both of which must fail here. A mapping
    anywhere under the buffer must be a plain ``dict`` with string keys
    only and at least one entry — any other ``Mapping`` and a container
    referencing itself are not JSON-representable, so they fail here
    like any other non-JSON value instead of crashing the caller's
    serialization. A value must be a dict (same rules, recursively), a
    list or tuple of recursively-checked items, or a JSON scalar —
    ``str``, ``int``, ``bool``, ``None``, or a finite ``float``.
    Everything else — a set, bytes, an arbitrary object, a non-finite
    float, a non-string key, an empty mapping — is rejected.

    Args:
        value: one node of the merged buffer — the top level or any
            nested value.
        where: the human-readable path of ``value`` within the buffer,
            carried into the failure detail.
        ancestors: the identities of the containers on the current
            recursion path — the cycle guard. A container shared twice
            in different places stays valid (JSON allows it); only a
            container holding an ancestor is rejected.

    Raises:
        ValueError: ``value`` violates the JSON-map shape — the message
            is the structural detail of the hard failure.
    """
    if isinstance(value, dict):
        nested = _nested_scope(value, where, ancestors)
        if not value:
            raise ValueError(f"empty mapping at {where}")

        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string key {key!r} at {where}")

            _check_json_map(item, f"{where}.{key}", nested)

        return

    if isinstance(value, (list, tuple)):
        nested = _nested_scope(value, where, ancestors)
        for index, item in enumerate(value):
            _check_json_map(item, f"{where}[{index}]", nested)

        return

    if value is None or isinstance(value, (str, bool, int)):
        return

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite float at {where}")

        return

    raise ValueError(f"value of type {type(value).__name__} at {where}")


def _commit_tool_buffer(tool: str, cell_path: str, pending: list[Any]) -> dict[str, object]:
    """Merge and validate one tool's buffered payloads — the tool commit point.

    Each buffered payload must be a ``Mapping`` — an iterable of
    key-value pairs is a structural failure, never a silent coercion
    into a mapping — and the payloads merge key-wise with the later
    write replacing the earlier on conflict. The merged buffer must
    satisfy the JSON-map shape before anything commits; an empty merged
    buffer commits nothing, silently.

    Args:
        tool: the tool identity of the committing view.
        cell_path: the path of the cell under delivery — carried into
            the failure message.
        pending: the buffered payloads of the tool's view.

    Returns:
        The merged contribution of the tool — empty when the buffer
        merged to nothing.

    Raises:
        ValueError: A payload is not a mapping or the merged buffer is
            structurally malformed — not representable in the JSON map,
            a nesting too deep for the validator included — the message
            names the tool, the action, the cell path, and the detail.
    """
    try:
        merged: dict[str, object] = {}
        for payload in pending:
            if not isinstance(payload, Mapping):
                raise ValueError(f"a contribution payload is not a mapping: {type(payload).__name__}")

            merged.update(payload)

        if merged:
            _check_json_map(merged, "the merged contribution")

    except (ValueError, RecursionError) as reason:
        raise ValueError(
            f"tool {tool} failed on schema.amend_cell at {cell_path}: "
            f"structurally malformed contribution ({reason})"
        ) from reason

    return merged


class SchemaHooks:
    """The checkpoint surface of the schema domain.

    Owns the single run registry of the generation walk and drives the
    cell-amendment delivery per tool with staged commit over the public
    primitives of the hooks platform. Tools are mutually blind — every
    amendment view reads a fresh copy of the same authored facts, never
    another tool's contribution; a tool's contribution commits only after
    every hook of the tool succeeded.

    Requirements:
        - Cheap construction — no enumeration and no imports happen at
          construction
        - One ``HookRegistry`` per run carries every checkpoint of a
          walk — the assembly runs once per run whatever the number of
          checkpoints
        - Every context is built from the values the caller passes — no
          repository, git, or file reads happen at the checkpoint
    """

    def __init__(self) -> None:
        """Create the checkpoint surface of one run.

        Nothing is enumerated and nothing is imported: the run registry
        builds lazily on the first checkpoint that needs it.
        """
        self._registry: HookRegistry | None = None

    def _ensure_registry(self) -> HookRegistry:
        """Build the run registry once — the shared state of every checkpoint.

        Returns:
            The assembled registry of the run — built on the first call and
            reused by every checkpoint; never rebuilt on the same surface.

        Raises:
            ImportError: A tool package exists but its facade fails to
                import — the single fatal case; the message names the
                package.
        """
        if self._registry is None:
            registry = HookRegistry()
            registry.build_once()
            self._registry = registry

        return self._registry

    def amend_cell(self, cell: CellFacts) -> dict[str, dict[str, object]]:
        """Deliver the cell-amendment checkpoint and return the tools area.

        Algorithm:
            1. Resolve the address ``schema.amend_cell`` against
               ``declared_actions`` — an unknown address is a clean error
               of the emitting side
            2. Walk the subscriptions of the address per tool in
               enumeration order: build the tool's ``CellAmendment`` view
               over a fresh copy of the authored facts — every tool reads
               its own fresh view of the same authored values, so no
               tool's in-place write reaches another tool's view or the
               caller's facts — wrap it via ``wrap_context``, project the
               call arguments via ``build_hook_arguments`` with the
               tool's own context, and call each hook of the tool
            3. A tool whose every hook returned without raising commits
               its merged buffer as one ``ToolContribution``: each
               buffered payload must be a ``Mapping`` — an iterable of
               key-value pairs is a structural failure, never a silent
               coercion into a mapping — the payloads merge key-wise
               with the later write replacing the earlier on conflict,
               and the merged buffer must satisfy the JSON-map shape; an
               empty merged buffer commits nothing, silently
            4. A tool with a raising hook is a hard failure: a clean
               error naming the hook, the tool, the action, and the
               failing cell stops the walk at the first failure; the
               tool's whole contribution is discarded together with its
               view
            5. Return ``merge_cell_contributions`` over the committed
               contributions — an address without subscriptions returns
               the empty mapping

        The zone never prints: the tools area is data the caller places
        on the node.

        Args:
            cell: The authored facts of the cell being built — operation
                data handed over by the calling walk.

        Returns:
            The tools area of the cell node — each non-empty merged
            contribution under its tool identity key; empty when nothing
            committed.

        Raises:
            ValueError: The address is not declared, a hook of the hard
                action failed — the message names the hook, the tool,
                the action, the cell path, and the reason — or a
                contribution is structurally malformed — the message
                names the tool, the action, the cell path, and the
                detail.
        """
        registry = self._ensure_registry()

        record = next(
            (entry for entry in declared_actions() if entry.domain == "schema" and entry.name == "amend_cell"),
            None,
        )
        if record is None:
            raise ValueError("unknown hook action: schema.amend_cell")

        groups: dict[str, list[Any]] = {}
        for subscription in registry.subscriptions_for("schema", "amend_cell"):
            groups.setdefault(subscription.tool, []).append(subscription)

        contributions: list[ToolContribution] = []

        for tool, subscriptions in groups.items():
            # A fresh view per tool — value-identical reads of the
            # authored facts with fresh lists at every level, so no
            # in-place write reaches the caller's facts or another
            # tool's view: a list write stays local to the tool's own
            # view and dies with it. The view dies with the tool when a
            # hook fails, taking the buffer with it.
            amendment = CellAmendment(cell=_read_only_view(cell))
            proxy = wrap_context(amendment)

            for subscription in subscriptions:
                try:
                    subscription.hook(**build_hook_arguments(subscription.hook, proxy, registry.self_context(tool)))
                except Exception as reason:
                    # Hard: stop at the first failure. The message copies
                    # the pipeline-zone format — hook name, tool,
                    # address, reason — and names the failing cell.
                    raise ValueError(
                        f"hook {subscription.name} of tool {tool} failed on schema.amend_cell at {cell.path}: {reason}"
                    ) from reason

            # The commit granularity is the tool: only after every hook
            # of the tool succeeded does the buffer merge — each payload
            # guarded as a Mapping before the update, because
            # dict.update would silently accept an iterable of
            # key-value pairs and coerce it into a mapping — and the
            # merged buffer must carry the JSON-map shape before
            # anything commits. An empty merged buffer commits nothing,
            # silently.
            merged = _commit_tool_buffer(tool, cell.path, amendment._pending)

            if merged:
                contributions.append(ToolContribution(tool=tool, facts=merged))

        return merge_cell_contributions(contributions)
