"""The checkpoint surface of the schema domain — the events cell of the zone.

The entity declared in the cell CODEMANIFEST with ``location: events.py``:
``SchemaHooks`` — the staged per-tool delivery of the hard
``schema/amend_cell`` action and the verdict-collecting gate delivery of
the hard ``schema/validate_schema`` action, both over the platform
facade. Construction is cheap and every context is built from the values
the caller passes; one lazily-built run registry carries every
checkpoint of a walk, so the package enumeration happens once per run
whatever the number of cells. Every tool reads a fresh copy of the same
delivered facts — no tool's in-place write reaches another tool's view
or the caller's facts, the committed tools overlay of the final tree
included — and a tool's contribution commits only after every hook of
the tool succeeded: its buffer merged key-wise, validated against the
JSON-map shape, and committed as an owned copy — a container the tool
retains and mutates at a later cell never reaches the committed area.
The amendment action is hard — the first failing tool stops the walk
with a clean error naming the tool, the action, and the failing cell.
The gate follows the same staged walk with one domain-local deviation:
it never stops early — every subscribed tool's validation hooks run to
completion and the vetoes and crashes are collected into one verdict,
one violation per tool. The zone never prints: the tools area and the
verdict are data the caller acts on.
"""

from __future__ import annotations

import copy
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
from .contexts import SchemaValidation
from .facts import CellFacts, DependencyFacts, GateVerdict, SchemaNode, Violation
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


def _copy_json(value: object) -> object:
    """Copy one committed overlay value — fresh containers at every level.

    The JSON-shape domain of a committed contribution — validated at the
    tool commit point of ``amend_cell`` — covers exactly these forms: a
    ``dict`` copies to a fresh dict with every value copied recursively,
    a ``list`` — or a ``tuple``, which the commit point admits as a list
    — to a fresh list with every item copied recursively, and any scalar
    passes as-is. A tuple copies as a list because the delivered view
    represents the serialized result, where the two are one JSON array;
    passing a tuple through by identity would share its nested
    containers with the caller's serialized tree. The copy extends the
    mutual-blindness guarantee of ``_read_only_view`` to the gate: the
    caller's projection — nested overlay values included — is never
    shared with a tool.

    Args:
        value: one value of a node's committed tools overlay, at any
            nesting level.

    Returns:
        The fresh deep copy of ``value``.
    """
    if isinstance(value, dict):
        return {key: _copy_json(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_copy_json(item) for item in value]

    return value


def _copy_tree(nodes: list[SchemaNode]) -> list[SchemaNode]:
    """Build the delivery view of the final tree — fresh nodes and containers at every level.

    The frozen record closes field writes, but the list- and
    dict-valued fields would otherwise reach the hook as the caller's
    live containers: an in-place ``types.append(...)`` would mutate the
    caller's tree and a nested overlay write would pierce every later
    tool's view. The fresh copy closes both channels: every node is
    rebuilt, every list and dependency re-recorded, and every committed
    overlay value copied through ``_copy_json``, so a write stays local
    to the tool's own view and dies with it. It is not an optimization:
    it is the mutual-blindness guarantee of ``_read_only_view`` extended
    to the gate — the delivered view carries the final result, the tools
    overlay included, a recorded exception to the authored-facts-only
    delivery rule.

    Args:
        nodes: the final assembled tree handed over by the calling walk.

    Returns:
        The fresh delivery view of ``nodes``.
    """
    return [
        SchemaNode(
            path=node.path,
            description=node.description,
            types=list(node.types),
            usages=list(node.usages),
            dependencies=[
                DependencyFacts(path=dependency.path, types=list(dependency.types), usages=list(dependency.usages))
                for dependency in node.dependencies
            ],
            children=_copy_tree(node.children),
            tools={tool: _copy_json(facts) for tool, facts in node.tools.items()},
        )
        for node in nodes
    ]


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
    buffer commits nothing, silently. What commits is an owned deep copy
    of the validated buffer: the merge shares every nested container
    with the tool's buffer, and the tool's context survives the
    checkpoint — a container the tool retained and mutated at a later
    cell would otherwise write into this cell's already-validated area.

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
            # The ownership cut of the commit: without the copy, a
            # container the tool retained on its context and mutated at
            # a later cell would write into this cell's
            # already-validated area.
            merged = copy.deepcopy(merged)

    except (ValueError, RecursionError) as reason:
        raise ValueError(
            f"tool {tool} failed on schema.amend_cell at {cell_path}: structurally malformed contribution ({reason})"
        ) from reason

    return merged


class SchemaHooks:
    """The checkpoint surface of the schema domain.

    Owns the single run registry of the generation walk and drives the
    cell-amendment delivery per tool with staged commit, plus the
    validation gate over the final assembled tree, over the public
    primitives of the hooks platform. Tools are mutually blind — every
    amendment view reads a fresh copy of the same authored facts, never
    another tool's contribution; a tool's contribution commits only after
    every hook of the tool succeeded. The gate walks the same staging
    with one domain-local deviation — it never stops early: every
    subscribed tool's validation hooks run to completion and the vetoes
    and crashes collect into one verdict, one violation per tool.

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

    def validate_schema(self, tree: list[SchemaNode]) -> GateVerdict:
        """Deliver the validation gate over the final tree and return the collected verdict.

        Algorithm:
            1. Resolve the address ``schema.validate_schema`` against
               ``declared_actions`` — an unknown address is a clean error
               of the emitting side
            2. Walk the subscriptions of the address per tool in
               enumeration order: build the tool's ``SchemaValidation``
               view over a fresh copy of the final tree — every tool
               reads its own fresh view of the same assembled nodes, the
               committed tools overlay included, so no tool's in-place
               write reaches another tool's view or the caller's tree —
               wrap it via ``wrap_context``, project the call arguments
               via ``build_hook_arguments`` with the tool's own context,
               and call each hook of the tool; the veto buffer is
               snapshotted before each call — a buffer change during a
               call attributes the veto to that hook's subscription name
            3. A raising hook is the tool's single crash violation — the
               crash reason, never a raw traceback — and stops that
               tool's remaining hooks; the crash overrides the tool's
               buffered veto; the walk continues with the next tool and
               never stops between tools whatever a tool returned or
               raised
            4. A tool whose every hook returned and whose view carries a
               buffered veto contributes exactly one ``Violation`` with
               the attributed hook; a tool whose buffer stayed empty
               approves silently — no record
            5. Return the ``GateVerdict`` with the violations in
               enumeration order — an address without subscriptions
               returns the empty, approved verdict

        The gate modifies nothing and never prints: the verdict is data,
        and acting on it — the merged error, the exit code — belongs to
        the calling operation.

        Args:
            tree: The final assembled tree in tree order — the committed
                tools overlay included; operation data handed over by the
                calling walk.

        Returns:
            The :class:`~goga.schema.hooks.GateVerdict` — approved when
            no tool vetoed or crashed.

        Raises:
            ValueError: The address is not declared.
        """
        registry = self._ensure_registry()

        record = next(
            (entry for entry in declared_actions() if entry.domain == "schema" and entry.name == "validate_schema"),
            None,
        )
        if record is None:
            raise ValueError("unknown hook action: schema.validate_schema")

        groups: dict[str, list[Any]] = {}
        for subscription in registry.subscriptions_for("schema", "validate_schema"):
            groups.setdefault(subscription.tool, []).append(subscription)

        violations: list[Violation] = []

        for tool, subscriptions in groups.items():
            # A fresh view per tool — value-identical reads of the final
            # tree with fresh nodes and containers at every level, the
            # committed tools overlay included, so no in-place write
            # reaches the caller's tree or another tool's view: a write
            # stays local to the tool's own view and dies with it.
            view = SchemaValidation(tree=_copy_tree(tree))
            proxy = wrap_context(view)

            attributed_hook = ""
            crash: tuple[str, str] | None = None

            for subscription in subscriptions:
                before = view._veto
                try:
                    subscription.hook(**build_hook_arguments(subscription.hook, proxy, registry.self_context(tool)))
                except Exception as reason:
                    # One crash violation for the tool — the crash reason
                    # overrides any buffered veto; the tool's remaining
                    # hooks stop, the walk does not.
                    crash = (subscription.name, str(reason))
                    break

                if view._veto != before:
                    attributed_hook = subscription.name

            if crash is not None:
                violations.append(Violation(tool=tool, hook=crash[0], reason=crash[1]))
            elif view._veto is not None:
                # The buffer only changes through veto(), so a non-empty
                # buffer always carries an observed attribution.
                violations.append(Violation(tool=tool, hook=attributed_hook, reason=view._veto))

        return GateVerdict(violations=violations)
