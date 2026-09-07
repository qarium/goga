"""Contract and logic tests for the entities declared in
``goga/hooks/registry/CODEMANIFEST`` with ``location: state.py``:

- ``HookRegistry()`` — the run registry: the single assembly, the read side,
  the isolated per-tool contexts, and the per-tool inspection view
- ``ToolContext(tool)`` — the isolated runtime context of one tool
- ``ToolHooks(tool, subscriptions, rejections)`` — the per-tool inspection
  entry

The environment boundary is pinned by the shared fixtures of
``tests/hooks/conftest.py`` — the enumeration mapping and the fake
``goga_tool_*`` modules. The registry, its registrars, and the package access
run for real; the fatal broken-import case is mocked at the
``call_register_hooks`` seam in one test and driven through a real broken
package on disk in another.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import typing
from collections.abc import Callable
from pathlib import Path

import pytest
from goga.hooks.registry import HookRegistry, ToolContext, ToolHooks
from goga.hooks.tools import RejectedRegistration, Subscription

from tests.conftest import is_kw_only_dataclass

_CELL_ALL = ["HookRegistry", "ToolContext", "ToolHooks"]


def _noop_hook(context: object) -> None:
    """A stand-in registered callable — the registry never calls it."""


def _subscribe(name: str) -> Callable[[object], None]:
    """Build a facade callback subscribing one hook under ``name``."""

    def register_hooks(hooks: object) -> None:
        hooks.subscribe("statuses", "register_statuses", name, _noop_hook)  # type: ignore[attr-defined]

    return register_hooks


# --- Contract tests ---


class TestRegistryContract:
    def test_entities_are_importable_from_the_package_facade(self) -> None:
        """All three entities live on the cell package and its ``__all__`` is exact."""
        import goga.hooks.registry as cell

        assert cell.HookRegistry is HookRegistry
        assert cell.ToolContext is ToolContext
        assert cell.ToolHooks is ToolHooks
        assert cell.__all__ == _CELL_ALL

        for name in _CELL_ALL:
            assert getattr(cell, name, None) is not None

    def test_module_defines_no_public_entity_beyond_the_three(self) -> None:
        """No extra API, and nothing reaches the cells above the registry."""
        module = importlib.import_module("goga.hooks.registry.state")
        defined = {
            name
            for name, value in vars(module).items()
            if not name.startswith("_") and getattr(value, "__module__", None) == module.__name__
        }
        origin_modules = {str(getattr(value, "__module__", "")) for value in vars(module).values()}

        assert defined == {"HookRegistry", "ToolContext", "ToolHooks"}
        assert not any(origin.startswith("goga.hooks.dispatch") for origin in origin_modules)
        assert not any(origin.startswith("goga.hooks.catalog") for origin in origin_modules)

    def test_hook_registry_constructs_with_no_arguments(self) -> None:
        """``HookRegistry()`` — keyword-only dataclass, private build state."""
        registry = HookRegistry()

        assert isinstance(registry, HookRegistry)
        assert dataclasses.is_dataclass(HookRegistry)
        assert is_kw_only_dataclass(HookRegistry)
        assert not HookRegistry.__dataclass_params__.frozen

        assert [(f.name, f.init, f.repr) for f in dataclasses.fields(HookRegistry)] == [
            ("_built", False, False),
            ("_subscriptions", False, False),
            ("_rejections", False, False),
            ("_contexts", False, False),
        ]

        with pytest.raises(TypeError):
            HookRegistry("anything")  # type: ignore[misc]

    def test_method_signatures(self) -> None:
        """The four methods carry exactly the declared parameters."""
        expected = {
            "build_once": ["self"],
            "subscriptions_for": ["self", "domain", "action"],
            "self_context": ["self", "tool"],
            "by_tool": ["self"],
        }
        return_hints = {name: typing.get_type_hints(getattr(HookRegistry, name))["return"] for name in expected}

        for name, parameters in expected.items():
            assert list(inspect.signature(getattr(HookRegistry, name)).parameters) == parameters

        assert return_hints["build_once"] is type(None)
        assert return_hints["subscriptions_for"] == list[Subscription]
        assert return_hints["self_context"] is ToolContext
        assert return_hints["by_tool"] == list[ToolHooks]

    def test_reads_are_lists_and_start_empty(self) -> None:
        """``subscriptions`` and ``rejections`` are readable lists before the build."""
        registry = HookRegistry()

        assert isinstance(registry.subscriptions, list)
        assert isinstance(registry.rejections, list)
        assert registry.subscriptions == []
        assert registry.rejections == []

    def test_construction_enumerates_nothing(self, pin_package_environment) -> None:
        """A fresh registry is cheap — the environment is not read at construction."""
        boundary = pin_package_environment({"goga_tool_a": ["goga-tool-a"]})

        HookRegistry()

        boundary.assert_not_called()

    def test_reads_never_trigger_the_build(self, pin_package_environment) -> None:
        """The read properties are pure reads — no enumeration behind them."""
        boundary = pin_package_environment({"goga_tool_a": ["goga-tool-a"]})
        registry = HookRegistry()

        assert registry.subscriptions == []
        assert registry.rejections == []
        assert registry.subscriptions_for("statuses", "register_statuses") == []
        assert registry.by_tool() == []

        boundary.assert_not_called()

    def test_tool_context_is_kw_only_mutable_and_open(self) -> None:
        """``ToolContext(tool=...)`` — keyword-only, mutable, no ``__slots__``."""
        context = ToolContext(tool="t")

        assert context.tool == "t"
        assert dataclasses.is_dataclass(ToolContext)
        assert is_kw_only_dataclass(ToolContext)
        assert not ToolContext.__dataclass_params__.frozen
        assert [f.name for f in dataclasses.fields(ToolContext)] == ["tool"]

        context.own_state = {"runs": 1}  # a hook writes its own context freely

        assert context.own_state == {"runs": 1}
        assert not hasattr(ToolContext, "__slots__")

        with pytest.raises(TypeError):
            ToolContext("t")  # type: ignore[misc]

    def test_tool_hooks_is_a_kw_only_frozen_record(self) -> None:
        """``ToolHooks`` carries exactly the three declared fields, frozen."""
        subscription = Subscription(
            tool="t",
            domain="statuses",
            action="register_statuses",
            name="published",
            hook=_noop_hook,
        )
        rejection = RejectedRegistration(
            tool="t",
            domain="statuses",
            action="register_statuses",
            name="dup",
            reason="repeated name on the same address",
        )
        entry = ToolHooks(tool="t", subscriptions=[subscription], rejections=[rejection])

        assert entry.tool == "t"
        assert entry.subscriptions == [subscription]
        assert entry.rejections == [rejection]

        assert dataclasses.is_dataclass(ToolHooks)
        assert ToolHooks.__dataclass_params__.frozen
        assert is_kw_only_dataclass(ToolHooks)
        assert [f.name for f in dataclasses.fields(ToolHooks)] == [
            "tool",
            "subscriptions",
            "rejections",
        ]

        with pytest.raises(TypeError):
            ToolHooks("t", [], [])  # type: ignore[misc]

        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.tool = "other"  # type: ignore[misc]


# --- Logic tests: the single build ---


class TestBuildOnce:
    def test_build_once_collects_in_enumeration_order(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Subscriptions land in enumeration order, qualified by package identity."""
        pin_package_environment({"goga_tool_a": ["goga-tool-a"], "goga_tool_b": ["goga-tool-b"]})
        install_tool_package("goga_tool_a", register_hooks=_subscribe("one"))
        install_tool_package("goga_tool_b", register_hooks=_subscribe("two"))
        registry = HookRegistry()

        registry.build_once()

        assert [(s.tool, s.name) for s in registry.subscriptions] == [("a", "one"), ("b", "two")]

    def test_build_once_is_idempotent(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two builds over one registry enumerate once and never double the state."""
        boundary = pin_package_environment({"goga_tool_a": ["goga-tool-a"]})
        install_tool_package("goga_tool_a", register_hooks=_subscribe("one"))
        registry = HookRegistry()

        registry.build_once()
        registry.build_once()

        assert boundary.call_count == 1
        assert [s.name for s in registry.subscriptions] == ["one"]

    def test_build_once_skips_a_package_without_the_callback_quietly(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A facade without ``register_hooks`` is a quiet skip — no warning."""
        pin_package_environment({"goga_tool_a": ["goga-tool-a"], "goga_tool_b": ["goga-tool-b"]})
        install_tool_package("goga_tool_a")  # no callback on the facade
        install_tool_package("goga_tool_b", register_hooks=_subscribe("two"))
        registry = HookRegistry()

        registry.build_once()

        assert [s.name for s in registry.subscriptions] == ["two"]
        assert caplog.text == ""

    def test_build_once_collects_rejections_of_every_registrar(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Refused envelopes are part of the assembled state, in order."""
        pin_package_environment({"goga_tool_a": ["goga-tool-a"]})

        def register_hooks(hooks: object) -> None:
            subscribe = hooks.subscribe  # type: ignore[attr-defined]
            subscribe("statuses", "register_statuses", "ok", _noop_hook)
            subscribe("statuses", "register_statuses", "ok", _noop_hook)  # repeated
            subscribe("statuses", "no_such_action", "lost", _noop_hook)  # unknown address

        install_tool_package("goga_tool_a", register_hooks=register_hooks)
        registry = HookRegistry()

        registry.build_once()

        assert [r.reason for r in registry.rejections] == [
            "repeated name on the same address",
            "unknown action statuses.no_such_action",
        ]
        assert [r.tool for r in registry.rejections] == ["a", "a"]

    def test_build_once_callback_crash_warns_and_keeps_partial_registrations(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A crashed callback ends its own registration only — the rest runs."""
        pin_package_environment({"goga_tool_a": ["goga-tool-a"], "goga_tool_b": ["goga-tool-b"]})

        def crashing(hooks: object) -> None:
            hooks.subscribe("statuses", "register_statuses", "first", _noop_hook)  # type: ignore[attr-defined]
            raise RuntimeError("kaput")

        install_tool_package("goga_tool_a", register_hooks=crashing)
        install_tool_package("goga_tool_b", register_hooks=_subscribe("second"))
        registry = HookRegistry()

        registry.build_once()

        assert [s.name for s in registry.subscriptions] == ["first", "second"]
        assert "skipping hook registration of tool a: kaput" in caplog.text

    def test_build_once_broken_import_is_fatal_through_the_real_import(
        self,
        pin_package_environment,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The real import boundary and the real build agree on the fatal case.

        A facade importing a missing dependency fails through the platform's
        own wrapper, and the build re-raises it: the producer
        (``call_register_hooks``) and the consumer (``build_once``) run
        together here, so the fatal case does not rest on a hand-crafted
        message at the ``call_register_hooks`` seam.
        """
        package_dir = tmp_path / "goga_tool_broken"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("import goga_missing_dependency\n")
        monkeypatch.syspath_prepend(tmp_path)
        pin_package_environment({"goga_tool_broken": ["goga-tool-broken"]})
        registry = HookRegistry()

        with pytest.raises(ImportError, match=r"package goga_tool_broken failed to import"):
            registry.build_once()

    def test_build_once_callback_importerror_is_warning_not_fatal(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An import failure raised inside a callback is a crash, not the fatal case."""
        pin_package_environment({"goga_tool_a": ["goga-tool-a"], "goga_tool_b": ["goga-tool-b"]})

        def crashing(hooks: object) -> None:
            hooks.subscribe("statuses", "register_statuses", "first", _noop_hook)  # type: ignore[attr-defined]
            raise ModuleNotFoundError("No module named 'opt_dep'", name="opt_dep")

        install_tool_package("goga_tool_a", register_hooks=crashing)
        install_tool_package("goga_tool_b", register_hooks=_subscribe("second"))
        registry = HookRegistry()

        registry.build_once()

        assert [s.name for s in registry.subscriptions] == ["first", "second"]
        assert "skipping hook registration of tool a" in caplog.text


# --- Logic tests: the read side ---


class TestRegistryReads:
    def test_subscriptions_for_returns_the_address_subscriptions_in_order(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Exact address match, enumeration order."""
        pin_package_environment({"goga_tool_a": ["goga-tool-a"], "goga_tool_b": ["goga-tool-b"]})
        install_tool_package("goga_tool_a", register_hooks=_subscribe("one"))
        install_tool_package("goga_tool_b", register_hooks=_subscribe("two"))
        registry = HookRegistry()

        registry.build_once()

        assert [s.name for s in registry.subscriptions_for("statuses", "register_statuses")] == ["one", "two"]
        assert [s.name for s in registry.subscriptions_for("statuses", "register_other")] == []

    def test_subscriptions_for_empty_address_is_not_an_error(
        self,
        pin_package_environment,
    ) -> None:
        """An address without subscriptions yields an empty list."""
        pin_package_environment({})
        registry = HookRegistry()

        registry.build_once()

        assert registry.subscriptions_for("statuses", "register_statuses") == []
        assert registry.subscriptions_for("nope", "no_action") == []

    def test_self_context_returns_one_instance_per_tool(self) -> None:
        """One context per tool per run — the tool's invocations share it."""
        registry = HookRegistry()

        first = registry.self_context("a")
        second = registry.self_context("a")
        other = registry.self_context("b")

        assert first is second
        assert first is not other
        assert first.tool == "a"
        assert other.tool == "b"

    def test_by_tool_groups_alphabetically_with_rejections(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One entry per tool, alphabetical — both lists on the same entry."""
        pin_package_environment({"goga_tool_b": ["goga-tool-b"], "goga_tool_a": ["goga-tool-a"]})
        install_tool_package("goga_tool_b", register_hooks=_subscribe("kept"))

        def refused(hooks: object) -> None:
            subscribe = hooks.subscribe  # type: ignore[attr-defined]
            subscribe("statuses", "register_statuses", "kept", _noop_hook)
            subscribe("statuses", "register_statuses", "dup", "not-callable")

        install_tool_package("goga_tool_a", register_hooks=refused)
        registry = HookRegistry()

        registry.build_once()

        view = registry.by_tool()

        assert [entry.tool for entry in view] == ["a", "b"]
        assert [s.name for s in view[0].subscriptions] == ["kept"]
        assert [r.name for r in view[0].rejections] == ["dup"]
        assert [s.name for s in view[1].subscriptions] == ["kept"]
        assert view[1].rejections == []

    def test_by_tool_of_an_empty_registry_is_empty(self) -> None:
        """A registry without registrations carries no entry at all."""
        assert HookRegistry().by_tool() == []
