"""Contract and logic tests for the entities declared in
``goga/topics/hooks/CODEMANIFEST`` with ``location: amendments.py``: the
draft holders ``CreationDraft`` and ``TodoEntryDraft`` and the amendment
views ``CreationAmendment`` and ``TodoEntryAmendment``.

Buffering isolation — no fixtures, no mocks: an ``amend`` call buffers
on the view of its hook alone, the holder content changes only through
the delivery commit, and the read-through properties expose the live
holder fields.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest
from goga.topics.hooks import (
    CreationAmendment,
    CreationDraft,
    TodoEntryAmendment,
    TodoEntryDraft,
    TopicIdentity,
)

from tests.conftest import is_kw_only_dataclass

IDENTITY = TopicIdentity(slug="feature-foo", year="2026", branch="feature-foo")

ZONE_ALL: list[str] = [
    "CreationAmendment",
    "CreationDraft",
    "TodoEntryAmendment",
    "TodoEntryDraft",
    "TopicCreated",
    "TopicDeleted",
    "TopicHooks",
    "TopicIdentity",
    "TopicPublished",
    "TopicSwitched",
    "TopicTodoEntered",
]
"""The final zone facade — the eleven names, alphabetical."""


def _creation_view(holder: CreationDraft) -> CreationAmendment:
    """Build a creation-amendment view over ``holder`` — the wiring of the walk.

    Args:
        holder: The live shared holder the view reads through.

    Returns:
        The view the delivery of one hook receives.
    """
    return CreationAmendment(
        identity=IDENTITY,
        checked_out=False,
        published=False,
        _draft=holder,
    )


# --- Contract tests ---


class TestAmendmentsContract:
    def test_entities_are_importable_from_the_zone_facade(self) -> None:
        """The four amendment types live on the zone package; ``__all__`` is exact."""
        import goga.topics.hooks as zone

        assert zone.CreationDraft is CreationDraft
        assert zone.TodoEntryDraft is TodoEntryDraft
        assert zone.CreationAmendment is CreationAmendment
        assert zone.TodoEntryAmendment is TodoEntryAmendment
        assert zone.__all__ == ZONE_ALL

    def test_holders_are_kw_only_mutable_dataclasses(self) -> None:
        """``Holder(field=...)`` — keyword-only construction, live fields."""
        creation = CreationDraft(
            commit_message="goga: create topic feature-foo",
            todo="the todo",
        )
        entry = TodoEntryDraft(text="saved text")

        assert creation.commit_message == "goga: create topic feature-foo"
        assert creation.todo == "the todo"
        assert entry.text == "saved text"

        for holder in (CreationDraft, TodoEntryDraft):
            assert dataclasses.is_dataclass(holder)
            assert not holder.__dataclass_params__.frozen
            assert is_kw_only_dataclass(holder)

        with pytest.raises(TypeError):
            CreationDraft("goga: create topic feature-foo", "the todo")  # type: ignore[misc]

        with pytest.raises(TypeError):
            TodoEntryDraft("saved text")  # type: ignore[misc]

    def test_views_are_kw_only_mutable_dataclasses_over_the_private_holder(self) -> None:
        """The views store the holder under ``_draft`` — the internal wiring keyword."""
        holder = CreationDraft(commit_message="m", todo="t")
        view = CreationAmendment(
            identity=IDENTITY,
            checked_out=False,
            published=False,
            _draft=holder,
        )
        entry_view = TodoEntryAmendment(
            identity=IDENTITY,
            _draft=TodoEntryDraft(text="saved"),
        )

        assert view.identity is IDENTITY
        assert view.checked_out is False
        assert view.published is False
        assert entry_view.identity is IDENTITY

        for view_cls in (CreationAmendment, TodoEntryAmendment):
            assert dataclasses.is_dataclass(view_cls)
            assert not view_cls.__dataclass_params__.frozen
            assert is_kw_only_dataclass(view_cls)

        with pytest.raises(TypeError):
            CreationAmendment(IDENTITY, False, False, holder)  # type: ignore[misc]

        with pytest.raises(TypeError):
            TodoEntryAmendment(IDENTITY, TodoEntryDraft(text="saved"))  # type: ignore[misc]

    def test_views_carry_the_wiring_fields_with_read_through_properties(self) -> None:
        """The holder stays private; the content reads are properties over it."""
        assert [field.name for field in dataclasses.fields(CreationAmendment)] == [
            "identity",
            "checked_out",
            "published",
            "_draft",
            "_buffered",
        ]
        assert [field.name for field in dataclasses.fields(TodoEntryAmendment)] == [
            "identity",
            "_draft",
            "_buffered",
            "_amended",
        ]

        creation_hints = typing.get_type_hints(CreationAmendment)
        assert creation_hints["identity"] == TopicIdentity
        assert creation_hints["checked_out"] is bool
        assert creation_hints["published"] is bool
        assert creation_hints["_draft"] is CreationDraft
        assert creation_hints["_buffered"] == tuple[str | None, str | None] | None

        entry_hints = typing.get_type_hints(TodoEntryAmendment)
        assert entry_hints["identity"] == TopicIdentity
        assert entry_hints["_draft"] is TodoEntryDraft
        assert entry_hints["_buffered"] == str | None
        assert entry_hints["_amended"] is bool

        for cls, names in (
            (CreationAmendment, ("commit_message", "todo")),
            (TodoEntryAmendment, ("text",)),
        ):
            field_names = {field.name for field in dataclasses.fields(cls)}
            assert not field_names.intersection(names)  # the reads are not fields

            for name in names:
                assert isinstance(getattr(cls, name), property)

        assert typing.get_type_hints(CreationAmendment.commit_message.fget)["return"] == str | None
        assert typing.get_type_hints(CreationAmendment.todo.fget)["return"] == str | None
        assert typing.get_type_hints(TodoEntryAmendment.text.fget)["return"] is str

    def test_the_buffered_field_is_uninitialized_hidden_and_empty(self) -> None:
        """``_buffered`` — init=False, repr=False, default None on a fresh view."""
        for view_cls in (CreationAmendment, TodoEntryAmendment):
            buffered = {field.name: field for field in dataclasses.fields(view_cls)}["_buffered"]

            assert buffered.init is False
            assert buffered.repr is False
            assert buffered.default is None

        # The amended marker of the entry view — the flag separating a
        # buffered None from a hook that never amended.
        amended = {field.name: field for field in dataclasses.fields(TodoEntryAmendment)}["_amended"]

        assert amended.init is False
        assert amended.repr is False
        assert amended.default is False

        view = _creation_view(CreationDraft(commit_message="m", todo="t"))

        assert view._buffered is None
        assert "_buffered" not in repr(view)

    def test_amend_returns_none_and_raises_nothing(self) -> None:
        """Buffering never raises — every amendment value is lawful at the view."""
        view = _creation_view(CreationDraft(commit_message="m", todo="t"))
        entry_view = TodoEntryAmendment(
            identity=IDENTITY,
            _draft=TodoEntryDraft(text="saved"),
        )

        assert view.amend("m2", "t2") is None
        assert view.amend(None, None) is None
        assert entry_view.amend("amended") is None

    def test_views_expose_amend_as_the_sole_public_method(self) -> None:
        """No cancel, redirect, or defer — an amendment transforms content only."""
        for cls in (CreationAmendment, TodoEntryAmendment):
            methods = {
                name
                for name in dir(cls)
                if not name.startswith("_")
                and callable(getattr(cls, name))
                and not isinstance(getattr(cls, name), property)
            }

            assert methods == {"amend"}


# --- Logic tests ---


class TestCreationBuffering:
    def test_amend_views_block_no_write_path_to_the_holder(self) -> None:
        """The buffering isolation behind the discard-on-failure semantics.

        ``amend`` buffers on the view alone; the holder fields stay at
        the draft values, and the view reads the live holder — the draft
        values, not the buffer.
        """
        holder = CreationDraft(commit_message="orig", todo="orig todo")
        view = _creation_view(holder)

        assert view.amend("m", "t") is None

        assert holder.commit_message == "orig"
        assert holder.todo == "orig todo"
        assert view.commit_message == "orig"
        assert view.todo == "orig todo"

    def test_amend_called_twice_last_buffer_wins(self) -> None:
        """``amend`` means replace entirely — the last buffer wins, never accumulates.

        The walk of ``events.py`` lands in Task 6; the last-wins guarantee
        is pinned here against the view/holder semantics — a hook double
        buffers twice, the buffer content commits through the direct
        ``_commit``.
        """
        holder = CreationDraft(commit_message="orig", todo="orig todo")
        view = _creation_view(holder)

        view.amend("first", "t-first")
        view.amend("second", "t-second")

        assert view._buffered == ("second", "t-second")
        assert holder.commit_message == "orig"  # untouched during both calls

        holder._commit(view._buffered)

        assert holder.commit_message == "second"
        assert holder.todo == "t-second"

    def test_amend_none_none_is_a_lawful_whole_replacement(self) -> None:
        """``amend(None, None)`` buffers the identity-only form without holder contact."""
        holder = CreationDraft(commit_message="orig", todo="orig todo")
        view = _creation_view(holder)

        view.amend(None, None)

        assert view._buffered == (None, None)
        assert holder.commit_message == "orig"
        assert holder.todo == "orig todo"

        holder._commit(view._buffered)

        assert holder.commit_message is None
        assert holder.todo is None

    def test_view_reads_reflect_the_committed_amendments_of_earlier_hooks(self) -> None:
        """The read-through reads the live holder — a later hook sees the earlier commits."""
        holder = CreationDraft(commit_message="orig", todo="orig todo")
        view = _creation_view(holder)

        holder._commit(("m1", "t1"))

        assert view.commit_message == "m1"
        assert view.todo == "t1"


class TestTodoEntryBuffering:
    def test_entry_view_reads_through_the_live_holder(self) -> None:
        """``text`` reads the live holder — ``amend`` buffers alone, ``_commit`` replaces."""
        holder = TodoEntryDraft(text="saved text")
        view = TodoEntryAmendment(identity=IDENTITY, _draft=holder)

        assert view.text == "saved text"

        view.amend("amended")

        assert view._buffered == "amended"
        assert holder.text == "saved text"

        holder._commit("amended")

        assert view.text == "amended"
        assert holder.text == "amended"

    def test_entry_amend_called_twice_last_buffer_wins(self) -> None:
        """The single-field whole replacement carries the same last-wins rule."""
        holder = TodoEntryDraft(text="saved text")
        view = TodoEntryAmendment(identity=IDENTITY, _draft=holder)

        view.amend("first")
        view.amend("second")

        assert view._buffered == "second"
        assert holder.text == "saved text"

        holder._commit(view._buffered)

        assert holder.text == "second"
