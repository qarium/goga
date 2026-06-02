from __future__ import annotations

import json
from pathlib import Path

import click
from click.testing import CliRunner
from goga import app
from goga.cli import app as cli_app

from tests.conftest import cwd as _cwd

SIMPLE_MANIFEST = """\
Usages: {}

Annotations: ""

---
"TestEntity()":
  location: entity.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Integration test cell
"""


class TestFacadeAvailability:
    def test_import_app_from_goga(self) -> None:
        """The app symbol is importable from the goga package."""
        assert app is not None

    def test_import_app_from_cli_module(self) -> None:
        """The app symbol is also available from goga.cli."""
        assert cli_app is not None

    def test_both_imports_reference_same_object(self) -> None:
        """goga.app and goga.cli.app reference the same object."""
        assert app is cli_app


class TestApiShape:
    def test_app_is_click_group(self) -> None:
        """The app object is a click Group instance."""
        assert isinstance(app, click.Group)

    def test_app_is_not_plain_command(self) -> None:
        """The app object is not a plain click Command (it is a Group)."""
        # Group is a subclass of Command, so isinstance(app, Command) is True,
        # but we specifically want it to be a Group.
        assert type(app) is click.Group or isinstance(app, click.Group)


class TestRegisteredCommands:
    def test_commands_dict_exists(self) -> None:
        """The app has a commands dictionary."""
        assert hasattr(app, "commands")
        assert isinstance(app.commands, dict)

    def test_linter_command_registered(self) -> None:
        """The 'linter' command is registered on the app group."""
        assert "linter" in app.commands

    def test_build_command_registered(self) -> None:
        """The 'build' command is registered on the app group."""
        assert "build" in app.commands

    def test_connect_command_registered(self) -> None:
        """The 'connect' command is registered on the app group."""
        assert "connect" in app.commands

    def test_both_commands_registered(self) -> None:
        """Both 'linter' and 'build' commands are present in app.commands."""
        command_names = set(app.commands.keys())
        assert {"linter", "build"}.issubset(command_names)


class TestHelpOutput:
    def test_help_exit_code_zero(self) -> None:
        """The --help flag on the app group exits with code 0."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_help_contains_linter(self) -> None:
        """The --help output lists the 'linter' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "linter" in result.output

    def test_help_contains_build(self) -> None:
        """The --help output lists the 'build' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "build" in result.output

    def test_help_contains_connect(self) -> None:
        """The --help output lists the 'connect' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "connect" in result.output

    def test_help_contains_both_commands(self) -> None:
        """The --help output contains both 'linter' and 'build'."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "linter" in result.output
        assert "build" in result.output


class TestBuildHelpOutput:
    def test_build_help_exit_code_zero(self) -> None:
        """The 'build --help' subcommand exits with code 0."""
        runner = CliRunner()
        result = runner.invoke(app, ["build", "--help"])
        assert result.exit_code == 0

    def test_build_help_contains_options(self) -> None:
        """The 'build --help' output shows build command options."""
        runner = CliRunner()
        result = runner.invoke(app, ["build", "--help"])
        assert "--dry-run" in result.output

    def test_build_help_contains_plan_argument(self) -> None:
        """The 'build --help' output shows the plan argument."""
        runner = CliRunner()
        result = runner.invoke(app, ["build", "--help"])
        assert "plan" in result.output.lower()


class TestSchemaLinterCoexist:
    def test_cli_schema_linter_coexist(self) -> None:
        runner = CliRunner()

        with runner.isolated_filesystem() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "CODEMANIFEST").write_text(SIMPLE_MANIFEST, encoding="utf-8")

            with _cwd(tmp_path):
                schema_result = runner.invoke(app, ["schema"])

            assert schema_result.exit_code == 0
            schema_data = json.loads(schema_result.output)
            assert isinstance(schema_data, list)

            with _cwd(tmp_path):
                linter_result = runner.invoke(app, ["linter", "."])

            assert linter_result.exit_code in (0, 1)
