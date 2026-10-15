"""Contract and logic tests for the ``drift`` CLI command of ``goga/commands/drift``.

Command under test (declared in ``goga/commands/drift/CODEMANIFEST`` with
``location: drift.py``):

- ``drift(cells, max_depth, depends_on)`` — click wrapper delegating to
  ``drift_logic`` of ``goga/drift``; JSON report on stdout, the three-outcome
  exit contract 0/1/2, failures as clean stderr messages with exit 2.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.commands import drift as drift_facade
from goga.commands.drift import drift as drift_source
from goga.commands.drift.drift import _project_entry
from goga.drift import drift as drift_logic

from tests.drift.conftest import (
    _plant_four_kinds,
    _plant_healthy_plus,
    _plant_locationless,
    _plant_nested_depth,
    _plant_stale_importer,
    _write_config,
    _write_package,
)


@pytest.fixture(autouse=True)
def _empty_package_environment(empty_package_environment) -> None:
    """Pin the package environment empty for every test of this module."""


def _run_drift(*args: str):
    runner = CliRunner()

    return runner.invoke(app, ["drift", *args])


class TestDriftCommand:
    """Facade, click surface, and registration contract of the wrapper."""

    def test_drift_importable_from_cell(self) -> None:
        """``drift`` is importable from ``goga.commands.drift``."""
        assert isinstance(drift_source, click.Command)

    def test_drift_importable_from_commands_facade(self) -> None:
        """``drift`` is importable from the ``goga.commands`` facade."""
        assert drift_facade is drift_source

    def test_drift_registered_on_app(self) -> None:
        """The root group carries the command under the name ``drift``."""
        assert any(cmd.name == "drift" for cmd in app.commands.values())


class TestDriftCliReport:
    """Design scenarios: the planted-project CLI runs and the exit contract."""

    def test_drift_cli_discrepancies_exit_1_and_print_full_report(self, tmp_path: Path) -> None:
        """The four-kinds project prints the four-entry report and exits 1."""
        _plant_four_kinds(tmp_path)

        result = _run_drift()

        assert result.exit_code == 1
        assert json.loads(result.output) == [
            {"cell": "extra", "kind": "codegraph_only"},
            {"cell": "ghost", "kind": "schema_only"},
            {"cell": "mix", "kind": "codegraph_only", "types": ["helper2"]},
            {"cell": "mix", "kind": "schema_only", "types": ["stale"]},
        ]
        assert result.output.endswith("\n")

    def test_drift_cli_agreement_exit_0_prints_empty_list(self, tmp_path: Path) -> None:
        """A healthy project prints the empty report and exits 0."""
        _write_config(tmp_path)
        _write_package(tmp_path, "pkg", "def run() -> None:\n    return\n", ["run"])

        result = _run_drift()

        assert result.exit_code == 0
        assert json.loads(result.output) == []

    def test_drift_cli_uninitialized_project_exit_2_clean_stderr(self, tmp_path: Path) -> None:
        """A project without .goga/config.yml exits 2 with clean stdout and a stderr reason."""
        _plant_four_kinds(tmp_path)
        (tmp_path / ".goga" / "config.yml").unlink()

        result = _run_drift()

        assert result.exit_code == 2
        assert result.stdout == ""
        assert ".goga/config.yml" in (result.stderr or "")

    def test_drift_cli_ast_error_exit_2(self, tmp_path: Path) -> None:
        """A rule-violating manifest exits 2 with the parse failure on stderr."""
        _plant_locationless(tmp_path)

        result = _run_drift()

        assert result.exit_code == 2
        assert result.stdout == ""
        assert "AST parsing failed" in (result.stderr or "")

    def test_drift_cli_repeated_runs_byte_identical(self, tmp_path: Path) -> None:
        """Two consecutive invocations print byte-identical reports, both exit 1."""
        _plant_four_kinds(tmp_path)

        first = _run_drift()
        second = _run_drift()

        assert first.exit_code == 1
        assert second.exit_code == 1
        assert first.output == second.output

    def test_drift_cli_cells_filter_scopes_report(self, tmp_path: Path) -> None:
        """A CELLS filter keeps only the matching entry — exit 1 with the scoped report."""
        _plant_four_kinds(tmp_path)

        result = _run_drift("ghost")

        assert result.exit_code == 1
        assert json.loads(result.output) == [{"cell": "ghost", "kind": "schema_only"}]

    def test_drift_cli_max_depth_zero_scopes_report(self, tmp_path: Path) -> None:
        """``--max-depth 0`` over the nested project empties the report — exit 0."""
        _plant_nested_depth(tmp_path)

        result = _run_drift("--max-depth", "0")

        assert result.exit_code == 0
        assert json.loads(result.output) == []

    def test_drift_cli_depends_on_scopes_report(self, tmp_path: Path) -> None:
        """``--depends-on`` keeps the surviving discrepancy of the dependent cell."""
        _plant_stale_importer(tmp_path)

        result = _run_drift("--depends-on", "lib")

        assert result.exit_code == 1
        assert json.loads(result.output) == [{"cell": "mix", "kind": "schema_only", "types": ["stale"]}]

    def test_drift_cli_gate_veto_exit_2_clean_stderr(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A vetoed schema gate exits 2 with the reason on stderr — stdout stays clean."""
        _plant_four_kinds(tmp_path)

        def register_alpha(hooks: object) -> None:
            def veto_alpha(context) -> None:
                context.veto("cell mix: broken")

            hooks.subscribe("schema", "validate_schema", "veto_alpha", veto_alpha)  # type: ignore[attr-defined]

        pin_package_environment({"goga_tool_alpha": ["alpha-dist"]})
        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)

        result = _run_drift()

        assert result.exit_code == 2
        assert result.stdout == ""
        assert "schema validation failed:" in (result.stderr or "")

    def test_drift_cli_help_documents_surface_report_and_statuses(self) -> None:
        """``--help`` documents the surface, the report fields, and the three statuses."""
        result = _run_drift("--help")

        assert result.exit_code == 0
        assert "CELLS" in result.output
        assert "--max-depth" in result.output
        assert "--depends-on" in result.output
        assert "kind" in result.output
        assert "cell" in result.output
        assert "types" in result.output
        assert "schema_only" in result.output
        assert "codegraph_only" in result.output
        assert "0" in result.output
        assert "1" in result.output
        assert "2" in result.output

    def test_drift_cli_help_documents_the_tools_row_and_post_amendment_grading(self) -> None:
        """``--help`` documents the conditional ``tools`` row and the post-amendment grading."""
        result = _run_drift("--help")

        assert result.exit_code == 0
        assert "tools" in result.output
        assert "present iff at least one tool contributed" in result.output
        assert "never affects the exit code" in result.output
        assert "post-amendment entry list" in result.output
        assert "a cleared report grades 0, a tool-added entry grades 1" in result.output
        assert "amendment hard" in result.output
        assert "codegraph veto" in result.output
        assert "import failure" in result.output


# --- Checkpoint delivery (the CLI half of the drift hooks zone) ---


def _install_tool(pin_package_environment, install_tool_package, tool, register):
    """Pin the environment to one tool and install its facade carrying ``register``.

    Args:
        pin_package_environment: the boundary-pinning fixture factory.
        install_tool_package: the package-installing fixture factory.
        tool: the canonical tool identity — the package installs as
            ``goga_tool_{tool}`` and the derived identity is ``tool`` itself.
        register: the facade callback subscribing the tool's hooks.

    Returns:
        The boundary mock — the installed-packages read of the run.
    """
    boundary = pin_package_environment({f"goga_tool_{tool}": [f"{tool}-dist"]})

    install_tool_package(f"goga_tool_{tool}", register_hooks=register)
    return boundary


class TestDriftCheckpointDelivery:
    """The conditional ``tools`` key of the projection and the checkpoint failure conversion."""

    def test_drift_cli_projects_contributed_tools_on_every_entry(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A contributing entry tool places ``tools`` on every entry; the base fields stand."""
        _plant_four_kinds(tmp_path)

        def ticket(context) -> None:
            context.contribute({"ticket": "GOGA-9"})

        def register(hooks: object) -> None:
            hooks.subscribe("drift", "amend_entry", "ticket", ticket)  # type: ignore[attr-defined]

        _install_tool(pin_package_environment, install_tool_package, "watch", register)

        result = _run_drift()

        assert result.exit_code == 1
        doc = json.loads(result.output)
        assert all(entry["tools"] == {"watch": {"ticket": "GOGA-9"}} for entry in doc)
        assert [(entry["kind"], entry["cell"]) for entry in doc] == [
            ("codegraph_only", "extra"),
            ("schema_only", "ghost"),
            ("codegraph_only", "mix"),
            ("schema_only", "mix"),
        ]
        assert doc[2]["types"] == ["helper2"]
        assert doc[3]["types"] == ["stale"]
        assert json.dumps(doc, indent=4, sort_keys=True, ensure_ascii=False) + "\n" == result.output

    def test_drift_command_grades_the_post_amendment_list(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A tool clearing the report grades 0; a tool adding an entry grades 1."""
        _plant_four_kinds(tmp_path)

        def clear(context) -> None:
            context.adjust([])

        def register_clear(hooks: object) -> None:
            hooks.subscribe("drift", "amend_report", "clear", clear)  # type: ignore[attr-defined]

        _install_tool(pin_package_environment, install_tool_package, "watch", register_clear)

        cleared = _run_drift()

        assert cleared.exit_code == 0
        assert json.loads(cleared.output) == []

        healthy = tmp_path / "healthy"
        healthy.mkdir()
        _plant_healthy_plus(healthy)
        monkeypatch.chdir(healthy)

        def add(context) -> None:
            context.adjust([{"kind": "codegraph_only", "cell": "added", "types": ["thing"]}])

        def register_add(hooks: object) -> None:
            hooks.subscribe("drift", "amend_report", "add", add)  # type: ignore[attr-defined]

        _install_tool(pin_package_environment, install_tool_package, "alpha", register_add)

        added = _run_drift()

        assert added.exit_code == 1
        assert json.loads(added.output) == [{"cell": "added", "kind": "codegraph_only", "types": ["thing"]}]

    def test_drift_command_exit_2_on_amendment_failure(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A raising amend_report hook is a clean stderr failure with exit 2."""
        _plant_four_kinds(tmp_path)

        def boom(context) -> None:
            raise RuntimeError("kaboom")

        def register(hooks: object) -> None:
            hooks.subscribe("drift", "amend_report", "boom", boom)  # type: ignore[attr-defined]

        _install_tool(pin_package_environment, install_tool_package, "alpha", register)

        result = _run_drift()

        assert result.exit_code == 2
        assert result.stdout == ""
        assert "hook boom of tool alpha failed on drift.amend_report: kaboom" in (result.stderr or "")
        assert "Traceback" not in result.output

    def test_drift_in_run_codegraph_veto_surfaces_as_exit_2(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An in-run codegraph gate veto crashes the run — the clean exit-2 envelope."""
        _plant_four_kinds(tmp_path)

        def vetoer(context) -> None:
            context.veto("shape broken")

        def register(hooks: object) -> None:
            hooks.subscribe("codegraph", "validate_graph", "vetoer", vetoer)  # type: ignore[attr-defined]

        _install_tool(pin_package_environment, install_tool_package, "gate", register)

        result = _run_drift()

        assert result.exit_code == 2
        assert result.stdout == ""
        assert "codegraph validation failed:" in (result.stderr or "")
        assert "Traceback" not in result.output


# --- Routine↔CLI agreement and family determinism (the Task-16 integration net) ---


class TestDriftRoutineCliAgreement:
    """The routine's returned report and the CLI's printed document are one view."""

    def test_drift_routine_and_cli_agree_entry_for_entry_with_tool_overlays(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The direct call and the CLI agree on every entry; the exit code follows the returned list."""
        _plant_four_kinds(tmp_path)

        def score(context) -> None:
            context.contribute({"score": 3})

        def register(hooks: object) -> None:
            hooks.subscribe("drift", "amend_entry", "score", score)  # type: ignore[attr-defined]

        _install_tool(pin_package_environment, install_tool_package, "watch", register)

        report = drift_logic([], None, [])

        result = _run_drift()

        assert result.exit_code == (1 if report else 0)
        assert [_project_entry(entry) for entry in report] == json.loads(result.output)
        assert [(entry["kind"], entry["cell"]) for entry in json.loads(result.output)] == [
            ("codegraph_only", "extra"),
            ("schema_only", "ghost"),
            ("codegraph_only", "mix"),
            ("schema_only", "mix"),
        ]
        assert all(entry["tools"] == {"watch": {"score": 3}} for entry in json.loads(result.output))

    def test_drift_cli_repeated_runs_with_tools_byte_identical(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two fresh invocations with a contributing tool echo byte-identical reports, ``sort_keys`` included."""
        _plant_four_kinds(tmp_path)

        def ticket(context) -> None:
            context.contribute({"ticket": "GOGA-9"})

        def register(hooks: object) -> None:
            hooks.subscribe("drift", "amend_entry", "ticket", ticket)  # type: ignore[attr-defined]

        _install_tool(pin_package_environment, install_tool_package, "watch", register)

        first = _run_drift()
        second = _run_drift()

        assert first.exit_code == 1
        assert second.exit_code == 1
        assert second.output == first.output
        assert json.dumps(json.loads(first.output), indent=4, sort_keys=True, ensure_ascii=False) + "\n" == first.output
