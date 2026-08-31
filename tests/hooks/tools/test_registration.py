"""Contract and logic tests for the entities declared in
``goga/hooks/tools/CODEMANIFEST`` with ``location: registration.py``:

- ``HookRegistrar(tool)`` — the controlled registration surface of one tool
- ``Subscription(tool, domain, action, name, hook)`` — one accepted envelope
- ``RejectedRegistration(tool, domain, action, name, reason)`` — one refused
  envelope with its reason

The catalog read is the only seam: a test that needs a wider catalog
monkeypatches ``declared_actions`` in the namespace of the module under test.
The registrar itself runs for real — a hook is never called, so a plain
function stands in for one.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import typing

import pytest
from goga.hooks.catalog import Action
from goga.hooks.tools import HookRegistrar, RejectedRegistration, Subscription, registration

_CELL_ALL = [
    "HookRegistrar",
    "RejectedRegistration",
    "Subscription",
    "ToolPackage",
    "call_register_hooks",
    "enumerate_tool_packages",
]


def _hook() -> None:
    """A stand-in registered callable — the registrar never calls it."""


# --- Contract tests ---


class TestRegistrationContract:
    def test_entities_are_importable_from_the_package_facade(self) -> None:
        """All three entities live on the cell package and its ``__all__`` is exact."""
        import goga.hooks.tools as cell

        assert cell.HookRegistrar is HookRegistrar
        assert cell.Subscription is Subscription
        assert cell.RejectedRegistration is RejectedRegistration
        assert cell.__all__ == _CELL_ALL

        for name in _CELL_ALL:
            assert getattr(cell, name, None) is not None

    def test_module_defines_no_public_entity_beyond_the_three(self) -> None:
        """No extra API on ``registration.py``."""
        module = importlib.import_module("goga.hooks.tools.registration")
        defined = {
            name
            for name, value in vars(module).items()
            if not name.startswith("_") and getattr(value, "__module__", None) == module.__name__
        }

        assert defined == {"HookRegistrar", "RejectedRegistration", "Subscription"}

    def test_cell_does_not_import_from_registry_or_dispatch(self) -> None:
        """The cell stays below registry and dispatch in the dependency order."""
        modules = [
            importlib.import_module("goga.hooks.tools"),
            importlib.import_module("goga.hooks.tools.packages"),
            importlib.import_module("goga.hooks.tools.registration"),
        ]

        for module in modules:
            origins = {str(getattr(value, "__module__", "")) for value in vars(module).values()}

            assert not any(origin.startswith("goga.hooks.registry") for origin in origins)
            assert not any(origin.startswith("goga.hooks.dispatch") for origin in origins)

    def test_hook_registrar_is_a_kw_only_accumulating_dataclass(self) -> None:
        """``HookRegistrar(tool=...)`` — keyword-only, mutable, private state."""
        registrar = HookRegistrar(tool="t")

        assert registrar.tool == "t"
        assert dataclasses.is_dataclass(HookRegistrar)
        assert HookRegistrar.__dataclass_params__.kw_only
        assert not HookRegistrar.__dataclass_params__.frozen

        assert [(f.name, f.init, f.repr) for f in dataclasses.fields(HookRegistrar)] == [
            ("tool", True, True),
            ("_subscriptions", False, False),
            ("_rejections", False, False),
        ]

        with pytest.raises(TypeError):
            HookRegistrar("t")  # type: ignore[misc]

    def test_subscribe_signature(self) -> None:
        """``subscribe(self, domain, action, name, hook)`` — nothing else."""
        signature = inspect.signature(HookRegistrar.subscribe)
        return_hint = typing.get_type_hints(HookRegistrar.subscribe)["return"]

        assert list(signature.parameters) == ["self", "domain", "action", "name", "hook"]
        assert return_hint is type(None)

    def test_subscription_is_a_kw_only_frozen_record(self) -> None:
        """``Subscription`` carries exactly the five declared fields, frozen."""
        subscription = Subscription(
            tool="t",
            domain="statuses",
            action="register_statuses",
            name="published",
            hook=_hook,
        )

        assert subscription.tool == "t"
        assert subscription.domain == "statuses"
        assert subscription.action == "register_statuses"
        assert subscription.name == "published"
        assert subscription.hook is _hook

        assert dataclasses.is_dataclass(Subscription)
        assert Subscription.__dataclass_params__.frozen
        assert Subscription.__dataclass_params__.kw_only
        assert [f.name for f in dataclasses.fields(Subscription)] == [
            "tool",
            "domain",
            "action",
            "name",
            "hook",
        ]

        with pytest.raises(TypeError):
            Subscription("t", "statuses", "register_statuses", "published", _hook)  # type: ignore[misc]

        with pytest.raises(dataclasses.FrozenInstanceError):
            subscription.name = "other"  # type: ignore[misc]

    def test_rejected_registration_is_a_kw_only_frozen_record(self) -> None:
        """``RejectedRegistration`` carries exactly the five declared fields, frozen."""
        rejection = RejectedRegistration(
            tool="t",
            domain="statuses",
            action="register_statuses",
            name="dup",
            reason="repeated name on the same address",
        )

        assert rejection.tool == "t"
        assert rejection.domain == "statuses"
        assert rejection.action == "register_statuses"
        assert rejection.name == "dup"
        assert rejection.reason == "repeated name on the same address"

        assert dataclasses.is_dataclass(RejectedRegistration)
        assert RejectedRegistration.__dataclass_params__.frozen
        assert RejectedRegistration.__dataclass_params__.kw_only
        assert [f.name for f in dataclasses.fields(RejectedRegistration)] == [
            "tool",
            "domain",
            "action",
            "name",
            "reason",
        ]

        with pytest.raises(TypeError):
            RejectedRegistration("t", "statuses", "register_statuses", "dup", "why")  # type: ignore[misc]

        with pytest.raises(dataclasses.FrozenInstanceError):
            rejection.reason = "other"  # type: ignore[misc]

    def test_registrar_reads_start_empty(self) -> None:
        """``subscriptions`` and ``rejections`` are readable and start empty."""
        registrar = HookRegistrar(tool="t")

        assert isinstance(registrar.subscriptions, list)
        assert isinstance(registrar.rejections, list)
        assert registrar.subscriptions == []
        assert registrar.rejections == []


# --- Logic tests: the accepted envelope ---


class TestSubscribeAccepts:
    def test_subscribe_accepts_envelope_and_qualifies_with_registrar_tool(self) -> None:
        """One accepted envelope becomes one subscription qualified by the tool."""
        registrar = HookRegistrar(tool="my-tool")

        registrar.subscribe("statuses", "register_statuses", "published", _hook)

        assert registrar.subscriptions == [
            Subscription(
                tool="my-tool",
                domain="statuses",
                action="register_statuses",
                name="published",
                hook=_hook,
            )
        ]
        assert registrar.rejections == []

    def test_subscribe_same_name_different_address_is_allowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Uniqueness is per tool per address — the same name elsewhere applies."""
        monkeypatch.setattr(
            registration,
            "declared_actions",
            lambda: [
                Action(domain="statuses", name="register_statuses", error_class="soft"),
                Action(domain="statuses", name="register_other", error_class="soft"),
            ],
        )
        registrar = HookRegistrar(tool="t")

        registrar.subscribe("statuses", "register_statuses", "x", _hook)
        registrar.subscribe("statuses", "register_other", "x", _hook)

        assert [(s.domain, s.action, s.name) for s in registrar.subscriptions] == [
            ("statuses", "register_statuses", "x"),
            ("statuses", "register_other", "x"),
        ]
        assert registrar.rejections == []

    def test_subscribe_keeps_registration_order(self) -> None:
        """The accepted subscriptions read back in the order they arrived."""
        registrar = HookRegistrar(tool="t")

        for name in ("third", "first", "second"):
            registrar.subscribe("statuses", "register_statuses", name, _hook)

        assert [s.name for s in registrar.subscriptions] == ["third", "first", "second"]

    def test_subscribe_does_not_call_or_inspect_the_hook(self) -> None:
        """The callable is recorded verbatim — never called, never inspected."""
        calls: list[object] = []

        def counted() -> None:
            calls.append(counted)

        registrar = HookRegistrar(tool="t")

        registrar.subscribe("statuses", "register_statuses", "counted", counted)
        registrar.subscribe("statuses", "register_statuses", "builtin", dict)  # no signature

        assert calls == []
        assert [s.hook for s in registrar.subscriptions] == [counted, dict]
        assert registrar.rejections == []

    def test_subscription_and_rejection_reads_are_copies(self) -> None:
        """Mutating a returned list never reaches the registrar state."""
        registrar = HookRegistrar(tool="t")
        registrar.subscribe("statuses", "register_statuses", "published", _hook)

        registrar.subscriptions.clear()
        registrar.rejections.clear()

        assert [s.name for s in registrar.subscriptions] == ["published"]
        assert registrar.rejections == []


# --- Logic tests: the refused envelope ---


class TestSubscribeRejects:
    def test_subscribe_unknown_address_is_rejected_with_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An address outside the catalog is refused — data, not an exception."""
        registrar = HookRegistrar(tool="t")

        registrar.subscribe("nope", "no_action", "n", _hook)

        assert registrar.subscriptions == []
        assert [r.reason for r in registrar.rejections] == ["unknown action nope.no_action"]
        assert (registrar.rejections[0].tool, registrar.rejections[0].name) == ("t", "n")

        assert "Warning: rejected hook of tool t on nope.no_action: unknown action nope.no_action" in (
            capsys.readouterr().err
        )

    def test_subscribe_invalid_envelope_is_rejected_and_partial_registrations_survive(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Every violation is refused on its own; the accepted one survives."""
        registrar = HookRegistrar(tool="t")

        registrar.subscribe("statuses", "register_statuses", "ok", _hook)
        registrar.subscribe("statuses", "register_statuses", "", _hook)
        registrar.subscribe("statuses", "register_statuses", "not-callable", "not-callable")
        registrar.subscribe("statuses", "register_statuses", "ok", _hook)

        assert [s.name for s in registrar.subscriptions] == ["ok"]
        assert [r.reason for r in registrar.rejections] == [
            "name must be a non-empty string",
            "hook must be callable",
            "repeated name on the same address",
        ]

        err = capsys.readouterr().err
        assert err.count("Warning: rejected hook of tool t on statuses.register_statuses:") == 3

    def test_subscribe_non_string_name_is_rejected_with_an_empty_name(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A name that is not a string lands in the refusal as an empty string."""
        registrar = HookRegistrar(tool="t")

        registrar.subscribe("statuses", "register_statuses", None, _hook)  # type: ignore[arg-type]

        assert registrar.subscriptions == []
        assert registrar.rejections[0].name == ""
        assert registrar.rejections[0].reason == "name must be a non-empty string"
        assert capsys.readouterr().err.startswith(
            "Warning: rejected hook of tool t on statuses.register_statuses:"
        )

    def test_subscribe_repeats_are_refused_per_registrar(self) -> None:
        """Two tools hold separate registrars — the same name applies for both."""
        first = HookRegistrar(tool="a")
        second = HookRegistrar(tool="b")

        for registrar in (first, second):
            registrar.subscribe("statuses", "register_statuses", "published", _hook)

        assert [s.tool for s in first.subscriptions] == ["a"]
        assert [s.tool for s in second.subscriptions] == ["b"]
        assert first.rejections == []
        assert second.rejections == []
