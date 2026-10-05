"""The checkpoint surface of the contract domain — the events cell of the zone."""

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
from .amendments import ContractAmendment
from .facts import CellFacts, TypeFacts
from .overlay import ToolContribution, merge_type_contributions


def _read_only_view(cell: CellFacts) -> CellFacts:
    """Build the delivery view of one cell's facts — fresh containers at every list.

    Args:
        cell: the comparison facts handed over by the calling command.

    Returns:
        The fresh delivery view of ``cell`` — every list rebuilt and every type re-recorded with
        fresh member lists; the frozen ``FormFacts`` / ``MemberFacts`` records are shared untouched.
    """
    return CellFacts(
        path=cell.path,
        types=[
            TypeFacts(
                name=declared.name,
                signature=declared.signature,
                properties=list(declared.properties),
                methods=list(declared.methods),
            )
            for declared in cell.types
        ],
    )


_JSON_MAP_DEPTH_LIMIT = 128
"""The nesting-depth limit of a merged contribution buffer.

The caller serializes the committed areas with the stdlib JSON encoder,
which spends more stack per nesting level than this validator: a buffer
past the limit could pass here and still crash the caller's dump with a
raw ``RecursionError``. The limit keeps the commit-time guarantee
absolute — everything committed is serializable — while sitting far
above any depth a real fact mapping reaches.
"""


def _nested_scope(value: object, where: str, ancestors: frozenset[int], depth: int) -> frozenset[int]:
    """Guard one container node of the buffer against unsafe descent — its nested scope.

    Args:
        value: the container node about to be descended into.
        where: the human-readable path of ``value`` within the buffer,
            carried into the failure detail.
        ancestors: the identities of the containers on the current
            recursion path.
        depth: the nesting level of ``value`` below the merged buffer —
            the depth guard of ``_check_json_map``.

    Returns:
        The scope of the values inside ``value`` — ``ancestors`` plus
        the identity of ``value`` itself.

    Raises:
        ValueError: ``value`` is one of its own ancestors — a container
            referencing itself is not JSON-representable — or sits
            deeper than ``_JSON_MAP_DEPTH_LIMIT`` — a container the
            caller's serializer could not carry either.
    """
    if id(value) in ancestors:
        raise ValueError(f"circular reference at {where}")

    if depth > _JSON_MAP_DEPTH_LIMIT:
        raise ValueError(f"nesting too deep at {where}")

    return ancestors | {id(value)}


def _check_json_map(
    value: object,
    where: str,
    ancestors: frozenset[int] = frozenset(),
    depth: int = 0,
) -> None:
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
        depth: the nesting level of ``value`` below the merged buffer —
            carried into ``_nested_scope``, whose depth guard rejects a
            container past ``_JSON_MAP_DEPTH_LIMIT``.

    Raises:
        ValueError: ``value`` violates the JSON-map shape — a non-``dict`` mapping, a non-string
            key, an empty mapping, a non-JSON value type (set, bytes, an arbitrary object), a
            non-finite float, a circular reference, or nesting deeper than
            ``_JSON_MAP_DEPTH_LIMIT``; the message is the structural detail of the hard failure.
    """
    if isinstance(value, dict):
        nested = _nested_scope(value, where, ancestors, depth)
        if not value:
            raise ValueError(f"empty mapping at {where}")

        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string key {key!r} at {where}")

            _check_json_map(item, f"{where}.{key}", nested, depth + 1)

        return

    if isinstance(value, (list, tuple)):
        nested = _nested_scope(value, where, ancestors, depth)
        for index, item in enumerate(value):
            _check_json_map(item, f"{where}[{index}]", nested, depth + 1)

        return

    if value is None or isinstance(value, (str, bool, int)):
        return

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite float at {where}")

        return

    raise ValueError(f"value of type {type(value).__name__} at {where}")


def _commit_tool_buffer(
    tool: str,
    cell_path: str,
    declared_names: set[str],
    pending: list[Any],
) -> dict[str, dict[str, object]]:
    """Merge and validate one tool's buffered payloads — the tool commit point.

    Args:
        tool: the tool identity of the committing view.
        cell_path: the path of the cell under delivery — carried into
            the failure messages.
        declared_names: the declared type names of the delivered cell —
            the address check of every committed type name.
        pending: the buffered payloads of the tool's view.

    Returns:
        The merged contribution of the tool — an owned deep copy of the validated buffer; empty
        when the buffer merged to nothing.

    Raises:
        ValueError: A payload is not a mapping or the merged buffer is
            structurally malformed — not representable in the JSON map,
            a nesting too deep for the validator or any exception
            raised walking an exotic ``Mapping`` included — or the
            merged buffer addresses a type the cell does not declare;
            every message names the tool, the action, the cell path,
            and the detail or the offending type name.
    """
    try:
        merged: dict[str, dict[str, object]] = {}

        for payload in pending:
            if not isinstance(payload, Mapping):
                raise ValueError(f"a contribution payload is not a mapping: {type(payload).__name__}")

            for type_name, facts in payload.items():
                if not isinstance(facts, Mapping):
                    raise ValueError(f"a type contribution is not a mapping: {type(facts).__name__}")

                if not isinstance(type_name, str):
                    raise ValueError(f"non-string key {type_name!r} at the merged contribution")

                merged.setdefault(type_name, {}).update(facts)

        if merged:
            _check_json_map(merged, "the merged contribution")
            # The ownership cut of the commit: dict.update shares every
            # nested container with the tool's buffer, and the tool's
            # context survives this checkpoint — without the copy, a
            # container the tool retained and mutated at a later cell
            # would write into this cell's already-validated area. The
            # copy walks only JSON-map-validated data, so a failure of
            # an exotic subclass here is the same structural
            # malformation as anywhere else in the walk.
            merged = copy.deepcopy(merged)

    except Exception as reason:
        # The try block reads nothing but the tool's own buffered
        # payloads and the pure validator over the merged result, so
        # any exception out of it is a structural malformation of the
        # contribution — the same clean, tool-attributed failure as
        # any other malformed buffer, never a raw escape.
        raise ValueError(
            f"tool {tool} failed on contract.amend_contract at {cell_path}: "
            f"structurally malformed contribution ({reason})"
        ) from reason

    for type_name in merged:
        if type_name not in declared_names:
            raise ValueError(
                f"tool {tool} failed on contract.amend_contract at {cell_path}: "
                f"contribution addresses undeclared type {type_name}"
            )

    return merged


class ContractHooks:
    """The checkpoint surface of the contract domain — a tool's contribution commits only after all its hooks succeed.

    Requirements:
        - Cheap construction — no enumeration and no imports happen at
          construction
        - One ``HookRegistry`` per run carries every checkpoint of a
          command — the assembly runs once per run whatever the number
          of checkpoints
        - Every context is built from the values the caller passes — no
          configuration, git, or file reads happen at the checkpoint
    """

    def __init__(self) -> None:
        """Create the checkpoint surface of one run."""
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

    def amend_contract(self, cell: CellFacts) -> dict[str, dict[str, dict[str, object]]]:
        """Deliver the contract-amendment checkpoint and return the tools area.

        Algorithm:
            1. Resolve the address ``contract.amend_contract`` against
               ``declared_actions`` — an unknown address is a clean error
               of the emitting side
            2. Walk the subscriptions of the address per tool in
               enumeration order: build the tool's ``ContractAmendment``
               view over a fresh copy of the comparison facts — every
               tool reads its own fresh view of the same compared values,
               so no tool's in-place write reaches another tool's view or
               the caller's facts — wrap it via ``wrap_context``, project
               the call arguments via ``build_hook_arguments`` with the
               tool's own context, and call each hook of the tool
            3. A tool whose every hook returned without raising passes
               the structural check of its merged buffer: each payload
               must be a ``Mapping``, each addressed fact mapping a
               ``Mapping`` again, the payloads merge per addressed type
               fact-wise with the later write replacing the earlier on
               conflict, and the merged buffer must satisfy the JSON-map
               shape and address declared types only — anything else is
               the same hard failure as a crashed hook
            4. A passing tool commits as one ``ToolContribution``; an
               empty merged buffer commits nothing, silently
            5. A hard failure stops the delivery at the first failure in
               the walk — a clean error naming the tool, the action, and
               the failing cell path, and the offending type name for a
               bad address; the tool's whole contribution is discarded
               together with its view
            6. Return ``merge_type_contributions`` over the committed
               contributions — an address without subscriptions returns
               the empty mapping

        Args:
            cell: The comparison facts of the cell being amended —
                operation data handed over by the calling command.

        Returns:
            The tools area per addressed type name — each contributing tool's fact mapping under
            its tool identity inside that type's area; empty when nothing committed — the zone
            never prints.

        Raises:
            ValueError: The address is not declared, a hook of the hard
                action failed — the message names the hook, the tool,
                the action, the cell path, and the reason — or a
                contribution is structurally malformed or addresses an
                undeclared type — the message names the tool, the
                action, the cell path, and the detail or the offending
                type name.
        """
        registry = self._ensure_registry()

        record = next(
            (entry for entry in declared_actions() if entry.domain == "contract" and entry.name == "amend_contract"),
            None,
        )
        if record is None:
            raise ValueError("unknown hook action: contract.amend_contract")

        declared_names = {declared.name for declared in cell.types}

        groups: dict[str, list[Any]] = {}

        for subscription in registry.subscriptions_for("contract", "amend_contract"):
            groups.setdefault(subscription.tool, []).append(subscription)

        contributions: list[ToolContribution] = []

        for tool, subscriptions in groups.items():
            # A fresh view per tool — value-identical reads of the
            # comparison facts with fresh lists at every level, so no
            # in-place write reaches the caller's facts or another
            # tool's view: a list write stays local to the tool's own
            # view and dies with it. The view dies with the tool when a
            # hook fails, taking the buffer with it.
            amendment = ContractAmendment(cell=_read_only_view(cell))
            proxy = wrap_context(amendment)

            for subscription in subscriptions:
                try:
                    subscription.hook(**build_hook_arguments(subscription.hook, proxy, registry.self_context(tool)))
                except Exception as reason:
                    # Hard: stop at the first failure. The message copies
                    # the platform format — hook name, tool, address,
                    # reason — and names the failing cell.
                    raise ValueError(
                        f"hook {subscription.name} of tool {tool} failed on contract.amend_contract "
                        f"at {cell.path}: {reason}"
                    ) from reason

            # The commit granularity is the tool: only after every hook
            # of the tool succeeded does the buffer merge — each payload
            # guarded as a Mapping before the update, because
            # dict.update would silently accept an iterable of
            # key-value pairs and coerce it into a mapping — and the
            # merged buffer must carry the JSON-map shape and declared
            # type addresses only before anything commits. An empty
            # merged buffer commits nothing, silently.
            merged = _commit_tool_buffer(tool, cell.path, declared_names, amendment._pending)

            if merged:
                contributions.append(ToolContribution(tool=tool, facts=merged))

        return merge_type_contributions(contributions)
