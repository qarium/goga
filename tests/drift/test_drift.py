"""Contract and logic tests for the ``drift`` entry routine of ``goga/drift``.

Routine under test (declared in ``goga/drift/CODEMANIFEST`` with
``location: drift.py``):

- ``drift(cells, max_depth, depends_on) -> list[DriftEntry]`` — produce the
  complete views, compare them, and scope the entries to the filtered views.

The scenarios plant real projects on ``tmp_path`` (cwd pinned by the shared
``_isolate_cwd`` fixture) and run both producers for real — no mocks; the
producer errors propagate through the routine under test.
"""

from __future__ import annotations

import inspect
import typing
from pathlib import Path

import pytest
from goga.drift import DriftEntry, drift

from tests.drift.conftest import (
    _plant_four_kinds,
    _plant_healthy_plus,
    _plant_locationless,
    _plant_nested_depth,
    _snapshot_tree,
    _write_config,
)


def _kinds(report: list[DriftEntry]) -> list[tuple[str, str, list[str] | None]]:
    """Project the report onto the comparable (kind, cell, types) tuples."""
    return [(entry.kind, entry.cell, entry.types) for entry in report]


class TestDriftRoutine:
    """Facade and call contract of the entry routine."""

    def test_drift_importable_from_facade(self) -> None:
        """``drift`` is importable from the drift cell facade."""
        assert callable(drift)

    def test_facade_all_exposes_the_four_names(self) -> None:
        """The facade ``__all__`` exposes exactly the four sorted names."""
        import goga.drift

        assert goga.drift.__all__ == ["DriftEntry", "compare_views", "drift", "scope_entries"]

    def test_drift_has_correct_signature(self) -> None:
        """``drift`` declares the three family filter parameters."""
        sig = inspect.signature(drift)
        params = list(sig.parameters.keys())

        assert params == ["cells", "max_depth", "depends_on"]

    def test_drift_signature_defaults(self) -> None:
        """The contract defaults — no filter arguments required."""
        sig = inspect.signature(drift)

        assert sig.parameters["cells"].default == []
        assert sig.parameters["max_depth"].default is None
        assert sig.parameters["depends_on"].default == []

    def test_drift_param_and_return_types(self) -> None:
        """``drift`` types the three filters and the report it returns."""
        hints = typing.get_type_hints(drift)

        assert hints["cells"] == list[str]
        assert hints["max_depth"] == int | None
        assert hints["depends_on"] == list[str]
        assert hints["return"] == list[DriftEntry]


class TestDriftReport:
    """Design scenarios: the planted-project drift runs."""

    def test_drift_reports_planted_discrepancies_all_four_kinds(self, tmp_path: Path) -> None:
        """The four-kinds project yields exactly one entry per discrepancy direction."""
        _plant_four_kinds(tmp_path)

        report = drift([], None, [])

        assert _kinds(report) == [
            ("codegraph_only", "extra", None),
            ("schema_only", "ghost", None),
            ("codegraph_only", "mix", ["helper2"]),
            ("schema_only", "mix", ["stale"]),
        ]

    def test_drift_cells_filter_scopes_report_only(self, tmp_path: Path) -> None:
        """A cells filter keeps only the matching entry — the comparison stays complete."""
        _plant_four_kinds(tmp_path)

        report = drift(["ghost"], None, [])

        assert _kinds(report) == [("schema_only", "ghost", None)]

    def test_drift_depends_on_asymmetry_never_fabricates_entries(self, tmp_path: Path) -> None:
        """An import-only dependency surfaces no fabricated cell-level entry."""
        _plant_healthy_plus(tmp_path)

        report = drift([], None, ["lib"])

        assert report == []

    def test_drift_max_depth_scopes_report(self, tmp_path: Path) -> None:
        """A nested drift entry survives the unlimited run and dies at depth 0."""
        _plant_nested_depth(tmp_path)

        assert _kinds(drift([], None, [])) == [("schema_only", "a/b", ["stale"])]
        assert drift([], 0, []) == []

    def test_drift_deterministic_and_read_only(self, tmp_path: Path) -> None:
        """Two consecutive runs are identical and the project tree stays unchanged."""
        _plant_four_kinds(tmp_path)
        before = _snapshot_tree(tmp_path)

        first = drift([], None, [])
        second = drift([], None, [])

        assert first == second
        assert _snapshot_tree(tmp_path) == before


class TestDriftFailures:
    """Design scenarios: the producer failures propagate uncaught."""

    def test_drift_propagates_ast_parse_error(self, tmp_path: Path) -> None:
        """A rule-violating manifest surfaces the AST parse gate through the routine."""
        _plant_locationless(tmp_path)

        with pytest.raises(ValueError, match="AST parsing failed with 1 error"):
            drift([], None, [])

    def test_drift_propagates_unsupported_language_error(self, tmp_path: Path) -> None:
        """A configured language outside the whitelist surfaces the producer ValueError."""
        _write_config(tmp_path, language="rust")

        with pytest.raises(ValueError, match="unsupported language"):
            drift([], None, [])
