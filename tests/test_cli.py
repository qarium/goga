from __future__ import annotations

import inspect
import json
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest import mock

import click
import pytest
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

    def test_lint_command_registered(self) -> None:
        """The 'lint' command is registered on the app group."""
        assert "lint" in app.commands

    def test_build_command_registered(self) -> None:
        """The 'build' command is registered on the app group."""
        assert "build" in app.commands

    def test_connect_command_registered(self) -> None:
        """The 'connect' command is registered on the app group."""
        assert "connect" in app.commands

    def test_both_commands_registered(self) -> None:
        """Both 'lint' and 'build' commands are present in app.commands."""
        command_names = set(app.commands.keys())
        assert {"lint", "build"}.issubset(command_names)

    def test_upgrade_command_registered(self) -> None:
        """The 'upgrade' command is registered on the app group."""
        assert "upgrade" in app.commands


class TestHelpOutput:
    def test_help_exit_code_zero(self) -> None:
        """The --help flag on the app group exits with code 0."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_help_contains_lint(self) -> None:
        """The --help output lists the 'lint' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "lint" in result.output

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
        """The --help output contains both 'lint' and 'build'."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "lint" in result.output
        assert "build" in result.output

    def test_help_contains_upgrade(self) -> None:
        """The --help output lists the 'upgrade' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "upgrade" in result.output


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


class TestUpgradeHelpOutput:
    def test_upgrade_help_exit_code_zero(self) -> None:
        """The 'upgrade --help' subcommand exits with code 0."""
        runner = CliRunner()
        result = runner.invoke(app, ["upgrade", "--help"])
        assert result.exit_code == 0

    def test_upgrade_help_contains_options(self) -> None:
        """The 'upgrade --help' output shows the --sudo, --user, --tools options."""
        runner = CliRunner()
        result = runner.invoke(app, ["upgrade", "--help"])
        assert "--sudo" in result.output
        assert "--user" in result.output
        assert "--tools" in result.output


class TestVersionFlagContract:
    """Contract tests — the eager --version/-v flag on the root group."""

    def test_version_flag_prints_host_version_and_exits_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The --version flag prints the host version and exits with code 0."""
        monkeypatch.setattr("goga.cli.host_goga_version", lambda: "1.2.3")
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.output == "1.2.3\n"

    def test_version_option_listed_in_root_help(self) -> None:
        """The --version option appears in the root group help."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--version" in result.output

    def test_app_signature_unchanged_by_flag(self) -> None:
        """expose_value=False keeps the app() callback parameterless."""
        assert list(inspect.signature(app.callback).parameters) == []


class TestVersionFlagBehavior:
    """Logic tests — behavior of the eager --version/-v flag."""

    def test_app_version_flag_prints_host_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The --version flag echoes the bare host version string."""
        monkeypatch.setattr("goga.cli.host_goga_version", lambda: "1.2.3")
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.output == "1.2.3\n"

    def test_app_version_short_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The -v short spelling behaves exactly like --version."""
        monkeypatch.setattr("goga.cli.host_goga_version", lambda: "1.2.3")
        runner = CliRunner()
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert result.output == "1.2.3\n"

    def test_app_version_flag_metadata_failure_is_clean(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An undeterminable host version surfaces as a clean error, no traceback."""
        monkeypatch.setattr("goga.cli.host_goga_version", mock.Mock(side_effect=PackageNotFoundError("goga")))
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 1
        assert "cannot determine" in result.output
        assert "Traceback" not in result.output

    def test_app_subcommands_unaffected_by_version_flag(self) -> None:
        """The eager group flag never conflicts with subcommands or their options."""
        runner = CliRunner()

        root_help = runner.invoke(app, ["--help"])
        assert root_help.exit_code == 0
        assert "--version" in root_help.output

        build_help = runner.invoke(app, ["build", "--help"])
        assert build_help.exit_code == 0
        assert "--version" not in build_help.output

        install_help = runner.invoke(app, ["install", "--help"])
        assert install_help.exit_code == 0
        # install keeps its own value option of the same name — the group's
        # eager flag does not shadow it.
        assert "--version" in install_help.output


class TestSchemaLintCoexist:
    def test_cli_schema_lint_coexist(self) -> None:
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
                lint_result = runner.invoke(app, ["lint", "."])

            assert lint_result.exit_code in (0, 1)
