"""The amendment drafts and views of the topics lifecycle events."""

from __future__ import annotations

from dataclasses import dataclass, field

from .identity import TopicIdentity


@dataclass(kw_only=True)
class CreationDraft:
    """The shared draft holder of the creation amendment — the draft content, the final after the delivery.

    Attributes:
        commit_message: The draft commit message — None on paths that
            build no commit.
        todo: The draft todo text — None when none resolved.

    Requirements:
        The content changes only through the delivery commit of the
        amendment checkpoint — never through a delivered view.
    """

    commit_message: str | None
    todo: str | None

    def _commit(self, values: tuple[str | None, str | None]) -> None:
        """Replace the whole content from one committed buffer.

        Args:
            values: The committed buffer — the complete new pair.
        """
        self.commit_message, self.todo = values


@dataclass(kw_only=True)
class TodoEntryDraft:
    """The shared draft holder of the todo-entry amendment — the draft text, the final after the delivery.

    Attributes:
        text: The saved draft text.

    Requirements:
        The content changes only through the delivery commit of the
        amendment checkpoint — never through a delivered view.
    """

    text: str

    def _commit(self, text: str) -> None:
        """Replace the whole text from one committed buffer.

        Args:
            text: The committed buffer — the complete new text.
        """
        self.text = text


@dataclass(kw_only=True)
class CreationAmendment:
    """The creation-amendment view of one hook — the read-only surface over the live shared draft.

    Attributes:
        identity: The identity of the topic being created.
        checked_out: True when the chosen path checks out the fresh
            branch.
        published: True when the chosen path publishes the work.

    Requirements:
        The holder is never a public attribute of a delivered view — a
        view exposes no write path to it.
        The identity-only form — no commit message and no todo on the
        chosen path — is valid; the tool decides whether to act.
    """

    identity: TopicIdentity
    checked_out: bool
    published: bool
    _draft: CreationDraft
    _buffered: tuple[str | None, str | None] | None = field(default=None, init=False, repr=False)

    @property
    def commit_message(self) -> str | None:
        """Expose the live draft commit message.

        Returns:
            The live draft commit message — ``None`` on paths that build no
            commit.
        """
        return self._draft.commit_message

    @property
    def todo(self) -> str | None:
        """Expose the live draft todo text.

        Returns:
            The live draft todo text — ``None`` when none resolved.
        """
        return self._draft.todo

    def amend(self, commit_message: str | None, todo: str | None) -> None:
        """Buffer one amendment replacing the full draft content — it takes effect only when the delivery commits it.

        Args:
            commit_message: The complete new commit message — None keeps
                the field structurally absent.
            todo: The complete new todo text — None keeps the field
                structurally absent.

        Constraints:
            Do not cancel, redirect, or defer the operation — an
            amendment transforms content only.
        """
        self._buffered = (commit_message, todo)


@dataclass(kw_only=True)
class TodoEntryAmendment:
    """The todo-entry-amendment view of one hook — the read-only surface over the live shared draft.

    Attributes:
        identity: The identity of the topic whose todo is being entered.

    Requirements:
        The holder is never a public attribute of a delivered view — a
        view exposes no write path to it.
    """

    identity: TopicIdentity
    _draft: TodoEntryDraft
    _buffered: str | None = field(default=None, init=False, repr=False)
    _amended: bool = field(default=False, init=False, repr=False)
    """Whether ``amend`` was called — separates a buffered None from a hook
    that never amended, so the walk rejects the out-of-contract None buffer
    with its warning instead of reading it as no amendment."""

    @property
    def text(self) -> str:
        """Expose the live draft text.

        Returns:
            The live draft text.
        """
        return self._draft.text

    def amend(self, text: str) -> None:
        """Buffer one amendment replacing the full text — it takes effect only when the delivery commits it.

        Args:
            text: The complete new text.

        Constraints:
            Do not cancel, redirect, or defer the operation — an
            amendment transforms content only.
        """
        self._buffered = text
        self._amended = True
