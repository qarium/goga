"""Contract and logic tests for the entity declared in
``goga/topics/hooks/CODEMANIFEST`` with ``location: events.py``:
``TopicHooks`` — the checkpoint surface with the two amendment walks and
the five notification emissions, over the lazily-built shared run
registry.

The environment boundary is pinned by the local fixtures of
``tests/topics/hooks/conftest.py`` — the enumeration mapping and the fake
``goga_tool_*`` modules — so the registry, the walks, and the platform
delivery run for real behind every checkpoint. The autouse reset of the
conftest starts every test with an unbuilt run registry: no subscription
leaks across tests and enumeration counts are per-test.
"""

from __future__ import annotations

import inspect
import logging
import typing
from collections.abc import Callable
from typing import Any

import pytest
from goga.topics.hooks import (
    CreationDraft,
    TodoEntryDraft,
    TopicCreated,
    TopicHooks,
    TopicIdentity,
)

from tests.topics.hooks.conftest import TWO_TOOL_ENVIRONMENT

IDENTITY = TopicIdentity(slug="add-topics-hooks", year="2026", branch="add-topics-hooks")

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

METHOD_CONTRACTS: dict[str, tuple[tuple[str, object], ...]] = {
    "amend_creation": (
        ("identity", TopicIdentity),
        ("checked_out", bool),
        ("published", bool),
        ("commit_message", str | None),
        ("todo", str | None),
    ),
    "amend_todo_entry": (("identity", TopicIdentity), ("text", str)),
    "emit_created": (
        ("identity", TopicIdentity),
        ("checked_out", bool),
        ("published", bool),
        ("todo", str | None),
        ("commit_message", str | None),
        ("commit_hash", str | None),
    ),
    "emit_published": (
        ("identity", TopicIdentity),
        ("commit_message", str),
        ("commit_hash", str),
        ("todo", str),
    ),
    "emit_switched": (("identity", TopicIdentity), ("outcome", str)),
    "emit_todo_entered": (("identity", TopicIdentity), ("text", str)),
    "emit_deleted": (
        ("identity", TopicIdentity),
        ("local_branch", str | None),
        ("origin_twin", str | None),
        ("directory_removed", bool),
    ),
}
"""The seven checkpoint methods with their declared parameters and types."""

PinEnvironment = Callable[[dict[str, list[str]]], Any]
"""The enumeration-boundary pinning factory of the local conftest."""

InstallToolPackage = Callable[[str, Callable[[Any], None] | None], Any]
"""The fake-package installing factory of the local conftest."""


def _register(*subscriptions: tuple[str, Callable[..., None]]) -> Callable[[Any], None]:
    """Build a facade callback subscribing each hook on its topics action.

    Each pair is one subscription — the topics action name and the hook;
    the hook's ``__name__`` is its hook name, so the failure warnings of
    the walks name the functions the test declares.

    Args:
        subscriptions: The (action, hook) pairs to subscribe.

    Returns:
        The ``register_hooks`` callback of one fake tool package.
    """

    def register_hooks(hooks: Any) -> None:
        for action, hook in subscriptions:
            hooks.subscribe("topics", action, hook.__name__, hook)

    return register_hooks


# --- Contract tests ---


class TestEventsContract:
    def test_entity_is_importable_from_the_zone_facade(self) -> None:
        """The checkpoint surface lives on the zone package; ``__all__`` is final."""
        import goga.topics.hooks as zone

        assert zone.TopicHooks is TopicHooks
        assert zone.__all__ == ZONE_ALL

    def test_the_module_state_is_one_lazily_built_run_registry(
        self,
        pin_package_environment: PinEnvironment,
    ) -> None:
        """``_RUN_REGISTRY`` starts unbuilt; the builder assembles it once."""
        from goga.topics.hooks import events

        boundary = pin_package_environment(TWO_TOOL_ENVIRONMENT)

        assert events._RUN_REGISTRY is None  # the autouse reset of the conftest

        registry = events._run_registry()

        assert events._RUN_REGISTRY is registry
        assert events._run_registry() is registry
        assert boundary.call_count == 1

    @pytest.mark.parametrize(("method", "parameters"), METHOD_CONTRACTS.items())
    def test_method_signatures_match_the_declared_api(
        self,
        method: str,
        parameters: tuple[tuple[str, object], ...],
    ) -> None:
        """Every checkpoint method carries exactly its declared parameters."""
        function = getattr(TopicHooks, method)
        hints = typing.get_type_hints(function)

        declared = list(inspect.signature(function).parameters)[1:]  # past self

        assert declared == [name for name, _ in parameters]

        for name, annotation in parameters:
            assert hints[name] == annotation

    def test_amendments_return_their_holders_and_emissions_return_none(self) -> None:
        """The two walks return their holders; the five emissions return nothing."""
        assert typing.get_type_hints(TopicHooks.amend_creation)["return"] is CreationDraft
        assert typing.get_type_hints(TopicHooks.amend_todo_entry)["return"] is TodoEntryDraft

        for method in ("emit_created", "emit_published", "emit_switched", "emit_todo_entered", "emit_deleted"):
            assert typing.get_type_hints(getattr(TopicHooks, method))["return"] is type(None)

    def test_topic_hooks_construction_enumerates_nothing(
        self,
        pin_package_environment: PinEnvironment,
    ) -> None:
        """Cheap construction — no enumeration and no imports happen at construction.

        ``__init__`` stores nothing and touches nothing: the enumeration
        boundary stays unread and the run registry stays unbuilt, keeping
        import-time and construction-time behavior identical for every
        consumer.
        """
        from goga.topics.hooks import events

        boundary = pin_package_environment(TWO_TOOL_ENVIRONMENT)

        TopicHooks()

        assert boundary.call_count == 0
        assert events._RUN_REGISTRY is None


# --- Logic tests: the creation-amendment walk ---


class TestCreationWalk:
    def test_amend_creation_walks_per_hook_and_commits_in_order(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
    ) -> None:
        """The per-hook commit granularity — the core zone refinement.

        Two hooks of one tool carry independent buffers and read the
        committed amendments of the earlier hooks; the tail tool observes
        the final state; the holder carries the last committed buffer.
        """
        boundary = pin_package_environment(TWO_TOOL_ENVIRONMENT)
        seen: dict[str, str | None] = {}

        def first(context: object) -> None:
            context.amend("m1", "t1")  # type: ignore[attr-defined]

        def second(context: object) -> None:
            seen["second"] = context.todo  # type: ignore[attr-defined]
            context.amend("m2", "t2")  # type: ignore[attr-defined]

        def tail(context: object) -> None:
            seen["tail"] = context.todo  # type: ignore[attr-defined]

        install_tool_package(
            "goga_tool_one",
            register_hooks=_register(("amend_creation", first), ("amend_creation", second)),
        )
        install_tool_package("goga_tool_two", register_hooks=_register(("amend_creation", tail)))

        draft = TopicHooks().amend_creation(
            IDENTITY,
            checked_out=False,
            published=False,
            commit_message="goga: create topic add-topics-hooks",
            todo="first todo",
        )

        assert draft.commit_message == "m2"
        assert draft.todo == "t2"  # the last committed buffer
        assert seen == {"second": "t1", "tail": "t2"}  # ordered visibility
        assert boundary.call_count == 1  # one enumeration for the whole walk

    def test_amend_creation_discards_buffer_of_raising_hook(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A failing hook never breaks the operation and never leaks its buffer."""
        pin_package_environment(TWO_TOOL_ENVIRONMENT)

        def boom(context: object) -> None:
            context.amend("m", "t")  # type: ignore[attr-defined]
            raise RuntimeError("kaputt")

        def tail(context: object) -> None:
            context.amend("late", "late-t")  # type: ignore[attr-defined]

        install_tool_package("goga_tool_one", register_hooks=_register(("amend_creation", boom)))
        install_tool_package("goga_tool_two", register_hooks=_register(("amend_creation", tail)))

        with caplog.at_level(logging.WARNING):
            draft = TopicHooks().amend_creation(IDENTITY, False, False, "orig", "orig todo")

        assert draft.commit_message == "late"  # the buffer of boom is gone
        assert draft.todo == "late-t"
        assert any(
            "hook boom of tool one failed on topics.amend_creation: kaputt" in record.message
            for record in caplog.records
        )

    def test_amend_creation_rejects_empty_amendment_whole(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A whitespace field rejects the whole buffer — nothing partially lands."""

        def blank(context: object) -> None:
            context.amend("   ", "fine text")  # type: ignore[attr-defined]

        pin_package_environment(TWO_TOOL_ENVIRONMENT)
        install_tool_package("goga_tool_one", register_hooks=_register(("amend_creation", blank)))

        with caplog.at_level(logging.WARNING):
            draft = TopicHooks().amend_creation(IDENTITY, False, False, "orig", "orig todo")

        assert draft.commit_message == "orig"  # the original values survive
        assert draft.todo == "orig todo"
        expected_warning = (
            "hook blank of tool one failed on topics.amend_creation: the buffered amendment is empty or whitespace-only"
        )

        assert expected_warning in caplog.text

    def test_amend_creation_discards_buffer_of_unprocessable_type(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A buffer field of an out-of-contract type fails that hook alone — never the walk."""

        def numeric(context: object) -> None:
            context.amend(123, "fine text")  # type: ignore[arg-type, attr-defined]

        def tail(context: object) -> None:
            context.amend("late", "late-t")  # type: ignore[attr-defined]

        pin_package_environment(TWO_TOOL_ENVIRONMENT)
        install_tool_package("goga_tool_one", register_hooks=_register(("amend_creation", numeric)))
        install_tool_package("goga_tool_two", register_hooks=_register(("amend_creation", tail)))

        with caplog.at_level(logging.WARNING):
            draft = TopicHooks().amend_creation(IDENTITY, False, False, "orig", "orig todo")

        assert draft.commit_message == "late"  # the buffer of numeric is gone
        assert draft.todo == "late-t"
        assert any(
            "hook numeric of tool one failed on topics.amend_creation:" in record.message and "int" in record.message
            for record in caplog.records
        )

    def test_amend_creation_without_subscriptions_returns_original_values(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
    ) -> None:
        """The no-subscriber case — a transparent no-op, never an error."""

        def recorder(context: object) -> None:
            return None

        pin_package_environment(TWO_TOOL_ENVIRONMENT)
        install_tool_package("goga_tool_one", register_hooks=_register(("topic_created", recorder)))

        draft = TopicHooks().amend_creation(IDENTITY, False, False, "m", None)

        assert draft.commit_message == "m"
        assert draft.todo is None

    def test_amend_creation_identity_only_form_is_valid(
        self,
        recording_hooks: Callable[..., list[tuple[str, str, object]]],
    ) -> None:
        """The identity-only form is the norm on the ensure fast path — observable."""
        records = recording_hooks("amend_creation")

        draft = TopicHooks().amend_creation(IDENTITY, True, False, None, None)

        assert draft.commit_message is None
        assert draft.todo is None
        assert len(records) == 1

        view = records[0][2]

        assert view.checked_out is True
        assert view.published is False
        assert view.commit_message is None
        assert view.todo is None

    def test_amend_creation_hard_class_stops_the_walk_with_clean_error(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A hard-class catalog record turns a hook failure into a clean error (D7)."""
        from goga.hooks.catalog import Action
        from goga.topics.hooks import events

        monkeypatch.setattr(
            events,
            "declared_actions",
            lambda: [Action(domain="topics", name="amend_creation", error_class="hard")],
        )

        def boom(context: object) -> None:
            raise RuntimeError("stop")

        pin_package_environment(TWO_TOOL_ENVIRONMENT)
        install_tool_package("goga_tool_one", register_hooks=_register(("amend_creation", boom)))

        with pytest.raises(ValueError, match=r"hook boom of tool one failed on topics\.amend_creation: stop"):
            TopicHooks().amend_creation(IDENTITY, False, False, "orig", "orig todo")


# --- Logic tests: the todo-entry-amendment walk ---


class TestTodoEntryWalk:
    @pytest.mark.parametrize("blank", ["   ", ""])
    def test_amend_todo_entry_rejects_blank_text_buffer(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
        caplog: pytest.LogCaptureFixture,
        blank: str,
    ) -> None:
        """The single-field rejection — a blank buffer never lands.

        A whitespace-only text is rejected whole, with the empty-amendment
        warning — the single predicate that distinguishes this walk from
        the creation walk, where a structurally absent field is lawful.
        """

        def buffer_blank(context: object) -> None:
            context.amend(blank)  # type: ignore[attr-defined]

        pin_package_environment(TWO_TOOL_ENVIRONMENT)
        install_tool_package("goga_tool_one", register_hooks=_register(("amend_todo_entry", buffer_blank)))

        with caplog.at_level(logging.WARNING):
            draft = TopicHooks().amend_todo_entry(IDENTITY, "saved text")

        assert draft.text == "saved text"
        expected_warning = (
            "hook buffer_blank of tool one failed on topics.amend_todo_entry: "
            "the buffered amendment is empty or whitespace-only"
        )

        assert expected_warning in caplog.text

    def test_amend_todo_entry_none_buffer_never_commits(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A None buffer value is the rejection case, never a committed text.

        The contract types ``text`` as ``str``; the out-of-contract None
        buffer is treated as the rejection case of this walk — the saved
        text survives and the empty-amendment warning fires, exactly like
        the blank buffer. On the creation side ``amend(None, None)`` is
        the lawful identity-only form; this is the single predicate that
        tells the two walks apart.
        """

        def buffer_none(context: object) -> None:
            context.amend(None)  # type: ignore[attr-defined]

        pin_package_environment(TWO_TOOL_ENVIRONMENT)
        install_tool_package("goga_tool_one", register_hooks=_register(("amend_todo_entry", buffer_none)))

        with caplog.at_level(logging.WARNING):
            draft = TopicHooks().amend_todo_entry(IDENTITY, "saved text")

        assert draft.text == "saved text"
        expected_warning = (
            "hook buffer_none of tool one failed on topics.amend_todo_entry: "
            "the buffered amendment is empty or whitespace-only"
        )

        assert expected_warning in caplog.text

    def test_amend_todo_entry_discards_buffer_of_raising_hook(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A failing hook never breaks the entry and never leaks its buffer."""
        pin_package_environment(TWO_TOOL_ENVIRONMENT)

        def boom(context: object) -> None:
            context.amend("boom text")  # type: ignore[attr-defined]
            raise RuntimeError("kaputt")

        def tail(context: object) -> None:
            context.amend("late text")  # type: ignore[attr-defined]

        install_tool_package("goga_tool_one", register_hooks=_register(("amend_todo_entry", boom)))
        install_tool_package("goga_tool_two", register_hooks=_register(("amend_todo_entry", tail)))

        with caplog.at_level(logging.WARNING):
            draft = TopicHooks().amend_todo_entry(IDENTITY, "saved text")

        assert draft.text == "late text"  # the buffer of boom is gone
        assert any(
            "hook boom of tool one failed on topics.amend_todo_entry: kaputt" in record.message
            for record in caplog.records
        )

    def test_amend_todo_entry_discards_buffer_of_unprocessable_type(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A text buffer of an out-of-contract type fails that hook alone — never the entry."""

        def numeric(context: object) -> None:
            context.amend(123)  # type: ignore[arg-type, attr-defined]

        def tail(context: object) -> None:
            context.amend("late text")  # type: ignore[attr-defined]

        pin_package_environment(TWO_TOOL_ENVIRONMENT)
        install_tool_package("goga_tool_one", register_hooks=_register(("amend_todo_entry", numeric)))
        install_tool_package("goga_tool_two", register_hooks=_register(("amend_todo_entry", tail)))

        with caplog.at_level(logging.WARNING):
            draft = TopicHooks().amend_todo_entry(IDENTITY, "saved text")

        assert draft.text == "late text"  # the buffer of numeric is gone
        assert any(
            "hook numeric of tool one failed on topics.amend_todo_entry:" in record.message and "int" in record.message
            for record in caplog.records
        )

    def test_amend_todo_entry_hard_class_stops_the_walk_with_clean_error(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A hard-class catalog record turns a hook failure into a clean error (D7)."""
        from goga.hooks.catalog import Action
        from goga.topics.hooks import events

        monkeypatch.setattr(
            events,
            "declared_actions",
            lambda: [Action(domain="topics", name="amend_todo_entry", error_class="hard")],
        )

        def boom(context: object) -> None:
            raise RuntimeError("stop")

        pin_package_environment(TWO_TOOL_ENVIRONMENT)
        install_tool_package("goga_tool_one", register_hooks=_register(("amend_todo_entry", boom)))

        with pytest.raises(ValueError, match=r"hook boom of tool one failed on topics\.amend_todo_entry: stop"):
            TopicHooks().amend_todo_entry(IDENTITY, "saved text")

    def test_amend_todo_entry_walks_per_hook_and_commits_the_last_buffer(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
    ) -> None:
        """The same per-hook staged walk over the single text field."""
        pin_package_environment(TWO_TOOL_ENVIRONMENT)

        def one(context: object) -> None:
            context.amend("first")  # type: ignore[attr-defined]

        def two(context: object) -> None:
            context.amend("second")  # type: ignore[attr-defined]

        install_tool_package(
            "goga_tool_one",
            register_hooks=_register(("amend_todo_entry", one), ("amend_todo_entry", two)),
        )

        draft = TopicHooks().amend_todo_entry(IDENTITY, "saved text")

        assert draft.text == "second"


# --- Logic tests: the notification emissions and the shared registry ---


class TestEmissions:
    def test_emit_created_shares_one_instance_and_returns_none(
        self,
        recording_hooks: Callable[..., list[tuple[str, str, object]]],
    ) -> None:
        """The context-instance sharing and the fire-and-forget contract.

        Both tools observe the identical underlying context, each through
        its own fresh delivery proxy — no per-tool copies, no return
        channel.
        """
        records = recording_hooks("topic_created")
        recording_hooks("topic_created", module_name="goga_tool_two")

        result = TopicHooks().emit_created(
            IDENTITY,
            checked_out=False,
            published=False,
            todo="t",
            commit_message="m",
            commit_hash="abc123",
        )

        assert result is None
        assert len(records) == 2
        first, second = records[0][2], records[1][2]

        assert type(first) is not TopicCreated  # the delivery view, not the context
        assert type(first) is not type(second)  # a fresh proxy per delivery
        assert first.identity is second.identity  # the shared instance, one attribute deep

        for delivered in (first, second):
            assert delivered.checked_out is False
            assert delivered.published is False
            assert delivered.todo == "t"
            assert delivered.commit_message == "m"
            assert delivered.commit_hash == "abc123"
            assert delivered.identity.home_path == ".goga/history/2026/add-topics-hooks"

    def test_run_registry_built_once_across_checkpoints(
        self,
        pin_package_environment: PinEnvironment,
        install_tool_package: InstallToolPackage,
    ) -> None:
        """D1 — the checkpoints never multiply the package enumeration.

        Every checkpoint — across separate ``TopicHooks`` instances and
        both checkpoint kinds — shares the one assembled registry.
        """
        actions: tuple[str, ...] = ("amend_creation", "topic_created", "topic_todo_entered", "amend_todo_entry")
        delivered: list[str] = []
        boundary = pin_package_environment(TWO_TOOL_ENVIRONMENT)

        def register_hooks(registrar: Any) -> None:
            for action in actions:

                def hook(context: object, _action: str = action) -> None:
                    delivered.append(_action)

                registrar.subscribe("topics", action, action, hook)

        install_tool_package("goga_tool_one", register_hooks=register_hooks)

        hooks = TopicHooks()
        hooks.amend_creation(IDENTITY, False, False, None, None)  # the identity-only form
        hooks.emit_created(IDENTITY, False, False, None, None, None)
        hooks.amend_todo_entry(IDENTITY, "t")
        hooks.emit_todo_entered(IDENTITY, "t")
        TopicHooks().emit_switched(IDENTITY, "local-checkout")  # a second instance

        assert boundary.call_count == 1
        assert delivered == ["amend_creation", "topic_created", "amend_todo_entry", "topic_todo_entered"]
