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
    _plant_root_manifest,
    _plant_stale_importer,
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


class TestDriftCheckpointContract:
    """Contract: the run is observed and amended — silence changes nothing."""

    def test_drift_returns_the_four_kinds_report_with_empty_tools_under_a_silent_tool(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A subscribed-but-silent tool leaves the report and every tools area unchanged."""
        _plant_four_kinds(tmp_path)
        pin_package_environment({"goga_tool_watch": ["watch-dist"]})

        def register(hooks: object) -> None:
            def watch(context: object) -> None:
                return None

            hooks.subscribe("drift", "amend_report", "watch", watch)  # type: ignore[attr-defined]
            hooks.subscribe("drift", "amend_entry", "watch", watch)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_watch", register_hooks=register)

        report = drift([], None, [])

        assert _kinds(report) == [
            ("codegraph_only", "extra", None),
            ("schema_only", "ghost", None),
            ("codegraph_only", "mix", ["helper2"]),
            ("schema_only", "mix", ["stale"]),
        ]
        assert all(entry.tools == {} for entry in report)


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

    def test_drift_depends_on_keeps_surviving_entry(self, tmp_path: Path) -> None:
        """A depends_on filter keeps the discrepancy of the dependent cell and drops the rest."""
        _plant_stale_importer(tmp_path)

        assert _kinds(drift([], None, ["lib"])) == [("schema_only", "mix", ["stale"])]
        assert drift([], None, ["unrelated"]) == []

    def test_drift_max_depth_scopes_report(self, tmp_path: Path) -> None:
        """A nested drift entry survives the unlimited run and dies at depth 0."""
        _plant_nested_depth(tmp_path)

        assert _kinds(drift([], None, [])) == [("schema_only", "a/b", ["stale"])]
        assert drift([], 0, []) == []

    def test_drift_root_manifest_reports_dot_schema_only_cell(self, tmp_path: Path) -> None:
        """A root CODEMANIFEST without root code yields the ``.`` schema-only entry."""
        _plant_root_manifest(tmp_path)

        report = drift([], None, [])

        assert _kinds(report) == [
            ("schema_only", ".", None),
            ("codegraph_only", "pkg", None),
        ]

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

    def test_drift_propagates_schema_gate_veto(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A vetoed schema validation gate surfaces through the routine unchanged."""
        _plant_four_kinds(tmp_path)

        def register_alpha(hooks: object) -> None:
            def veto_alpha(context) -> None:
                context.veto("cell mix: broken")

            hooks.subscribe("schema", "validate_schema", "veto_alpha", veto_alpha)  # type: ignore[attr-defined]

        pin_package_environment({"goga_tool_alpha": ["alpha-dist"]})
        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)

        with pytest.raises(ValueError, match="schema validation failed"):
            drift([], None, [])


class TestDriftCheckpointOrder:
    """Design scenarios: the fixed run ordering and the terminal facts."""

    def test_drift_runs_the_full_checkpoint_order(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The recorded order starts at the start moment and ends at the completion moment."""
        _plant_four_kinds(tmp_path)
        pin_package_environment({"goga_tool_watch": ["watch-dist"]})
        calls: list[tuple[str, str]] = []

        def register(hooks: object) -> None:
            def on_started(context: object) -> None:
                calls.append(("run_started", ""))

            def on_report(context: object) -> None:
                calls.append(("amend_report", ""))

            def on_entry(context: object) -> None:
                calls.append(("amend_entry", f"{context.entry.kind} {context.entry.cell}"))

            def on_completed(context: object) -> None:
                calls.append(("run_completed", context.completion.outcome.value))

            hooks.subscribe("drift", "run_started", "on_started", on_started)  # type: ignore[attr-defined]
            hooks.subscribe("drift", "amend_report", "on_report", on_report)  # type: ignore[attr-defined]
            hooks.subscribe("drift", "amend_entry", "on_entry", on_entry)  # type: ignore[attr-defined]
            hooks.subscribe("drift", "run_completed", "on_completed", on_completed)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_watch", register_hooks=register)

        report = drift([], None, [])

        actions = [action for action, _ in calls]

        assert actions[0] == "run_started"
        assert actions[-1] == "run_completed"
        assert calls[-1] == ("run_completed", "finished")
        assert actions.index("amend_report") < min(
            index for index, action in enumerate(actions) if action == "amend_entry"
        )
        assert actions.count("amend_entry") == len(report) == 4
        assert _kinds(report) == [
            ("codegraph_only", "extra", None),
            ("schema_only", "ghost", None),
            ("codegraph_only", "mix", ["helper2"]),
            ("schema_only", "mix", ["stale"]),
        ]

    def test_drift_completion_carries_the_final_report_on_finished_runs(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The finished completion carries the final report; every returned entry carries its overlay."""
        _plant_four_kinds(tmp_path)
        pin_package_environment({"goga_tool_watch": ["watch-dist"]})
        recorded: tuple[list[tuple[str, str]], str, str] | None = None

        def register(hooks: object) -> None:
            def ticket(context: object) -> None:
                context.contribute({"ticket": "GOGA-9"})

            def on_completed(context: object) -> None:
                nonlocal recorded

                completion = context.completion
                recorded = (
                    [(entry.kind, entry.cell) for entry in completion.report or []],
                    completion.outcome.value,
                    completion.reason,
                )

            hooks.subscribe("drift", "amend_entry", "ticket", ticket)  # type: ignore[attr-defined]
            hooks.subscribe("drift", "run_completed", "on_completed", on_completed)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_watch", register_hooks=register)

        report = drift([], None, [])

        assert recorded is not None

        stage, outcome, reason = recorded

        assert stage == [(entry.kind, entry.cell) for entry in report]
        assert outcome == "finished"
        assert reason == ""
        assert all(entry.tools == {"watch": {"ticket": "GOGA-9"}} for entry in report)


class TestDriftFailurePaths:
    """Design scenarios: the crashed completion fires and the original failure re-raises."""

    def test_drift_producer_failure_emits_crashed_completion_and_reraises(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An uninitialized project crashes before the report — the completion carries None and the reason."""
        pin_package_environment({"goga_tool_watch": ["watch-dist"]})
        recorded: list[tuple[object, str, str]] = []

        def register(hooks: object) -> None:
            def on_completed(context: object) -> None:
                completion = context.completion
                recorded.append((completion.report, completion.outcome.value, completion.reason))

            hooks.subscribe("drift", "run_completed", "on_completed", on_completed)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_watch", register_hooks=register)

        with pytest.raises(FileNotFoundError):
            drift([], None, [])

        assert len(recorded) == 1

        report, outcome, reason = recorded[0]

        assert report is None
        assert outcome == "crashed"
        assert ".goga/config.yml" in reason

    @pytest.mark.parametrize("raising_action", ["amend_report", "amend_entry"])
    def test_drift_amendment_failure_carries_the_scoped_pre_amendment_stage(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
        raising_action: str,
    ) -> None:
        """An amendment failure carries the scoped stage with empty tools; the checkpoint error re-raises."""
        _plant_four_kinds(tmp_path)
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"]})
        recorded: list[tuple[object, str]] = []

        def register(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("kaboom")

            def on_completed(context: object) -> None:
                completion = context.completion
                recorded.append((completion.report, completion.outcome.value))

            hooks.subscribe("drift", raising_action, "boom", boom)  # type: ignore[attr-defined]
            hooks.subscribe("drift", "run_completed", "on_completed", on_completed)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register)

        with pytest.raises(ValueError, match=rf"failed on drift\.{raising_action}"):
            drift([], None, [])

        assert len(recorded) == 1

        stage, outcome = recorded[0]

        assert outcome == "crashed"
        assert [(entry.kind, entry.cell, entry.tools) for entry in stage] == [
            ("codegraph_only", "extra", {}),
            ("schema_only", "ghost", {}),
            ("codegraph_only", "mix", {}),
            ("schema_only", "mix", {}),
        ]


class TestDriftCheckpointEdges:
    """Design scenarios: the empty scoped list, the import failure, and determinism."""

    def test_amend_report_empty_scoped_list_still_delivers(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An agreeing project still passes the report amendment — a tool-added entry settles and is enriched."""
        _plant_healthy_plus(tmp_path)
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"]})
        entry_calls: list[str] = []

        def register(hooks: object) -> None:
            def add(context: object) -> None:
                context.adjust([{"kind": "codegraph_only", "cell": "added", "types": ["thing"]}])

            def watch(context: object) -> None:
                entry_calls.append(context.entry.cell)

            hooks.subscribe("drift", "amend_report", "add", add)  # type: ignore[attr-defined]
            hooks.subscribe("drift", "amend_entry", "watch", watch)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register)

        report = drift([], None, [])

        assert _kinds(report) == [("codegraph_only", "added", ["thing"])]
        assert entry_calls == ["added"]

    def test_amend_entry_empty_settled_list_fires_nothing(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A clean scoped report with no adjusters delivers no entry amendment."""
        _plant_healthy_plus(tmp_path)
        pin_package_environment({"goga_tool_watch": ["watch-dist"]})
        entry_calls: list[str] = []

        def register(hooks: object) -> None:
            def watch(context: object) -> None:
                entry_calls.append(context.entry.cell)

            hooks.subscribe("drift", "amend_entry", "watch", watch)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_watch", register_hooks=register)

        assert drift([], None, []) == []
        assert entry_calls == []

    def test_drift_start_moment_import_failure_propagates_without_completion(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A broken tool package kills the start moment before the failure wrap — no completion fires."""
        _plant_four_kinds(tmp_path)

        package_dir = tmp_path / "goga_tool_broken"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("import goga_missing_dependency\n", encoding="utf-8")
        monkeypatch.syspath_prepend(tmp_path)

        pin_package_environment({"goga_tool_broken": ["broken-dist"], "goga_tool_watch": ["watch-dist"]})
        calls: list[str] = []

        def register(hooks: object) -> None:
            def on_completed(context: object) -> None:
                calls.append("run_completed")

            hooks.subscribe("drift", "run_completed", "on_completed", on_completed)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_watch", register_hooks=register)

        with pytest.raises(ImportError, match=r"package goga_tool_broken failed to import"):
            drift([], None, [])

        assert calls == []

    def test_drift_determinism_with_tools_installed(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two runs with a contributing tool produce identical reports including the tools mappings."""
        _plant_four_kinds(tmp_path)
        pin_package_environment({"goga_tool_watch": ["watch-dist"]})

        def register(hooks: object) -> None:
            def ticket(context: object) -> None:
                context.contribute({"ticket": "GOGA-9"})

            hooks.subscribe("drift", "amend_entry", "ticket", ticket)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_watch", register_hooks=register)

        first = drift([], None, [])
        second = drift([], None, [])

        assert first == second
        assert all(entry.tools == {"watch": {"ticket": "GOGA-9"}} for entry in first)
