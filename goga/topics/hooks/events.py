"""The checkpoint surface of the topics lifecycle events.

The entity declared in the cell CODEMANIFEST with ``location: events.py``:
``TopicHooks`` — the two amendment deliveries and the five notification
emissions over the platform facade. One registry per run carries every
checkpoint of a command: the shared module-level ``HookRegistry`` is
assembled on the first checkpoint and never rebuilt, so nested flows never
multiply the package enumeration. Every context and draft is built from
the values the caller passes — no repository reads happen at a checkpoint.
"""

from __future__ import annotations

import logging

from ...hooks import (
    HookRegistry,
    build_hook_arguments,
    declared_actions,
    emit_hook_event,
    wrap_context,
)
from .amendments import CreationAmendment, CreationDraft, TodoEntryAmendment, TodoEntryDraft
from .contexts import TopicCreated, TopicDeleted, TopicPublished, TopicSwitched, TopicTodoEntered
from .identity import TopicIdentity

logger = logging.getLogger(__name__)

_DOMAIN = "topics"
"""The owning domain of every checkpoint fired here."""

_CREATION_ACTION = "amend_creation"
"""The address of the creation-amendment checkpoint."""

_ENTRY_ACTION = "amend_todo_entry"
"""The address of the todo-entry-amendment checkpoint."""

_EMPTY_AMENDMENT = "the buffered amendment is empty or whitespace-only"
"""The rejection reason of a buffer whose structurally present content is blank."""

_RUN_REGISTRY: HookRegistry | None = None
"""The shared registry of the run — assembled on the first checkpoint, never rebuilt."""


def _run_registry() -> HookRegistry:
    """Return the shared run registry, assembling it on first use.

    One registry per run: the first checkpoint builds it once via
    ``build_once`` and every later checkpoint — of this or any other
    ``TopicHooks`` instance — shares the assembled object.

    Returns:
        The assembled registry of the run.
    """
    global _RUN_REGISTRY  # noqa: PLW0603 — the design fixes the transport as this one module attribute

    if _RUN_REGISTRY is None:
        registry = HookRegistry()
        registry.build_once()
        _RUN_REGISTRY = registry

    return _RUN_REGISTRY


def _error_class(action: str) -> str:
    """Resolve the cataloged error class of one topics action address.

    Args:
        action: The action name within the topics domain.

    Returns:
        The error class recorded for the address in the action catalog.

    Raises:
        ValueError: The address is not declared — a clean error of the
            emitting side.
    """
    record = next(
        (entry for entry in declared_actions() if entry.domain == _DOMAIN and entry.name == action),
        None,
    )
    if record is None:
        raise ValueError(f"unknown hook action: {_DOMAIN}.{action}")

    return record.error_class


def _blank(value: str | None) -> bool:
    """Report whether a structurally present amendment field is blank.

    Args:
        value: The buffered field value — None means structurally absent.

    Returns:
        True when the field is present but empty or whitespace-only.
    """
    return value is not None and not value.strip()


def _rejected_text(text: str | None) -> bool:
    """Report whether a todo-entry buffer is rejected as blank.

    The single predicate that distinguishes the entry walk from the
    creation walk: the contract types ``text`` as ``str``, so a None
    buffer value is the rejection case here — lawful as the structurally
    absent form on the creation side.

    Args:
        text: The buffered text.

    Returns:
        True when the text is None or whitespace-only.
    """
    return text is None or not text.strip()


class TopicHooks:
    """The checkpoint surface of the topics lifecycle.

    The two amendment deliveries and the five notification emissions over
    the platform facade. Construction is cheap — no state, no enumeration,
    no imports; the shared run registry assembles on the first checkpoint.

    Requirements:
        Cheap construction — no enumeration and no imports happen at
        construction.
        One ``HookRegistry`` per run carries every checkpoint of a
        command — the assembly runs once per run whatever the number of
        checkpoints.
        Every context and draft is built from the values the caller
        passes — no repository reads happen at a checkpoint.
    """

    def amend_creation(
        self,
        identity: TopicIdentity,
        checked_out: bool,
        published: bool,
        commit_message: str | None,
        todo: str | None,
    ) -> CreationDraft:
        """Deliver the creation-amendment checkpoint and return the holder.

        Args:
            identity: The identity of the topic being created.
            checked_out: True when the chosen path checks out the fresh
                branch.
            published: True when the chosen path publishes the work.
            commit_message: The draft commit message — None on paths that
                build no commit.
            todo: The draft todo text — None when none resolved.

        Returns:
            The holder carrying the final amended values — the last
            committed buffer, or the original draft values when no buffer
            committed.

        Algorithm:
            1. Assemble the shared run registry and resolve the address
               ``topics.amend_creation`` against ``declared_actions``
            2. Create the shared ``CreationDraft`` with the draft values
            3. Walk the subscriptions of the address in enumeration order:
               per subscription build the hook's ``CreationAmendment`` view
               over the live holder — outside the failure intercept — wrap
               it via ``wrap_context``, project the call arguments via
               ``build_hook_arguments`` with the tool's own context, and
               call the hook
            4. A hook that returned and buffered an amendment: the buffer
               replaces the holder content whole — except when a
               structurally present field is empty or whitespace-only,
               which rejects the whole buffer
            5. A hook that raised or returned a buffer the walk cannot
               process: its buffer is discarded
            6. Both rejection cases emit the warning naming the hook, the
               tool, the action, and the reason, and the walk continues
            7. Return the holder

        Requirements:
            The delivery is per hook — two hooks of one tool never share a
            buffer or a failure.
            An address without subscriptions returns the original draft
            values — not an error.

        Raises:
            ValueError: The address is not declared, or a hook of a
                hard-class record of the address failed — the message
                names the hook, the tool, and the reason.

        Constraints:
            Do not apply any amendment after the walk ends — the caller
            fixes the final draft into the artifacts itself.
            Do not skip a subscriber of the address.
        """
        registry = _run_registry()
        error_class = _error_class(_CREATION_ACTION)
        holder = CreationDraft(commit_message=commit_message, todo=todo)

        for subscription in registry.subscriptions_for(_DOMAIN, _CREATION_ACTION):
            # Outside the intercept: a crashing view builder is the emitting
            # side's bug, never a hook failure.
            view = CreationAmendment(
                identity=identity,
                checked_out=checked_out,
                published=published,
                _draft=holder,
            )

            try:
                proxy = wrap_context(view)
                arguments = build_hook_arguments(
                    subscription.hook,
                    proxy,
                    registry.self_context(subscription.tool),
                )
                subscription.hook(**arguments)

                # Inside the intercept on purpose: the buffer is hook
                # content, so a buffer the walk cannot process — a field
                # of an out-of-contract type — fails that hook alone.
                buffered = view._buffered
                if buffered is None:
                    continue

                if _blank(buffered[0]) or _blank(buffered[1]):
                    logger.warning(
                        "hook %s of tool %s failed on %s.%s: %s",
                        subscription.name,
                        subscription.tool,
                        _DOMAIN,
                        _CREATION_ACTION,
                        _EMPTY_AMENDMENT,
                    )
                    continue  # the whole buffer is rejected

                holder._commit(buffered)
            except Exception as reason:
                if error_class == "hard":
                    raise ValueError(
                        f"hook {subscription.name} of tool {subscription.tool} "
                        f"failed on {_DOMAIN}.{_CREATION_ACTION}: {reason}"
                    ) from reason

                logger.warning(
                    "hook %s of tool %s failed on %s.%s: %s",
                    subscription.name,
                    subscription.tool,
                    _DOMAIN,
                    _CREATION_ACTION,
                    reason,
                )
                continue  # the buffer of the failed hook is discarded

        return holder

    def amend_todo_entry(self, identity: TopicIdentity, text: str) -> TodoEntryDraft:
        """Deliver the todo-entry-amendment checkpoint and return the holder.

        The same per-hook staged walk as the creation amendment, over the
        single text field.

        Args:
            identity: The identity of the topic whose todo is being
                entered.
            text: The saved draft text.

        Returns:
            The holder carrying the final amended text — the last
            committed buffer, or the saved draft when no buffer committed.

        Algorithm:
            1. Assemble the shared run registry and resolve the address
               ``topics.amend_todo_entry`` against ``declared_actions``
            2. Create the shared ``TodoEntryDraft`` with the draft text
            3. Walk the subscriptions in enumeration order with a per-hook
               ``TodoEntryAmendment`` view over the live holder — the same
               call, commit, and rejection rules as the creation amendment
            4. Return the holder

        Requirements:
            The delivery is per hook — two hooks of one tool never share a
            buffer or a failure.
            An address without subscriptions returns the saved draft —
            not an error.

        Raises:
            ValueError: The address is not declared, or a hook of a
                hard-class record of the address failed — the message
                names the hook, the tool, and the reason.

        Constraints:
            Do not apply any amendment after the walk ends — the caller
            writes the final text itself.
            Do not skip a subscriber of the address.
        """
        registry = _run_registry()
        error_class = _error_class(_ENTRY_ACTION)
        holder = TodoEntryDraft(text=text)

        for subscription in registry.subscriptions_for(_DOMAIN, _ENTRY_ACTION):
            # Outside the intercept: a crashing view builder is the emitting
            # side's bug, never a hook failure.
            view = TodoEntryAmendment(identity=identity, _draft=holder)

            try:
                proxy = wrap_context(view)
                arguments = build_hook_arguments(
                    subscription.hook,
                    proxy,
                    registry.self_context(subscription.tool),
                )
                subscription.hook(**arguments)

                # Inside the intercept on purpose: the buffer is hook
                # content, so a buffer the walk cannot process — a value
                # of an out-of-contract type — fails that hook alone.
                if not view._amended:
                    continue

                # The buffered None is the out-of-contract rejection case of
                # this walk — the flag separates it from a hook that never
                # amended, so the predicate's None arm stays reachable.
                if _rejected_text(view._buffered):
                    logger.warning(
                        "hook %s of tool %s failed on %s.%s: %s",
                        subscription.name,
                        subscription.tool,
                        _DOMAIN,
                        _ENTRY_ACTION,
                        _EMPTY_AMENDMENT,
                    )
                    continue  # the whole buffer is rejected

                holder._commit(view._buffered)
            except Exception as reason:
                if error_class == "hard":
                    raise ValueError(
                        f"hook {subscription.name} of tool {subscription.tool} "
                        f"failed on {_DOMAIN}.{_ENTRY_ACTION}: {reason}"
                    ) from reason

                logger.warning(
                    "hook %s of tool %s failed on %s.%s: %s",
                    subscription.name,
                    subscription.tool,
                    _DOMAIN,
                    _ENTRY_ACTION,
                    reason,
                )
                continue  # the buffer of the failed hook is discarded

        return holder

    def emit_created(  # noqa: PLR0913, PLR0917 — the six facts are the declared checkpoint signature
        self,
        identity: TopicIdentity,
        checked_out: bool,
        published: bool,
        todo: str | None,
        commit_message: str | None,
        commit_hash: str | None,
    ) -> None:
        """Emit the creation notification — the facts of one completed creation.

        Args:
            identity: The identity of the created topic.
            checked_out: True when the creation path checked out the fresh
                branch.
            published: True when the creation path published the work.
            todo: The final todo text, or None.
            commit_message: The final commit message — None on paths
                building none.
            commit_hash: The hash of the built commit — None on paths
                building none.

        Algorithm:
            1. Build the ``TopicCreated`` context from the values
            2. Emit the address ``topics.topic_created`` via
               ``emit_hook_event`` — the context view of every receiving
               tool reads the same instance through the delivery proxy

        Requirements:
            Fire-and-forget — nothing is collected and no value returns.
            A failing hook is skipped with a warning under the soft error
            class of the action.
        """
        context = TopicCreated(
            identity=identity,
            checked_out=checked_out,
            published=published,
            todo=todo,
            commit_message=commit_message,
            commit_hash=commit_hash,
        )
        emit_hook_event(_run_registry(), _DOMAIN, "topic_created", context_for=lambda _tool: context)

    def emit_published(self, identity: TopicIdentity, commit_message: str, commit_hash: str, todo: str) -> None:
        """Emit the publication notification — one successful publication push.

        Args:
            identity: The identity of the published topic.
            commit_message: The final commit message landed in git.
            commit_hash: The hash of the publication commit.
            todo: The final todo text landed in the publication commit.

        Algorithm:
            1. Build the ``TopicPublished`` context from the values
            2. Emit the address ``topics.topic_published`` via
               ``emit_hook_event``

        Requirements:
            Fire-and-forget — nothing is collected and no value returns.
        """
        context = TopicPublished(
            identity=identity,
            commit_message=commit_message,
            commit_hash=commit_hash,
            todo=todo,
        )
        emit_hook_event(_run_registry(), _DOMAIN, "topic_published", context_for=lambda _tool: context)

    def emit_switched(self, identity: TopicIdentity, outcome: str) -> None:
        """Emit the switch notification — the outcome of one completed switch.

        Args:
            identity: The identity of the switched work — the branch-only
                form when the branch hosts no topic.
            outcome: The outcome kind — local-checkout,
                created-from-remote, or already-on-branch.

        Algorithm:
            1. Build the ``TopicSwitched`` context from the values
            2. Emit the address ``topics.topic_switched`` via
               ``emit_hook_event``

        Requirements:
            Fire-and-forget — nothing is collected and no value returns.
        """
        context = TopicSwitched(identity=identity, outcome=outcome)
        emit_hook_event(_run_registry(), _DOMAIN, "topic_switched", context_for=lambda _tool: context)

    def emit_todo_entered(self, identity: TopicIdentity, text: str) -> None:
        """Emit the todo-entry notification — one saved todo entry.

        Args:
            identity: The identity of the topic whose todo was entered.
            text: The final written text.

        Algorithm:
            1. Build the ``TopicTodoEntered`` context from the values
            2. Emit the address ``topics.topic_todo_entered`` via
               ``emit_hook_event``

        Requirements:
            Fire-and-forget — nothing is collected and no value returns.
        """
        context = TopicTodoEntered(identity=identity, text=text)
        emit_hook_event(_run_registry(), _DOMAIN, "topic_todo_entered", context_for=lambda _tool: context)

    def emit_deleted(
        self,
        identity: TopicIdentity,
        local_branch: str | None,
        origin_twin: str | None,
        directory_removed: bool,
    ) -> None:
        """Emit the deletion notification — one fully removed target.

        Args:
            identity: The identity of the removed topic — slug and home
                path; no branch fact.
            local_branch: The removed local branch name, or None.
            origin_twin: The removed origin twin name, or None.
            directory_removed: True when the topic directory was removed.

        Algorithm:
            1. Build the ``TopicDeleted`` context from the values
            2. Emit the address ``topics.topic_deleted`` via
               ``emit_hook_event``

        Requirements:
            Fire-and-forget — nothing is collected and no value returns.
        """
        context = TopicDeleted(
            identity=identity,
            local_branch=local_branch,
            origin_twin=origin_twin,
            directory_removed=directory_removed,
        )
        emit_hook_event(_run_registry(), _DOMAIN, "topic_deleted", context_for=lambda _tool: context)
