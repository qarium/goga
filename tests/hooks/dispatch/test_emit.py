"""Contract and logic tests for the entity declared in
``goga/hooks/dispatch/CODEMANIFEST`` with ``location: emit.py``:

- ``emit_hook_event(registry, domain, action, context_for)`` — the emission
  of an action to its subscribed hooks under the action's error class

The environment boundary is pinned by the shared fixtures of
``tests/hooks/conftest.py`` — the enumeration mapping and the fake
``goga_tool_*`` modules — so the registry, the registrars, and the delivery
run for real behind the emission. The hard failure treatment needs a
hard-class catalog record; ``tests/hooks/dispatch/conftest.py`` pins the
catalog of the emission for that, and the registration-side catalog is
pinned the same way in the hard-failure test below, so the hard address
registers through the real envelope.
"""

from __future__ import annotations

import importlib
import inspect
import typing
from collections.abc import Callable
from unittest import mock

import pytest
from goga.hooks.catalog import Action
from goga.hooks.dispatch import emit_hook_event
from goga.hooks.dispatch.delivery import wrap_context
from goga.hooks.registry import HookRegistry, ToolContext
from goga.hooks.tools import registration

_CELL_ALL = ["build_hook_arguments", "emit_hook_event", "wrap_context"]


def _noop_hook(context: object) -> None:
    """A stand-in registered callable — receiving the view is all it does."""


def _plain_view(tool: str) -> object:
    """A stand-in view builder — the view itself carries no meaning here."""
    return object()


def _subscribe(
    name: str,
    hook: Callable[..., object],
    domain: str = "statuses",
    action: str = "register_statuses",
) -> Callable[[object], None]:
    """Build a facade callback subscribing ``hook`` under ``name`` on an address."""

    def register_hooks(hooks: object) -> None:
        hooks.subscribe(domain, action, name, hook)  # type: ignore[attr-defined]

    return register_hooks


# --- Contract tests ---


class TestEmissionContract:
    def test_entity_is_importable_from_the_package_facade(self) -> None:
        """The emission lives on the cell package and its ``__all__`` is exact."""
        import goga.hooks.dispatch as cell
        from goga.hooks.dispatch.delivery import build_hook_arguments

        assert cell.emit_hook_event is emit_hook_event
        assert cell.build_hook_arguments is build_hook_arguments
        assert cell.wrap_context is wrap_context
        assert cell.__all__ == _CELL_ALL

    def test_module_defines_no_public_entity_beyond_the_one(self) -> None:
        """No extra API, and the cell imports from catalog and registry only."""
        module = importlib.import_module("goga.hooks.dispatch.emit")
        defined = {
            name
            for name, value in vars(module).items()
            if not name.startswith("_") and getattr(value, "__module__", None) == module.__name__
        }
        origin_modules = {str(getattr(value, "__module__", "")) for value in vars(module).values()}
        platform_origins = {
            origin for origin in origin_modules if origin.startswith("goga.hooks.") and origin != module.__name__
        }

        assert defined == {"emit_hook_event"}
        assert platform_origins <= {
            "goga.hooks.catalog",
            "goga.hooks.catalog.catalog",
            "goga.hooks.registry",
            "goga.hooks.registry.state",
            "goga.hooks.dispatch.delivery",
        }

    def test_signature_and_return(self) -> None:
        """The emission carries exactly the declared parameters and returns None."""
        assert list(inspect.signature(emit_hook_event).parameters) == [
            "registry",
            "domain",
            "action",
            "context_for",
        ]

        hints = typing.get_type_hints(emit_hook_event)

        assert hints["return"] is type(None)
        assert hints["registry"] is HookRegistry
        assert hints["domain"] is str
        assert hints["action"] is str

    def test_the_first_emission_performs_the_single_build(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The emission assembles the registry — no separate build step."""
        boundary = pin_package_environment({"goga_tool_a": ["goga-tool-a"]})
        install_tool_package("goga_tool_a", register_hooks=_subscribe("one", _noop_hook))
        registry = HookRegistry()

        assert registry.subscriptions == []

        emit_hook_event(registry, "statuses", "register_statuses", _plain_view)

        assert boundary.call_count == 1
        assert [s.name for s in registry.subscriptions] == ["one"]

    def test_a_second_emission_never_rebuilds_the_registry(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two emissions over one registry enumerate the environment once."""
        boundary = pin_package_environment({"goga_tool_a": ["goga-tool-a"]})
        calls: list[object] = []

        def hook(context: object) -> None:
            calls.append(context)

        install_tool_package("goga_tool_a", register_hooks=_subscribe("one", hook))
        registry = HookRegistry()

        emit_hook_event(registry, "statuses", "register_statuses", _plain_view)
        emit_hook_event(registry, "statuses", "register_statuses", _plain_view)

        assert boundary.call_count == 1
        assert len(calls) == 2  # the hook fires again; the build does not


# --- Logic tests: the delivered event ---


class TestEmissionDelivery:
    def test_emit_delivers_proxied_context_and_self_to_hook(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The hook receives the delivery view and its own tool context."""
        pin_package_environment({"goga_tool_demo": ["goga-tool-demo"]})
        captured: list[tuple[object, ToolContext]] = []

        def hook(self: ToolContext, context: object) -> None:
            captured.append((context, self))

        install_tool_package("goga_tool_demo", register_hooks=_subscribe("published", hook))
        sentinel = type("Sentinel", (), {"tool_name": "demo-tool-name", "marker": 1})()
        registry = HookRegistry()

        def context_for(tool: str) -> object:
            return sentinel

        emit_hook_event(registry, "statuses", "register_statuses", context_for)

        assert len(captured) == 1
        captured_context, captured_self = captured[0]

        assert captured_context is not sentinel
        assert captured_context.tool_name == sentinel.tool_name  # reads pass through

        with pytest.raises(AttributeError, match="read-only"):
            captured_context.marker = 2  # type: ignore[misc]

        assert sentinel.marker == 1  # the emitted object stays untouched
        assert isinstance(captured_self, ToolContext)
        assert captured_self.tool == "demo"
        assert captured_self is registry.self_context("demo")

        # The proxy class is created in a closure per delivery — an isinstance
        # check against any other proxy type can never succeed.
        assert not isinstance(captured_context, type(wrap_context(sentinel)))

    def test_emit_builds_one_view_per_distinct_tool(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One context view per distinct tool, reused by its remaining hooks."""
        pin_package_environment({"goga_tool_a": ["goga-tool-a"], "goga_tool_b": ["goga-tool-b"]})
        built_for: list[str] = []
        received: dict[str, list[object]] = {}

        def context_for(tool: str) -> object:
            built_for.append(tool)
            return type("View", (), {"token": object()})()  # a fresh token per built view

        def hook_of(label: str) -> Callable[..., None]:
            def hook(context: object) -> None:
                received.setdefault(label, []).append(context)

            return hook

        def register_a(hooks: object) -> None:
            subscribe = hooks.subscribe  # type: ignore[attr-defined]
            subscribe("statuses", "register_statuses", "one", hook_of("one"))
            subscribe("statuses", "register_statuses", "two", hook_of("two"))

        def register_b(hooks: object) -> None:
            hooks.subscribe("statuses", "register_statuses", "three", hook_of("three"))  # type: ignore[attr-defined]

        install_tool_package("goga_tool_a", register_hooks=register_a)
        install_tool_package("goga_tool_b", register_hooks=register_b)
        registry = HookRegistry()

        emit_hook_event(registry, "statuses", "register_statuses", context_for)

        assert built_for == ["a", "b"]  # one per distinct tool, first-subscription order
        assert set(received) == {"one", "two", "three"}

        # Both hooks of "a" read the same underlying view — the proxies differ,
        # the delivered object does not.
        assert received["one"][0].token is received["two"][0].token  # type: ignore[attr-defined]
        assert received["one"][0].token is not received["three"][0].token  # type: ignore[attr-defined]


# --- Logic tests: failures ---


class TestEmissionFailures:
    def test_emit_unknown_address_raises_clean_error(
        self,
        pin_package_environment,
    ) -> None:
        """An address outside the catalog is a clean error of the emitting side."""
        pin_package_environment({})
        registry = HookRegistry()

        with pytest.raises(ValueError, match=r"unknown hook action: statuses\.no_such_action"):
            emit_hook_event(registry, "statuses", "no_such_action", _plain_view)

    def test_emit_soft_failure_warns_and_continues(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A soft hook is skipped with a warning — the sequence continues."""
        pin_package_environment({"goga_tool_a": ["goga-tool-a"], "goga_tool_b": ["goga-tool-b"]})
        b_calls: list[object] = []

        def failing(context: object) -> None:
            raise ValueError("bad registration")

        def b_hook(context: object) -> None:
            b_calls.append(context)

        install_tool_package("goga_tool_a", register_hooks=_subscribe("x", failing))
        install_tool_package("goga_tool_b", register_hooks=_subscribe("y", b_hook))
        registry = HookRegistry()

        emit_hook_event(registry, "statuses", "register_statuses", _plain_view)

        assert len(b_calls) == 1
        assert "hook x of tool a failed on statuses.register_statuses: bad registration" in caplog.text

    def test_emit_hard_failure_stops_at_first_failure(
        self,
        pin_package_environment,
        install_tool_package,
        monkeypatch: pytest.MonkeyPatch,
        hard_action_catalog: object,
    ) -> None:
        """A hard hook failure stops the sequence with a clean error."""
        calls: list[str] = []

        def first(context: object) -> None:
            calls.append("first")
            raise RuntimeError("stop")

        def second(context: object) -> None:
            calls.append("second")

        monkeypatch.setattr(
            registration,
            "declared_actions",
            lambda: [
                Action(domain="d", name="act", error_class="hard"),
                Action(domain="statuses", name="register_statuses", error_class="soft"),
            ],
        )
        pin_package_environment({"goga_tool_t1": ["goga-tool-t1"], "goga_tool_t2": ["goga-tool-t2"]})
        install_tool_package("goga_tool_t1", register_hooks=_subscribe("n1", first, domain="d", action="act"))
        install_tool_package("goga_tool_t2", register_hooks=_subscribe("n2", second, domain="d", action="act"))
        registry = HookRegistry()

        with pytest.raises(ValueError, match=r"hook n1 of tool t1 failed on d\.act: stop"):
            emit_hook_event(registry, "d", "act", _plain_view)

        assert calls == ["first"]

    def test_emit_context_for_failure_is_clean_error_not_hook_failure(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A crashing view builder is an emitting-side error, never a warning."""
        pin_package_environment({"goga_tool_a": ["goga-tool-a"]})
        hook_calls: list[object] = []

        def hook(context: object) -> None:
            hook_calls.append(context)

        install_tool_package("goga_tool_a", register_hooks=_subscribe("x", hook))
        registry = HookRegistry()

        def context_for(tool: str) -> object:
            return 1 / 0  # a crash of the emitting side, not of the hook

        with pytest.raises(ZeroDivisionError):
            emit_hook_event(registry, "statuses", "register_statuses", context_for)

        assert hook_calls == []
        assert "failed on statuses.register_statuses" not in caplog.text

    def test_emit_projection_failure_is_treated_as_hook_failure(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An unprojectable signature is a hook failure under the error class."""
        pin_package_environment({"goga_tool_a": ["goga-tool-a"]})
        install_tool_package("goga_tool_a", register_hooks=_subscribe("built-in", dict))
        registry = HookRegistry()

        emit_hook_event(registry, "statuses", "register_statuses", _plain_view)

        assert "hook built-in of tool a failed on statuses.register_statuses" in caplog.text

    def test_emit_address_without_submissions_emits_nothing(
        self,
        pin_package_environment,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """No subscriptions of the address — no view, no call, no diagnostics."""
        pin_package_environment({})
        registry = HookRegistry()
        context_for = mock.Mock()

        result = emit_hook_event(registry, "statuses", "register_statuses", context_for)

        assert result is None
        context_for.assert_not_called()
        assert caplog.text == ""
