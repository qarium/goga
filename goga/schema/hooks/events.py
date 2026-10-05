"""The checkpoint surface of the schema domain — the events cell of the zone."""

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

    Args:
        cell: the authored facts handed over by the calling walk.

    Returns:
        The fresh delivery view of ``cell`` — every list rebuilt, so an in-place write stays local
            to the tool's own view and never reaches the caller's facts.
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

    Args:
        value: one value of a node's committed tools overlay, at any
            nesting level.

    Returns:
        The fresh deep copy of ``value`` — dicts and lists copied recursively, scalars pass as-is,
            and a tuple copies as a list.
    """
    if isinstance(value, dict):
        return {key: _copy_json(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_copy_json(item) for item in value]

    return value


def _copy_tree(nodes: list[SchemaNode]) -> list[SchemaNode]:
    """Build the delivery view of the final tree — fresh nodes and containers at every level.

    Args:
        nodes: the final assembled tree handed over by the calling walk.

    Returns:
        The fresh delivery view of ``nodes`` — every node rebuilt and every overlay value copied
            through ``_copy_json``, so a write stays local to the tool's own view.
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

    Args:
        tool: the tool identity of the committing view.
        cell_path: the path of the cell under delivery — carried into
            the failure message.
        pending: the buffered payloads of the tool's view.

    Returns:
        The owned deep copy of the tool's key-wise merged payloads — a later write replaces an
            earlier one; empty when the buffer merged to nothing.

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
    """The checkpoint surface of the schema domain — the staged cell-amendment delivery and the validation gate.

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
        """Create the checkpoint surface of one run — the run registry builds lazily on the first checkpoint."""
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

        Args:
            tree: The final assembled tree in tree order — the committed
                tools overlay included; operation data handed over by the
                calling walk.

        Returns:
            The :class:`~goga.schema.hooks.GateVerdict` — approved when no tool vetoed or crashed;
            the gate modifies nothing, acting on the verdict belongs to the caller.

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
