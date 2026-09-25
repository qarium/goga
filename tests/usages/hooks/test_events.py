"""Contract and logic tests for the entity declared in
``goga/usages/hooks/CODEMANIFEST`` with ``location: events.py``:
``UsagesHooks`` — the checkpoint surface emitting the four run-level
moments of the sync and status operations over the hooks platform.

The surface runs for real over the platform boundary fixtures re-exported
by the zone test package — the registry, the registrars, and the delivery
execute the actual platform code; the fake ``goga_tool_*`` packages
imitate the consumer practice's subscribe sketch with the fixed offered
names. The entity is imported directly from its declaring module
``goga.usages.hooks.events`` — the ``location`` the cell CODEMANIFEST pins
(the facade re-export is pinned separately by ``test_facade.py``).
"""

from __future__ import annotations

import inspect
import typing

import pytest
from goga.usages.hooks.events import UsagesHooks
from goga.usages.hooks.facts import (
    Completion,
    DepDrift,
    SyncDepOutcome,
    SyncOutcome,
    UsagesMoment,
)


def _noop(_self: object, _context: object) -> None:
    """One no-op hook body shared by every address of the counting tool."""
    return None


# --- Contract tests ---


class TestSurfaceContract:
    def test_surface_is_a_class_with_exactly_the_four_emit_methods(self) -> None:
        """The public surface is the four emissions — nothing else is public."""
        public = [name for name in dir(UsagesHooks) if not name.startswith("_")]

        assert inspect.isclass(UsagesHooks)
        assert public == [
            "emit_status_completed",
            "emit_status_started",
            "emit_sync_completed",
            "emit_sync_started",
        ]

    def test_emit_methods_carry_the_declared_signatures(self) -> None:
        """Every method takes exactly the declared parameters."""
        assert list(inspect.signature(UsagesHooks.emit_sync_started).parameters) == ["self", "moment", "force"]
        assert list(inspect.signature(UsagesHooks.emit_sync_completed).parameters) == [
            "self",
            "moment",
            "deps",
            "success",
            "completion",
            "reason",
        ]
        assert list(inspect.signature(UsagesHooks.emit_status_started).parameters) == ["self", "moment"]
        assert list(inspect.signature(UsagesHooks.emit_status_completed).parameters) == [
            "self",
            "moment",
            "changed",
            "success",
            "completion",
            "reason",
        ]

    def test_emit_method_annotations_and_defaults_are_pinned(self) -> None:
        """The CODEMANIFEST types round-trip; ``reason`` defaults to None; none returns a value."""
        assert typing.get_type_hints(UsagesHooks.emit_sync_started) == {
            "moment": UsagesMoment,
            "force": bool,
            "return": type(None),
        }
        assert typing.get_type_hints(UsagesHooks.emit_sync_completed) == {
            "moment": UsagesMoment,
            "deps": list[SyncDepOutcome],
            "success": bool,
            "completion": Completion,
            "reason": str | None,
            "return": type(None),
        }
        assert typing.get_type_hints(UsagesHooks.emit_status_started) == {
            "moment": UsagesMoment,
            "return": type(None),
        }
        assert typing.get_type_hints(UsagesHooks.emit_status_completed) == {
            "moment": UsagesMoment,
            "changed": list[DepDrift],
            "success": bool,
            "completion": Completion,
            "reason": str | None,
            "return": type(None),
        }

        assert inspect.signature(UsagesHooks.emit_sync_completed).parameters["reason"].default is None
        assert inspect.signature(UsagesHooks.emit_status_completed).parameters["reason"].default is None


# --- Logic tests — the real platform over the boundary fixtures ---


class TestMomentDelivery:
    def test_construction_enumerates_nothing_and_one_registry_serves_all_four_moments(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Construction reads the environment zero times; four moments build one registry.

        The emissions never multiply the package enumeration, and the
        registrar callback of the tool runs exactly once however many
        moments fire.
        """
        boundary = pin_package_environment({"goga_tool_rec": ["goga-tool-rec"]})
        register_hooks_calls: list[str] = []

        def _register(hooks: object) -> None:
            register_hooks_calls.append("called")

            for action in ("sync_started", "sync_completed", "status_started", "status_completed"):
                hooks.subscribe("usages", action, "noop", _noop)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_rec", register_hooks=_register)

        m = UsagesMoment(operation="sync", group=None, dep=None)
        hooks = UsagesHooks()

        assert boundary.call_count == 0  # after construction alone

        hooks.emit_sync_started(m, False)
        hooks.emit_sync_completed(m, [], True, Completion.finished)
        hooks.emit_status_started(m)
        hooks.emit_status_completed(m, [], True, Completion.finished)

        assert boundary.call_count == 1
        assert register_hooks_calls == ["called"]  # the callback ran exactly once

    def test_emit_delivers_the_readonly_context_by_fixed_names(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The hooks receive the built context by the declared parameter names.

        A ``context``-only hook and a ``self, context`` hook both read the
        same frozen facts — the delivered view is write-closed by the
        platform proxy.
        """
        pin_package_environment({"goga_tool_rec": ["goga-tool-rec"]})
        captured: list[object] = []

        def _register(hooks: object) -> None:
            def record(context: object) -> None:
                captured.append(context)

            def record_self(self: object, context: object) -> None:
                self.last_context = context
                captured.append(context)

            hooks.subscribe("usages", "sync_started", "record", record)  # type: ignore[attr-defined]
            hooks.subscribe("usages", "sync_completed", "record_self", record_self)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_rec", register_hooks=_register)

        m = UsagesMoment(operation="sync", group=None, dep=None)
        outcome = SyncDepOutcome(
            group="libs",
            dep="click",
            outcome=SyncOutcome.failed,
            message="failed to sync usages for libs/click",
        )
        hooks = UsagesHooks()

        hooks.emit_sync_started(m, True)
        hooks.emit_sync_completed(m, [outcome], False, Completion.crashed, reason="boom")

        assert captured[0].moment is m
        assert captured[0].force is True
        assert captured[1].deps == [outcome]
        assert captured[1].success is False
        assert captured[1].completion is Completion.crashed
        assert captured[1].reason == "boom"

        with pytest.raises(AttributeError):
            captured[0].force = False  # type: ignore[misc]  # the delivered view is read-only

    def test_a_hook_receives_nothing_it_did_not_declare(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A ``self``-only hook is called with ``self`` alone — no ``TypeError``.

        The fixed offered-names injection is platform-guaranteed; the zone
        must not have broken it by its context shape.
        """
        pin_package_environment({"goga_tool_rec": ["goga-tool-rec"]})
        seen: list[str] = []

        def _register(hooks: object) -> None:
            def only_self(self: object) -> None:
                self.was_called = True
                seen.append("called")

            hooks.subscribe("usages", "status_started", "only_self", only_self)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_rec", register_hooks=_register)

        m = UsagesMoment(operation="status", group=None, dep=None)

        UsagesHooks().emit_status_started(m)

        assert seen == ["called"]  # the call injected only self
