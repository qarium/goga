"""Contract and logic tests for the entities declared in
``goga/topics/hooks/CODEMANIFEST`` with ``location: contexts.py``: the
five notification contexts ``TopicCreated``, ``TopicPublished``,
``TopicSwitched``, ``TopicTodoEntered``, ``TopicDeleted``.

Read-only fact bags — no fixtures, no mocks: an ``emit_*`` method
constructs one from the values the caller passed, every field read
returns the constructor value, and no method surface or write path
exists.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest
from goga.topics.hooks import (
    TopicCreated,
    TopicDeleted,
    TopicIdentity,
    TopicPublished,
    TopicSwitched,
    TopicTodoEntered,
)

from tests.conftest import is_kw_only_dataclass

IDENTITY = TopicIdentity(slug="feature-foo", year="2026", branch="feature-foo")
DELETION_IDENTITY = TopicIdentity(slug="one", year="2026", branch=None)

CONTEXT_FIELDS: dict[type, dict[str, object]] = {
    TopicCreated: {
        "identity": TopicIdentity,
        "checked_out": bool,
        "published": bool,
        "todo": str | None,
        "commit_message": str | None,
        "commit_hash": str | None,
    },
    TopicPublished: {
        "identity": TopicIdentity,
        "commit_message": str,
        "commit_hash": str,
        "todo": str,
    },
    TopicSwitched: {
        "identity": TopicIdentity,
        "outcome": str,
    },
    TopicTodoEntered: {
        "identity": TopicIdentity,
        "text": str,
    },
    TopicDeleted: {
        "identity": TopicIdentity,
        "local_branch": str | None,
        "origin_twin": str | None,
        "directory_removed": bool,
    },
}
"""The declared field sets with their types — one entry per context."""

CONTEXT_CASES: list[tuple[type, dict[str, object]]] = [
    (
        TopicCreated,
        {
            "identity": IDENTITY,
            "checked_out": False,
            "published": False,
            "todo": "the todo",
            "commit_message": "goga: create topic feature-foo",
            "commit_hash": "deadbeef",
        },
    ),
    (
        TopicPublished,
        {
            "identity": IDENTITY,
            "commit_message": "goga: create topic feature-foo",
            "commit_hash": "cafe123",
            "todo": "the todo",
        },
    ),
    (
        TopicSwitched,
        {
            "identity": IDENTITY,
            "outcome": "local-checkout",
        },
    ),
    (
        TopicTodoEntered,
        {
            "identity": IDENTITY,
            "text": "the final text",
        },
    ),
    (
        TopicDeleted,
        {
            "identity": DELETION_IDENTITY,
            "local_branch": "one",
            "origin_twin": "one",
            "directory_removed": True,
        },
    ),
]
"""One construction case per context — keyword order matches the signature."""

CASE_IDS = [cls.__name__ for cls, _ in CONTEXT_CASES]

# --- Contract tests ---


class TestContextsContract:
    def test_entities_are_importable_from_the_zone_facade(self) -> None:
        """The five contexts live on the zone package and ``__all__`` is exact."""
        import goga.topics.hooks as zone

        assert zone.TopicCreated is TopicCreated
        assert zone.TopicPublished is TopicPublished
        assert zone.TopicSwitched is TopicSwitched
        assert zone.TopicTodoEntered is TopicTodoEntered
        assert zone.TopicDeleted is TopicDeleted
        assert zone.__all__ == [
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

    @pytest.mark.parametrize(("cls", "values"), CONTEXT_CASES, ids=CASE_IDS)
    def test_contexts_are_kw_only_frozen_dataclasses(
        self,
        cls: type,
        values: dict[str, object],
    ) -> None:
        """``Cls(field=..., ...)`` — keyword-only construction, frozen holder."""
        cls(**values)  # type: ignore[arg-type] — construction itself must pass

        assert dataclasses.is_dataclass(cls)
        assert cls.__dataclass_params__.frozen
        assert is_kw_only_dataclass(cls)

        with pytest.raises(TypeError):
            cls(*values.values())  # type: ignore[misc]

    @pytest.mark.parametrize(("cls", "values"), CONTEXT_CASES, ids=CASE_IDS)
    def test_context_assignment_raises_frozen_instance_error(
        self,
        cls: type,
        values: dict[str, object],
    ) -> None:
        """The contexts are read-only facts — no hook rewrites them."""
        context = cls(**values)  # type: ignore[arg-type]

        with pytest.raises(dataclasses.FrozenInstanceError):
            context.identity = IDENTITY  # type: ignore[misc]

        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(context, next(iter(values)), "rewritten")  # type: ignore[misc]

    @pytest.mark.parametrize(("cls", "values"), CONTEXT_CASES, ids=CASE_IDS)
    def test_contexts_carry_the_declared_fields_and_types(
        self,
        cls: type,
        values: dict[str, object],
    ) -> None:
        """The field list and the type of every field match the declaration."""
        declared = CONTEXT_FIELDS[cls]
        field_names = [field.name for field in dataclasses.fields(cls)]
        field_types = typing.get_type_hints(cls)

        assert field_names == list(declared)
        for name, expected_type in declared.items():
            assert field_types[name] == expected_type

        public_members = [name for name in dir(cls) if not name.startswith("_")]
        assert public_members == []  # no method surface, no computed members


# --- Logic tests ---


class TestContextFacts:
    @pytest.mark.parametrize(("cls", "values"), CONTEXT_CASES, ids=CASE_IDS)
    def test_every_constructor_value_reads_back_identically(
        self,
        cls: type,
        values: dict[str, object],
    ) -> None:
        """Plain data fields — attribute reads suffice, nothing transforms."""
        context = cls(**values)  # type: ignore[arg-type]

        for name, value in values.items():
            if isinstance(value, TopicIdentity):
                assert getattr(context, name) is value
            else:
                assert getattr(context, name) == value

        assert isinstance(context.identity, TopicIdentity)  # type: ignore[attr-defined]
        assert context.identity is values["identity"]  # type: ignore[attr-defined]

    def test_switched_outcome_carries_each_fixed_kind(self) -> None:
        """The kind is fixed by the emitting routine — the context carries the string."""
        for outcome in ("local-checkout", "created-from-remote", "already-on-branch"):
            switched = TopicSwitched(identity=IDENTITY, outcome=outcome)

            assert switched.outcome == outcome
            assert switched.identity is IDENTITY
