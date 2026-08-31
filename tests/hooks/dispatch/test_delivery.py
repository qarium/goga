"""Contract and logic tests for the entities declared in
``goga/hooks/dispatch/CODEMANIFEST`` with ``location: delivery.py``:

- ``wrap_context(target)`` — the transparent delivery view of an emitted
  domain object: reads and calls pass through, writes are blocked
- ``build_hook_arguments(hook, context, self_context)`` — the fixed-name
  injection projected against the signature of the hook

The delivery zone owns no external boundary, so the logic tests are
mock-free: mediation is exercised over plain target objects and plain
functions. The package facade of the cell is built together with the
emission; here the entities are reached through their declared module.
"""

from __future__ import annotations

import importlib
import inspect
import typing

import pytest
from goga.hooks.dispatch.delivery import build_hook_arguments, wrap_context
from goga.hooks.registry import ToolContext


class _Emitted:
    """A stand-in emitted object: a plain attribute, a property, a method."""

    version = "1"

    @property
    def name(self) -> str:
        return "n"

    def register(self, entry: str) -> tuple[str, str]:
        return ("registered", entry)


# --- Contract tests ---


class TestDeliveryContract:
    def test_entities_are_importable_from_the_declared_module(self) -> None:
        """Both entities live on the module the CODEMANIFEST declares."""
        module = importlib.import_module("goga.hooks.dispatch.delivery")

        assert module.wrap_context is wrap_context
        assert module.build_hook_arguments is build_hook_arguments

    def test_module_defines_no_public_entity_beyond_the_two(self) -> None:
        """No extra API, and nothing reaches the cells beside the registry."""
        module = importlib.import_module("goga.hooks.dispatch.delivery")
        defined = {
            name
            for name, value in vars(module).items()
            if not name.startswith("_") and getattr(value, "__module__", None) == module.__name__
        }
        origin_modules = {str(getattr(value, "__module__", "")) for value in vars(module).values()}

        assert defined == {"build_hook_arguments", "wrap_context"}
        assert not any(origin.startswith("goga.hooks.tools") for origin in origin_modules)
        assert not any(origin.startswith("goga.hooks.catalog") for origin in origin_modules)

    def test_signatures(self) -> None:
        """Both functions carry exactly the declared parameters."""
        expected = {
            "wrap_context": ["target"],
            "build_hook_arguments": ["hook", "context", "self_context"],
        }
        module_globals = globals()
        hints = {name: typing.get_type_hints(module_globals[name]) for name in expected}

        for name, parameters in expected.items():
            assert list(inspect.signature(module_globals[name]).parameters) == parameters

        assert hints["wrap_context"]["return"] is object
        assert hints["build_hook_arguments"]["return"] == dict[str, object]
        assert hints["build_hook_arguments"]["self_context"] is ToolContext

    def test_wrap_context_returns_an_object(self) -> None:
        """The factory returns a proxy object — never the target itself."""
        target = object()
        proxy = wrap_context(target)

        assert isinstance(proxy, object)
        assert proxy is not target

    def test_the_proxy_type_carries_no_instance_state(self) -> None:
        """The proxy is a slots-only closure class — no instance dict."""
        proxy = wrap_context(object())

        assert type(proxy).__slots__ == ()
        assert not hasattr(proxy, "__dict__")


# --- Logic tests: the delivery proxy ---


class TestWrapContext:
    def test_wrap_context_passes_reads_properties_and_calls(self) -> None:
        """Reads, properties, and bound-method calls resolve on the target."""
        proxy = wrap_context(_Emitted())

        assert proxy.version == "1"
        assert proxy.name == "n"
        assert proxy.register("s") == ("registered", "s")

    def test_wrap_context_blocks_assignment_and_deletion(self) -> None:
        """Writes raise a clean error naming the mediation — the target stays."""
        target = type("Target", (), {"x": 1})()
        proxy = wrap_context(target)

        with pytest.raises(
            AttributeError,
            match="the delivered context is read-only: attribute assignment is blocked",
        ):
            proxy.x = 2  # type: ignore[misc]

        with pytest.raises(
            AttributeError,
            match="the delivered context is read-only: attribute deletion is blocked",
        ):
            del proxy.x  # type: ignore[attr-defined]

        assert target.x == 1
        assert proxy.x == 1

    def test_wrap_context_exposes_no_reference_to_target(self) -> None:
        """The proxy hides the target — no dict, no class identity, no alias."""
        target = type("Target", (), {"tool_name": "demo"})()
        proxy = wrap_context(target)

        # CPython answers vars() of an instance without __dict__ with a
        # TypeError; the checked fact is that no proxy dict exists to mine.
        with pytest.raises(TypeError):
            vars(proxy)  # type: ignore[arg-type]

        with pytest.raises(AttributeError):
            _ = proxy.__dict__  # type: ignore[attr-defined]

        assert proxy.__class__ is not type(target)
        assert hasattr(proxy, "tool_name") is True
        assert [name for name in dir(proxy) if not name.startswith("__")] == []
        assert target not in [getattr(proxy, name) for name in dir(proxy)]

    def test_wrap_context_dunder_lookup_never_reaches_target(self) -> None:
        """Special-method lookup follows the language default, not the target."""
        proxy = wrap_context(type("Sized", (), {"__len__": lambda _self: 5})())

        with pytest.raises(TypeError):
            len(proxy)  # type: ignore[arg-type]

        with pytest.raises(AttributeError):
            _ = proxy.__len__  # type: ignore[attr-defined]

    def test_the_proxy_class_is_fresh_per_delivery(self) -> None:
        """Every call builds its own class in the closure — no shared type."""
        target = object()

        assert type(wrap_context(target)) is not type(wrap_context(target))


# --- Logic tests: the signature projection ---


class TestBuildHookArguments:
    def test_build_hook_arguments_fills_declared_names_in_any_order(self) -> None:
        """Values land by declared name; unoffered and positional-only get nothing."""
        context_view = object()
        own = ToolContext(tool="demo")

        def takes_context(context: object) -> None:
            """Declares only the delivered view."""

        def takes_self_first(self: ToolContext, context: object) -> None:
            """Declares both — the tool context first."""

        def takes_context_first(context: object, self: ToolContext) -> None:
            """Declares both — the delivered view first."""

        def takes_keyword_only(*, context: object) -> None:
            """Declares the delivered view as keyword-only."""

        def takes_other(other: object) -> None:
            """Declares an unoffered name."""

        def takes_positional_only(context: object, /) -> None:
            """Declares the delivered view as positional-only — no injection."""

        def takes_mixed(first: object, /, context: object) -> None:
            """Only the name decides: a keyword-capable context still receives."""

        assert build_hook_arguments(takes_context, context_view, own) == {"context": context_view}
        assert build_hook_arguments(takes_self_first, context_view, own) == {
            "context": context_view,
            "self": own,
        }
        assert build_hook_arguments(takes_context_first, context_view, own) == {
            "context": context_view,
            "self": own,
        }
        assert build_hook_arguments(takes_keyword_only, context_view, own) == {"context": context_view}
        assert build_hook_arguments(takes_other, context_view, own) == {}
        assert build_hook_arguments(takes_positional_only, context_view, own) == {}
        assert build_hook_arguments(takes_mixed, context_view, own) == {"context": context_view}

    def test_build_hook_arguments_never_calls_the_hook(self) -> None:
        """The projection is a read of the signature — the call is not here."""
        calls: list[object] = []

        def hook(context: object, self: ToolContext) -> None:
            calls.append(context)

        arguments = build_hook_arguments(hook, object(), ToolContext(tool="t"))

        assert calls == []
        assert set(arguments) == {"context", "self"}
