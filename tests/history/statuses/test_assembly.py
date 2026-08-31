"""Contract and logic tests for the routine declared in
``goga/history/statuses/CODEMANIFEST`` with ``location: assembly.py``:

- ``assemble_status_scale() -> scale`` — the built-in axis extended by every
  tool subscribed to the status action

The cell emits the action through the hooks platform; the tests fake the
emission by monkeypatching ``emit_hook_event`` in the assembly namespace — a
fake that captures the emission arguments and drives ``context_for`` the way
the real emission would: one view per distinct tool, hooks called in
enumeration order. The package enumeration belongs to the platform and is
pinned at its own boundary when asserted. The platform-side failure handling
(a crashed hook, a broken facade import inside the build) is covered by
``tests/hooks/``; the fatal import case is asserted here by letting the fake
re-raise it. Warnings are checked with ``capsys``.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any
from unittest import mock

import pytest
from goga.history import statuses as cell
from goga.history.statuses import Stage, StatusScale, assemble_status_scale
from goga.history.statuses import assembly as assembly_module
from goga.hooks import HookRegistry

Hook = Callable[[Any], None]

_BUILTIN_NAMES = [
    "empty",
    "new",
    "defined",
    "discovered",
    "backlog",
    "designed",
    "specified",
    "planned",
    "done",
]

_ENUMERATION_TARGET = "goga.hooks.tools.packages.packages_distributions"


def _hook(*registrations: dict[str, Any]) -> Hook:
    """A hook that registers the given entries in order through the delivered context."""

    def register(context: Any) -> None:
        for registration in registrations:
            context.register(**registration)

    return register


def _fake_emission(
    monkeypatch: pytest.MonkeyPatch,
    tools: list[tuple[str, Hook]],
) -> dict[str, Any]:
    """Replace the emission with a fake driving ``tools`` the way the real one would.

    ``tools`` pairs a tool identity with its hook, in the order the emission
    delivers them — the enumeration order of the platform. The fake captures
    the registry, the address, and ``context_for``, builds one view per
    distinct tool at the tool's first subscription, and calls each hook with
    its tool's view.

    Args:
        monkeypatch: the pytest patcher restoring the emission on teardown.
        tools: the ``(tool, hook)`` pairs the fake drives; the list is read
            at call time, so a test may append between two assemblies.

    Returns:
        The captured emission arguments — ``registry``, ``domain``,
        ``action``, ``context_for``.
    """
    captured: dict[str, Any] = {}

    def emit_hook_event(
        registry: HookRegistry,
        domain: str,
        action: str,
        context_for: Callable[[str], Any],
    ) -> None:
        captured["registry"] = registry
        captured["domain"] = domain
        captured["action"] = action
        captured["context_for"] = context_for

        views: dict[str, Any] = {}
        for tool, hook in tools:
            if tool not in views:
                views[tool] = context_for(tool)
            hook(views[tool])

    monkeypatch.setattr(assembly_module, "emit_hook_event", emit_hook_event)
    return captured


def _names(scale: StatusScale) -> list[str]:
    return [stage.name for stage in scale.stages]


# --- Contract tests ---


class TestAssemblyContract:
    def test_routine_is_importable_from_the_cell_facade(self) -> None:
        """``assemble_status_scale`` lives on the cell facade and its ``__all__``."""
        assert cell.assemble_status_scale is assemble_status_scale
        assert "assemble_status_scale" in cell.__all__

    def test_routine_takes_no_arguments(self) -> None:
        """``assemble_status_scale()`` — called with no arguments."""
        assert list(inspect.signature(assemble_status_scale).parameters) == []

    def test_routine_returns_a_status_scale(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``-> scale: StatusScale`` — the return carries a ``stages`` attribute."""
        _fake_emission(monkeypatch, [])

        scale = assemble_status_scale()

        assert isinstance(scale, StatusScale)
        assert isinstance(scale.stages, list)
        assert all(isinstance(stage, Stage) for stage in scale.stages)

    def test_routine_does_not_cache_across_runs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every call assembles a fresh scale — no caching between runs."""
        tools: list[tuple[str, Hook]] = []
        _fake_emission(monkeypatch, tools)

        first = assemble_status_scale()
        tools.append(("a", _hook({"name": "x", "filepath": "a/x.md", "after": "planned"})))
        second = assemble_status_scale()

        assert _names(first) == _BUILTIN_NAMES
        assert _names(second) != _names(first)
        assert second.stages is not first.stages

    def test_module_owns_no_package_enumeration(self) -> None:
        """The platform carries the tool packages — the cell owns neither name nor helper."""
        for name in ("packages_distributions", "import_module", "_tool_packages", "_import_tool_package"):
            assert not hasattr(assembly_module, name)


# --- Logic tests ---


class TestAssembleEmission:
    def test_assemble_emits_the_status_action_with_per_tool_registries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The cell emits the declared address; the view qualifies entries by the tool identity."""
        hook = _hook({"name": "pub", "filepath": "p.md", "after": "planned"})

        captured = _fake_emission(monkeypatch, [("alpha", hook)])
        scale = assemble_status_scale()

        assert captured["domain"] == "statuses"
        assert captured["action"] == "register_statuses"
        assert isinstance(captured["registry"], HookRegistry)
        names = _names(scale)
        assert "alpha.pub" in names
        assert names.index("alpha.pub") == names.index("planned") + 1

    def test_assemble_no_package_enumeration_in_the_cell(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The platform owns the enumeration — the assembly never reads the environment."""
        _fake_emission(monkeypatch, [])

        with mock.patch(_ENUMERATION_TARGET) as enumeration:
            assemble_status_scale()

        enumeration.assert_not_called()

    def test_assemble_registry_without_registrations_leaves_pure_axis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A subscribed tool whose hook registers nothing leaves the pure built-in axis."""
        _fake_emission(monkeypatch, [("quiet", lambda _context: None)])

        scale = assemble_status_scale()

        assert _names(scale) == _BUILTIN_NAMES

    def test_assemble_two_tools_same_anchor_form_registration_order_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two tools delivered to the same anchor stack in delivery order — one block."""
        _fake_emission(
            monkeypatch,
            [
                ("a", _hook({"name": "pub", "filepath": "a/p.md", "after": "planned"})),
                ("b", _hook({"name": "pub", "filepath": "b/p.md", "after": "planned"})),
            ],
        )

        scale = assemble_status_scale()

        names = _names(scale)
        planned = names.index("planned")
        assert names[planned + 1 : planned + 3] == ["a.pub", "b.pub"]
        assert names[planned + 3] == "done"


class TestAssembleBuiltinAxis:
    def test_assemble_status_scale_builds_nine_entry_axis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The built-in axis counts nine entries — ``new``/``title.txt`` second, no regress to eight."""
        _fake_emission(monkeypatch, [])

        scale = assemble_status_scale()

        assert _names(scale)[:9] == _BUILTIN_NAMES
        assert scale.stages[1].filepath == "title.txt"
        assert len(scale.stages) == 9

    def test_assemble_builtin_axis_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No subscribed tools — the pure built-in axis in the contract order."""
        _fake_emission(monkeypatch, [])

        scale = assemble_status_scale()

        assert _names(scale) == _BUILTIN_NAMES
        assert [stage.filepath for stage in scale.stages] == [
            "",
            "title.txt",
            "prd.md",
            "adr.md",
            "task.md",
            "arch.md",
            "design.md",
            "plan.md",
            "completed/plan.md",
        ]


class TestAssemblePlacement:
    def test_assemble_places_anchored_statuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``after`` lands right after its anchor; ``before`` right before its anchor."""
        _fake_emission(
            monkeypatch,
            [
                ("a", _hook({"name": "x", "filepath": "a/x.md", "after": "planned"})),
                ("b", _hook({"name": "y", "filepath": "b/y.md", "before": "done"})),
            ],
        )

        scale = assemble_status_scale()

        names = _names(scale)
        assert names.index("a.x") == names.index("planned") + 1
        assert names.index("b.y") == names.index("done") - 1

    def test_assemble_both_anchors_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Both anchors define a range — the entry lands inside it."""
        _fake_emission(
            monkeypatch,
            [("a", _hook({"name": "x", "filepath": "a/x.md", "after": "defined", "before": "backlog"}))],
        )

        scale = assemble_status_scale()

        names = _names(scale)
        assert names.index("discovered") < names.index("a.x") < names.index("backlog")

    def test_assembly_anchors_around_new_axis(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Anchors around ``empty``/``new``/``defined`` stay resolvable on the nine-entry axis."""
        _fake_emission(
            monkeypatch,
            [
                (
                    "x",
                    _hook(
                        {"name": "ranged", "filepath": "x/ranged.md", "after": "empty", "before": "defined"},
                        {"name": "afternew", "filepath": "x/afternew.md", "after": "new"},
                    ),
                )
            ],
        )

        scale = assemble_status_scale()

        names = _names(scale)
        assert names.index("empty") < names.index("x.ranged") < names.index("defined")
        assert names.index("new") < names.index("x.afternew") < names.index("defined")
        assert capsys.readouterr().err == ""

    def test_assemble_invalid_anchor_range_skips_with_warning(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An inverted range is invalid — the entry is skipped with a warning naming the entry."""
        _fake_emission(
            monkeypatch,
            [("a", _hook({"name": "x", "filepath": "a/x.md", "after": "backlog", "before": "defined"}))],
        )

        scale = assemble_status_scale()

        assert "a.x" not in _names(scale)
        stderr = capsys.readouterr().err
        assert "Warning: skipping status registration a.x" in stderr
        assert "anchor range" in stderr

    def test_assemble_unresolvable_anchor_warns_and_skips_entry(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An anchor naming no entry of the scale skips only its own entry — the rest survives."""
        _fake_emission(
            monkeypatch,
            [
                (
                    "a",
                    _hook(
                        {"name": "good", "filepath": "g.md", "after": "planned"},
                        {"name": "bad", "filepath": "b.md", "after": "nonexistent"},
                    ),
                )
            ],
        )

        scale = assemble_status_scale()

        names = _names(scale)
        assert "a.good" in names
        assert "a.bad" not in names
        assert "Warning: skipping status registration a.bad" in capsys.readouterr().err

    def test_assemble_unresolvable_before_anchor_skips(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A ``before`` anchor naming no entry of the scale skips the registration."""
        _fake_emission(
            monkeypatch,
            [("a", _hook({"name": "x", "filepath": "a/x.md", "before": "nonexistent.status"}))],
        )

        scale = assemble_status_scale()

        assert "a.x" not in _names(scale)
        stderr = capsys.readouterr().err
        assert "Warning: skipping status registration a.x" in stderr
        assert "unknown before anchor" in stderr
        assert _names(scale) == _BUILTIN_NAMES

    def test_assemble_same_anchor_block_follows_delivery_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The block follows the delivery order of the emission — the cell does not sort tools.

        The design-review q1 regression, re-based: sorting the packages is
        the platform's contract now, so the tools are delivered in reverse
        alphabetical order here and the assembly must still place them in
        delivery order — the order the registries were handed over in.
        """
        _fake_emission(
            monkeypatch,
            [
                ("b", _hook({"name": "y", "filepath": "b/y.md", "after": "planned"})),
                ("a", _hook({"name": "x", "filepath": "a/x.md", "after": "planned"})),
            ],
        )

        scale = assemble_status_scale()

        names = _names(scale)
        planned = names.index("planned")
        assert names[planned + 1 : planned + 3] == ["b.y", "a.x"]
        assert names[planned + 3] == "done"

    def test_assemble_two_entries_of_one_tool_same_anchor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two entries of one tool sharing an anchor also stack in order."""
        _fake_emission(
            monkeypatch,
            [
                (
                    "a",
                    _hook(
                        {"name": "x", "filepath": "a/x.md", "after": "planned"},
                        {"name": "z", "filepath": "a/z.md", "after": "planned"},
                    ),
                )
            ],
        )

        scale = assemble_status_scale()

        names = _names(scale)
        planned = names.index("planned")
        assert names[planned + 1 : planned + 3] == ["a.x", "a.z"]

    def test_assemble_prefix_is_the_delivered_tool_identity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The qualifier is the tool identity the emission delivers — hyphen form included."""
        _fake_emission(
            monkeypatch,
            [("hello-world", _hook({"name": "x", "filepath": "hw/x.md", "after": "planned"}))],
        )

        scale = assemble_status_scale()

        assert "hello-world.x" in _names(scale)

    def test_assemble_anchor_to_earlier_tool_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An entry may anchor to a tool entry accepted from an earlier tool."""
        _fake_emission(
            monkeypatch,
            [
                ("a", _hook({"name": "x", "filepath": "a/x.md", "after": "planned"})),
                ("b", _hook({"name": "y", "filepath": "b/y.md", "after": "a.x"})),
            ],
        )

        scale = assemble_status_scale()

        names = _names(scale)
        assert names.index("a.x") < names.index("b.y") < names.index("done")


class TestAssembleFailures:
    def test_assemble_broken_import_is_fatal_through_the_emission(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A broken package import is the only fatal case — it propagates through the emission."""

        def emit_hook_event(
            registry: HookRegistry,
            domain: str,
            action: str,
            context_for: Callable[[str], Any],
        ) -> None:
            raise ImportError("package goga_tool_bad failed to import: boom")

        monkeypatch.setattr(assembly_module, "emit_hook_event", emit_hook_event)

        with pytest.raises(ImportError, match="goga_tool_bad"):
            assemble_status_scale()
