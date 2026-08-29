"""Contract and logic tests for the routine declared in
``goga/history/statuses/CODEMANIFEST`` with ``location: assembly.py``:

- ``assemble_status_scale() -> scale`` — the built-in axis extended by every
  installed tool package

The package enumeration and imports are mocked at the point of import; fake
packages are injected through ``sys.modules``. Warnings are checked with
``capsys``.
"""

from __future__ import annotations

import inspect
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any

import pytest
from goga.history import statuses as cell
from goga.history.statuses import Stage, StatusScale, assemble_status_scale
from goga.history.statuses import assembly as assembly_module

Registration = Callable[[Any], None]

_BUILTIN_NAMES = [
    "empty",
    "defined",
    "discovered",
    "backlog",
    "designed",
    "specified",
    "planned",
    "done",
]


def _install_package(monkeypatch: pytest.MonkeyPatch, name: str, attribute: Any) -> ModuleType:
    """Inject a fake ``goga_tool_*`` package into ``sys.modules``.

    ``attribute`` is the value the module carries as
    ``register_topic_statuses`` — a callable callback, a non-callable value,
    or ``None`` for a package without the attribute.
    """
    module = ModuleType(name)
    if attribute is not None:
        module.register_topic_statuses = attribute
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _registering(*registrations: dict[str, Any]) -> Registration:
    """A callback that registers the given entries in order."""

    def register_topic_statuses(statuses: Any) -> None:
        for registration in registrations:
            statuses.register(**registration)

    return register_topic_statuses


def _packages(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    """Patch the package enumeration to exactly ``names``."""
    monkeypatch.setattr(
        assembly_module,
        "packages_distributions",
        lambda: {name: [f"dist-{name}"] for name in names},
    )


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
        _packages(monkeypatch)

        scale = assemble_status_scale()

        assert isinstance(scale, StatusScale)
        assert isinstance(scale.stages, list)
        assert all(isinstance(stage, Stage) for stage in scale.stages)

    def test_routine_does_not_cache_across_runs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every call assembles a fresh scale — no caching between runs."""
        _packages(monkeypatch)
        first = assemble_status_scale()
        _install_package(
            monkeypatch,
            "goga_tool_a",
            _registering({"name": "x", "filepath": "a/x.md", "after": "planned"}),
        )
        _packages(monkeypatch, "goga_tool_a")

        second = assemble_status_scale()

        assert _names(first) == _BUILTIN_NAMES
        assert _names(second) != _names(first)
        assert second.stages is not first.stages


# --- Logic tests ---


class TestAssembleBuiltinAxis:
    def test_assemble_builtin_axis_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No tool packages — the pure built-in axis in the contract order."""
        _packages(monkeypatch)

        scale = assemble_status_scale()

        assert _names(scale) == _BUILTIN_NAMES
        assert [stage.filepath for stage in scale.stages] == [
            "",
            "prd.md",
            "adr.md",
            "task.md",
            "arch.md",
            "design.md",
            "plan.md",
            "completed/plan.md",
        ]

    def test_assemble_non_callable_callback_skipped(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A package whose callback attribute is not callable is skipped silently."""
        _install_package(monkeypatch, "goga_tool_bad", 42)
        _packages(monkeypatch, "goga_tool_bad")

        scale = assemble_status_scale()

        assert _names(scale) == _BUILTIN_NAMES
        assert capsys.readouterr().err == ""


class TestAssemblePlacement:
    def test_assemble_places_anchored_statuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``after`` lands right after its anchor; ``before`` right before its anchor."""
        _install_package(
            monkeypatch, "goga_tool_a", _registering({"name": "x", "filepath": "a/x.md", "after": "planned"})
        )
        _install_package(
            monkeypatch, "goga_tool_b", _registering({"name": "y", "filepath": "b/y.md", "before": "done"})
        )
        _packages(monkeypatch, "goga_tool_a", "goga_tool_b")

        scale = assemble_status_scale()

        names = _names(scale)
        assert names.index("a.x") == names.index("planned") + 1
        assert names.index("b.y") == names.index("done") - 1

    def test_assemble_both_anchors_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Both anchors define a range — the entry lands inside it."""
        _install_package(
            monkeypatch,
            "goga_tool_a",
            _registering({"name": "x", "filepath": "a/x.md", "after": "defined", "before": "backlog"}),
        )
        _packages(monkeypatch, "goga_tool_a")

        scale = assemble_status_scale()

        names = _names(scale)
        assert names.index("discovered") < names.index("a.x") < names.index("backlog")

    def test_assemble_invalid_anchor_range_skips_with_warning(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An inverted range is invalid — the entry is skipped with a warning."""
        _install_package(
            monkeypatch,
            "goga_tool_a",
            _registering({"name": "x", "filepath": "a/x.md", "after": "backlog", "before": "defined"}),
        )
        _packages(monkeypatch, "goga_tool_a")

        scale = assemble_status_scale()

        assert "a.x" not in _names(scale)
        stderr = capsys.readouterr().err
        assert "Warning" in stderr
        assert "goga_tool_a" in stderr

    def test_assemble_unresolvable_anchor_skips(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An anchor naming no entry of the scale skips the registration."""
        _install_package(
            monkeypatch,
            "goga_tool_a",
            _registering({"name": "x", "filepath": "a/x.md", "after": "nonexistent.status"}),
        )
        _packages(monkeypatch, "goga_tool_a")

        scale = assemble_status_scale()

        assert "a.x" not in _names(scale)
        stderr = capsys.readouterr().err
        assert "Warning" in stderr
        assert "goga_tool_a" in stderr
        assert _names(scale) == _BUILTIN_NAMES

    def test_assemble_unresolvable_before_anchor_skips(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A ``before`` anchor naming no entry of the scale skips the registration."""
        _install_package(
            monkeypatch,
            "goga_tool_a",
            _registering({"name": "x", "filepath": "a/x.md", "before": "nonexistent.status"}),
        )
        _packages(monkeypatch, "goga_tool_a")

        scale = assemble_status_scale()

        assert "a.x" not in _names(scale)
        stderr = capsys.readouterr().err
        assert "Warning" in stderr
        assert "goga_tool_a" in stderr
        assert _names(scale) == _BUILTIN_NAMES

    def test_assemble_same_anchor_block_keeps_registration_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two packages anchoring after the same entry form a block in package order.

        The design-review q1 regression: a bare ``insert(pos(A) + 1)`` would
        reverse the block — the alphabetical package order must win. The
        enumeration map is handed to the packages in reverse order so the
        assertion depends on the alphabetical sort, not on dict insertion
        order.
        """
        _install_package(
            monkeypatch, "goga_tool_a", _registering({"name": "x", "filepath": "a/x.md", "after": "planned"})
        )
        _install_package(
            monkeypatch, "goga_tool_b", _registering({"name": "y", "filepath": "b/y.md", "after": "planned"})
        )
        _packages(monkeypatch, "goga_tool_b", "goga_tool_a")

        scale = assemble_status_scale()

        names = _names(scale)
        planned = names.index("planned")
        assert names[planned + 1 : planned + 3] == ["a.x", "b.y"]
        assert names[planned + 3] == "done"

    def test_assemble_two_entries_of_one_package_same_anchor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two entries of one package sharing an anchor also stack in order."""
        _install_package(
            monkeypatch,
            "goga_tool_a",
            _registering(
                {"name": "x", "filepath": "a/x.md", "after": "planned"},
                {"name": "z", "filepath": "a/z.md", "after": "planned"},
            ),
        )
        _packages(monkeypatch, "goga_tool_a")

        scale = assemble_status_scale()

        names = _names(scale)
        planned = names.index("planned")
        assert names[planned + 1 : planned + 3] == ["a.x", "a.z"]

    def test_assemble_tool_prefix_strips_package_qualifier(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """P1 — the prefix is the top-level name without the ``goga_tool_`` part."""
        _install_package(
            monkeypatch,
            "goga_tool_hello_world",
            _registering({"name": "x", "filepath": "hw/x.md", "after": "planned"}),
        )
        _packages(monkeypatch, "goga_tool_hello_world")

        scale = assemble_status_scale()

        assert "hello_world.x" in _names(scale)

    def test_assemble_anchor_to_earlier_tool_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An entry may anchor to a tool entry accepted from an earlier package."""
        _install_package(
            monkeypatch, "goga_tool_a", _registering({"name": "x", "filepath": "a/x.md", "after": "planned"})
        )
        _install_package(monkeypatch, "goga_tool_b", _registering({"name": "y", "filepath": "b/y.md", "after": "a.x"}))
        _packages(monkeypatch, "goga_tool_a", "goga_tool_b")

        scale = assemble_status_scale()

        names = _names(scale)
        assert names.index("a.x") < names.index("b.y") < names.index("done")


class TestAssembleFailures:
    def test_assemble_broken_import_is_fatal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A package import failure is the only fatal case — a clean error."""
        _packages(monkeypatch, "goga_tool_bad")

        def _raise(name: str) -> ModuleType:
            raise ModuleNotFoundError(f"No module named {name!r}")

        monkeypatch.setattr(assembly_module, "import_module", _raise)

        with pytest.raises(ImportError, match="goga_tool_bad"):
            assemble_status_scale()

    def test_assemble_bad_registration_warns_and_continues(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A second, anchor-less registration skips with a warning; the rest survives."""
        _install_package(
            monkeypatch,
            "goga_tool_a",
            _registering(
                {"name": "good", "filepath": "a/good.md", "after": "planned"},
                {"name": "bad", "filepath": "a/bad.md"},
            ),
        )
        _install_package(
            monkeypatch, "goga_tool_b", _registering({"name": "y", "filepath": "b/y.md", "before": "done"})
        )
        _packages(monkeypatch, "goga_tool_a", "goga_tool_b")

        scale = assemble_status_scale()

        names = _names(scale)
        assert "a.good" in names
        assert "a.bad" not in names
        assert "b.y" in names
        stderr = capsys.readouterr().err
        assert "Warning: skipping status registration in goga_tool_a" in stderr

    def test_assemble_crashed_callback_warns_and_continues(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A callback that crashes after its first entry keeps that entry."""
        _install_package(monkeypatch, "goga_tool_a", _crashing_callback)
        _install_package(
            monkeypatch, "goga_tool_b", _registering({"name": "y", "filepath": "b/y.md", "before": "done"})
        )
        _packages(monkeypatch, "goga_tool_a", "goga_tool_b")

        scale = assemble_status_scale()

        names = _names(scale)
        assert "a.first" in names
        assert "b.y" in names
        stderr = capsys.readouterr().err
        assert "Warning: skipping status registration in goga_tool_a" in stderr
        assert "boom" in stderr


def _crashing_callback(statuses: Any) -> None:
    """Register one entry, then crash like a broken third-party callback."""
    statuses.register("first", "a/first.md", after="planned")
    raise TypeError("boom")
