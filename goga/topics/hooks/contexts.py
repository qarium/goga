"""The notification contexts of the topics lifecycle events.

The entities declared in the cell CODEMANIFEST with ``location:
contexts.py``: the five read-only fact bags of the post-moment
notifications — ``TopicCreated``, ``TopicPublished``, ``TopicSwitched``,
``TopicTodoEntered``, ``TopicDeleted``. An ``emit_*`` method constructs
one from the values the caller passed; a hook observes the outcome and
cannot alter it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .identity import TopicIdentity


@dataclass(frozen=True, kw_only=True)
class TopicCreated:
    """The read-only context of the creation notification.

    The final facts of one completed creation.

    Attributes:
        identity: The identity of the created topic.
        checked_out: True when the creation path checked out the fresh
            branch.
        published: True when the creation path published the work.
        todo: The final todo text, or None when none resolved.
        commit_message: The final commit message — present exactly when
            the creation path builds a commit, None otherwise.
        commit_hash: The hash of the built commit — present exactly when
            the creation path builds a commit, None otherwise.

    Requirements:
        Read-only facts of a completed operation — a hook observes the
        outcome and cannot alter it.
    """

    identity: TopicIdentity
    checked_out: bool
    published: bool
    todo: str | None
    commit_message: str | None
    commit_hash: str | None


@dataclass(frozen=True, kw_only=True)
class TopicPublished:
    """The read-only context of the publication notification.

    The final facts of one successful publication push.

    Attributes:
        identity: The identity of the published topic.
        commit_message: The final commit message landed in git.
        commit_hash: The hash of the publication commit.
        todo: The final todo text landed in the publication commit.

    Requirements:
        Read-only facts of a completed operation.
    """

    identity: TopicIdentity
    commit_message: str
    commit_hash: str
    todo: str


@dataclass(frozen=True, kw_only=True)
class TopicSwitched:
    """The read-only context of the switch notification.

    The outcome of one completed switch.

    Attributes:
        identity: The identity of the switched work — the branch-only
            form when the branch hosts no topic.
        outcome: The outcome kind — exactly one of local-checkout,
            created-from-remote, already-on-branch.

    Requirements:
        The outcome value is exactly one of the three fixed kinds —
        fixed by construction of the emitting routine.
        Read-only facts of a completed operation.
    """

    identity: TopicIdentity
    outcome: str


@dataclass(frozen=True, kw_only=True)
class TopicTodoEntered:
    """The read-only context of the todo-entry notification.

    The final text of one saved todo entry.

    Attributes:
        identity: The identity of the topic whose todo was entered.
        text: The final written text — after every amendment.

    Requirements:
        No prior text is carried — a tool keeps its own state in its
        own context.
        Read-only facts of a completed operation.
    """

    identity: TopicIdentity
    text: str


@dataclass(frozen=True, kw_only=True)
class TopicDeleted:
    """The read-only context of the deletion notification.

    The removal composition of one fully removed target.

    Attributes:
        identity: The identity of the removed topic — slug and home
            path; no branch fact.
        local_branch: The removed local branch name, or None when the
            target had none.
        origin_twin: The removed origin twin name, or None when the
            target had none.
        directory_removed: True when the topic directory was removed.

    Requirements:
        No deleted-commit hash is carried.
        Read-only facts of a completed operation.
    """

    identity: TopicIdentity
    local_branch: str | None
    origin_twin: str | None
    directory_removed: bool
