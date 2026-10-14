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

from tests.drift.conftest import _plant_four_kinds, _plant_locationless, _write_config, _write_package


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
