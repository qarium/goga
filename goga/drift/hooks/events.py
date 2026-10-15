"""The checkpoint surface of the drift domain — the events cell of the zone."""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ...hooks import (
    HookRegistry,
    build_hook_arguments,
    declared_actions,
    emit_hook_event,
    wrap_context,
)
from .amendments import EntryAmendment, ReportAmendment
from .facts import DriftFilters, EntryFacts, RunCompletion
from .overlay import ToolContribution, merge_entry_contributions

_ENTRY_KINDS = frozenset({"schema_only", "codegraph_only"})
"""The closed value set of an adjusted entry's kind — the comparison's entry kinds."""


def _read_only_view(entry: EntryFacts) -> EntryFacts:
    """Build the delivery view of one entry's facts — fresh containers at every level.

    Args:
        entry: the comparison-computed facts handed over by the calling walk.

    Returns:
        The fresh delivery view of ``entry`` — the type list rebuilt, so an in-place
            write stays local to the tool's own view and never reaches the caller's
            facts.
    """
    return EntryFacts(
        kind=entry.kind,
        cell=entry.cell,
        types=list(entry.types) if entry.types is not None else None,
    )


def _copy_json(value: object) -> object:
    """Copy one committed overlay value — fresh containers at every level.

    Args:
        value: one value of an entry's committed tools overlay, at any
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


def _commit_tool_buffer(tool: str, entry_subject: str, pending: list[Any]) -> dict[str, object]:
    """Merge and validate one tool's buffered payloads — the tool commit point.

    Args:
        tool: the tool identity of the committing view.
        entry_subject: the kind and cell path of the entry under delivery —
            carried into the failure message.
        pending: the buffered payloads of the tool's view.

    Returns:
        The owned deep copy of the tool's key-wise merged payloads — a later write replaces an
            earlier one; empty when the buffer merged to nothing.

    Raises:
        ValueError: A payload is not a mapping or the merged buffer is
            structurally malformed — not representable in the JSON map,
            a nesting too deep for the validator included — the message
            names the tool, the action, the entry subject, and the detail.
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
            # container the tool retained on its context and mutated at a
            # later entry would write into this entry's
            # already-validated area.
            merged = copy.deepcopy(merged)

    except (ValueError, RecursionError) as reason:
        raise ValueError(
            f"tool {tool} failed on drift.amend_entry at {entry_subject}: "
            f"structurally malformed contribution ({reason})"
        ) from reason

    return merged


def _check_adjusted_entry(entry: object, index: int) -> None:
    """Validate one entry of a buffered adjustment — the closed kind/cell/types shape.

    Args:
        entry: one entry of the adjusted list — a mapping at most.
        index: the position of ``entry`` in the adjusted list — carried
            into the failure detail.

    Raises:
        ValueError: ``entry`` violates the closed shape — the message is
            the structural detail of the hard failure; the entry is never
            sanitized, never adopted.
    """
    if not isinstance(entry, Mapping):
        raise ValueError(f"entry {index} is not a mapping: {type(entry).__name__}")

    where = f"entry {index}"
    extra = set(entry) - {"kind", "cell", "types"}

    if extra:
        # repr-keyed: extra keys of mixed types stay orderable, so the
        # structural detail never escapes as a raw TypeError.
        raise ValueError(f"{where} carries keys outside kind/cell/types: {sorted(extra, key=repr)}")

    if "kind" not in entry:
        raise ValueError(f"{where} carries no kind")

    # the isinstance guard keeps an unhashable kind inside the clean
    # failure — set membership would raise a bare TypeError instead.
    if not isinstance(entry["kind"], str) or entry["kind"] not in _ENTRY_KINDS:
        raise ValueError(f"{where} carries an unknown kind: {entry['kind']!r}")

    if "cell" not in entry:
        raise ValueError(f"{where} carries no cell")

    if not isinstance(entry["cell"], str):
        raise ValueError(f"{where} carries a non-string cell: {type(entry['cell']).__name__}")

    if entry["cell"] == "":
        raise ValueError(f"{where} carries an empty cell")

    if "types" in entry:
        _check_adjusted_types(entry["types"], where)


def _check_adjusted_types(types: object, where: str) -> None:
    """Validate the types list of one adjusted entry — a list whose every element is a string.

    Args:
        types: the adjusted entry's types value — a list at most; an
            empty list is carried verbatim — the contract admits a list
            of strings.
        where: the human-readable path of the owning entry — carried
            into the failure detail.

    Raises:
        ValueError: ``types`` violates the shape — not a list, or an
            element that is not a string; the entry is never sanitized,
            never adopted.
    """
    if not isinstance(types, list):
        raise ValueError(f"{where} carries a non-list types: {type(types).__name__}")

    for position, name in enumerate(types):
        if not isinstance(name, str):
            raise ValueError(f"{where} carries a non-string type at {position}: {type(name).__name__}")


def _validate_adjustment(tool: str, attributed: str, adjustment: object) -> list[dict[str, object]]:
    """Validate one tool's buffered adjustment — the closed-shape check of the report amendment.

    Args:
        tool: the tool identity of the adjusting view.
        attributed: the subscription name of the hook that wrote the
            adjustment — carried into the failure message.
        adjustment: the buffered payload of the tool's view — the whole
            replacement list.

    Returns:
        The validated adjustment — the adjusted list of entry mappings,
            each of exactly the closed kind/cell/types shape.

    Raises:
        ValueError: The adjustment violates the closed shape — the
            message names the attributed hook, the tool, the action, and
            the structural detail; the adjustment is never adopted, never
            sanitized.
    """
    try:
        if not isinstance(adjustment, list):
            raise ValueError(f"the adjustment is not a list: {type(adjustment).__name__}")

        for index, entry in enumerate(adjustment):
            _check_adjusted_entry(entry, index)

    except ValueError as reason:
        raise ValueError(
            f"hook {attributed} of tool {tool} failed on drift.amend_report: malformed adjustment ({reason})"
        ) from reason

    return adjustment


@dataclass(frozen=True, kw_only=True)
class _RunStarted:
    """The delivery wrapper of the start moment — the filters as the hook's context."""

    filters: DriftFilters


@dataclass(frozen=True, kw_only=True)
class _RunCompleted:
    """The delivery wrapper of the completion moment — the terminal facts as the hook's context."""

    completion: RunCompletion


class DriftHooks:
    """The checkpoint surface of the drift domain — the run moments and the two amendments.

    Requirements:
        - Cheap construction — no enumeration and no imports happen at
          construction
        - One ``HookRegistry`` per run carries every checkpoint of a
          command — the moments and the amendments share one assembly
          whatever the number of checkpoints
        - Every context is built from the values the caller passes — no
          configuration reads, no repository, git, or file reads happen at
          a checkpoint
        - No fact carries a credential-bearing value
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
                import — the single fatal platform case; the message names the
                package.
        """
        if self._registry is None:
            registry = HookRegistry()
            registry.build_once()
            self._registry = registry

        return self._registry

    def emit_run_started(self, filters: DriftFilters) -> None:
        """Emit the run-started moment — fire-and-forget; a failing hook only warns.

        Algorithm:
            1. Build the shared frozen context of the moment — one
               ``_RunStarted`` wrapper over the caller's filters, handed
               to every subscribing tool unchanged
            2. Deliver through the platform ``emit_hook_event`` — the
               soft error class of the address: a raising hook is a
               warning in the log naming the hook, the tool, and the
               reason, the sequence continues; no raise path for hook
               failures

        Args:
            filters: The filters of the starting run — the run's own
                inputs; operation data handed over by the calling routine.
        """
        context = _RunStarted(filters=filters)

        emit_hook_event(
            self._ensure_registry(),
            "drift",
            "run_started",
            context_for=lambda _tool: context,
        )

    def emit_run_completed(self, completion: RunCompletion) -> None:
        """Emit the run-completed moment on every terminal state — fire-and-forget; a failing hook only warns.

        Algorithm:
            1. Build the shared frozen context of the moment — one
               ``_RunCompleted`` wrapper over the caller's terminal
               facts, handed to every subscribing tool unchanged
            2. Deliver through the platform ``emit_hook_event`` — the
               soft error class of the address: a raising hook is a
               warning in the log naming the hook, the tool, and the
               reason, the sequence continues; no raise path for hook
               failures

        Args:
            completion: The terminal facts of the finished or crashed run
                — the last computed report stage, the outcome marker, the
                credential-free reason; operation data handed over by the
                calling routine.
        """
        context = _RunCompleted(completion=completion)

        emit_hook_event(
            self._ensure_registry(),
            "drift",
            "run_completed",
            context_for=lambda _tool: context,
        )

    def amend_report(self, report: list[EntryFacts]) -> list[EntryFacts]:
        """Deliver the report-amendment checkpoint and return the settled report.

        Algorithm:
            1. Resolve the address ``drift.amend_report`` against
               ``declared_actions`` — an unknown address is a clean error
               of the emitting side
            2. Seed the settled list with fresh copies of the finished
               scoped report — the working list; the input is never
               mutated
            3. Walk the subscriptions of the address per tool in
               enumeration order: build the tool's ``ReportAmendment``
               view over fresh copies of the ORIGINAL report — amending
               tools are mutually blind, every tool reads the same
               finished scoped report, never another tool's adjustment —
               wrap it via ``wrap_context``, project the call arguments
               via ``build_hook_arguments`` with the tool's own context,
               and call each hook of the tool; the adjustment buffer is
               snapshotted before each call — a buffer change during a
               call attributes the adjustment to that hook's subscription
               name
            4. A raising hook is a hard failure: a clean error naming the
               hook, the tool, the action, and the reason stops the walk
               at the first failure; nothing is adopted
            5. A tool whose every hook returned and whose view carries a
               buffered adjustment passes the closed-shape check — each
               entry exactly kind, cell, and types; the validated
               adjustment replaces the settled list whole — a later
               adjusting tool wins over the earlier, the replacement is
               never a chained merge; an empty adjusted list clears the
               report and a tool-added entry settles into it; no
               adjustment provenance is recorded or returned anywhere
            6. Return the settled list — an address without subscriptions
               returns value-identical fresh copies of the input

        Args:
            report: The finished scoped report — the comparison-computed
                entries; operation data handed over by the calling
                routine.

        Returns:
            The settled report — the post-amendment list of entry facts; the last
                adjusting tool's whole replacement when any tool adjusted,
                fresh copies of the input otherwise.

        Raises:
            ValueError: The address is not declared, a hook of the hard
                action failed — the message names the hook, the tool, the
                action, and the reason — or an adjustment violates the
                closed kind/cell/types shape — the message names the
                attributed hook, the tool, the action, and the detail; a
                malformed adjustment is never adopted, never sanitized.
        """
        registry = self._ensure_registry()

        record = next(
            (entry for entry in declared_actions() if entry.domain == "drift" and entry.name == "amend_report"),
            None,
        )
        if record is None:
            raise ValueError("unknown hook action: drift.amend_report")

        groups: dict[str, list[Any]] = {}

        for subscription in registry.subscriptions_for("drift", "amend_report"):
            groups.setdefault(subscription.tool, []).append(subscription)

        current = [_read_only_view(entry) for entry in report]

        for tool, subscriptions in groups.items():
            # A fresh view per tool over the ORIGINAL report — mutual
            # blindness: every tool reads the comparison-computed entries
            # only, never another tool's adjustment. The view dies with
            # the tool when a hook fails, taking the buffer with it.
            view = ReportAmendment(report=[_read_only_view(entry) for entry in report])
            proxy = wrap_context(view)
            attributed_hook = ""

            for subscription in subscriptions:
                before = view._adjustment

                try:
                    subscription.hook(**build_hook_arguments(subscription.hook, proxy, registry.self_context(tool)))
                except Exception as reason:
                    # Hard: stop at the first failure. The message copies
                    # the platform's format — hook name, tool, address,
                    # reason — and nothing of the tool is adopted.
                    raise ValueError(
                        f"hook {subscription.name} of tool {tool} failed on drift.amend_report: {reason}"
                    ) from reason

                if view._adjustment is not before:
                    attributed_hook = subscription.name

            if view._adjustment is None:
                continue  # never adjusted — silent, the settled list stands

            # The closed shape or the hard failure — never sanitized,
            # never adopted on a violation; the validated replacement
            # settles whole, the later adjusting tool winning.
            entries = _validate_adjustment(tool, attributed_hook, view._adjustment)
            current = [
                EntryFacts(
                    kind=entry["kind"],
                    cell=entry["cell"],
                    types=list(entry["types"]) if "types" in entry else None,
                )
                for entry in entries
            ]

        return current

    def amend_entry(self, entry: EntryFacts) -> dict[str, dict[str, object]]:
        """Deliver the entry-amendment checkpoint for one entry and return its tools area.

        Algorithm:
            1. Resolve the address ``drift.amend_entry`` against
               ``declared_actions`` — an unknown address is a clean error
               of the emitting side
            2. Walk the subscriptions of the address per tool in
               enumeration order: build the tool's ``EntryAmendment`` view
               over a fresh copy of the entry's facts — every tool reads
               its own fresh view of the same entry facts, so no tool's
               in-place write reaches another tool's view or the caller's
               facts — wrap it via ``wrap_context``, project the call
               arguments via ``build_hook_arguments`` with the tool's own
               context, and call each hook of the tool
            3. A tool whose every hook returned without raising passes
               the structural check of its merged buffer: each buffered
               payload must be a ``Mapping`` — an iterable of key-value
               pairs is a structural failure, never a silent coercion
               into a mapping — the payloads merge key-wise with the
               later write replacing the earlier on conflict, and the
               merged buffer must satisfy the JSON-map shape; an empty
               merged buffer commits nothing, silently, as one
               ``ToolContribution``
            4. A tool with a raising hook or a malformed merged buffer
               is a hard failure: a clean error naming the hook or the
               tool, the action, and the entry subject stops the walk at
               the first failure; the tool's whole contribution is
               discarded together with its view
            5. Return ``merge_entry_contributions`` over the committed
               contributions — an address without subscriptions returns
               the empty mapping

        Args:
            entry: The facts of the entry being enriched — operation data
                handed over by the calling routine.

        Returns:
            The tools area of the entry — each non-empty merged contribution under
                its tool identity key; empty when nothing committed.

        Raises:
            ValueError: The address is not declared, a hook of the hard
                action failed — the message names the hook, the tool, the
                action, the entry kind and cell path, and the reason — or
                a contribution is structurally malformed — the message
                names the tool, the action, the entry kind and cell path,
                and the detail.
        """
        registry = self._ensure_registry()

        record = next(
            (entry for entry in declared_actions() if entry.domain == "drift" and entry.name == "amend_entry"),
            None,
        )
        if record is None:
            raise ValueError("unknown hook action: drift.amend_entry")

        groups: dict[str, list[Any]] = {}

        for subscription in registry.subscriptions_for("drift", "amend_entry"):
            groups.setdefault(subscription.tool, []).append(subscription)

        contributions: list[ToolContribution] = []
        entry_subject = f"{entry.kind} {entry.cell}"

        for tool, subscriptions in groups.items():
            # A fresh view per tool — value-identical reads of the entry
            # facts with a fresh type list, so no in-place write reaches
            # the caller's facts or another tool's view: a list write
            # stays local to the tool's own view and dies with it. The
            # view dies with the tool when a hook fails, taking the
            # buffer with it.
            amendment = EntryAmendment(entry=_read_only_view(entry))
            proxy = wrap_context(amendment)

            for subscription in subscriptions:
                try:
                    subscription.hook(**build_hook_arguments(subscription.hook, proxy, registry.self_context(tool)))
                except Exception as reason:
                    # Hard: stop at the first failure. The message copies
                    # the platform's format — hook name, tool, address,
                    # reason — and names the entry subject.
                    raise ValueError(
                        f"hook {subscription.name} of tool {tool} failed on "
                        f"drift.amend_entry at {entry_subject}: {reason}"
                    ) from reason

            # The commit granularity is the tool: only after every hook
            # of the tool succeeded does the buffer merge — each payload
            # guarded as a Mapping before the update, because
            # dict.update would silently accept an iterable of
            # key-value pairs and coerce it into a mapping — and the
            # merged buffer must carry the JSON-map shape before
            # anything commits. An empty merged buffer commits nothing,
            # silently.
            merged = _commit_tool_buffer(tool, entry_subject, amendment._pending)

            if merged:
                contributions.append(ToolContribution(tool=tool, facts=merged))

        return merge_entry_contributions(contributions)
