from __future__ import annotations

import importlib
import types
from unittest import mock

import click
from click.testing import CliRunner
from goga.commands.tool import tool


class TestFacadeAccessible:
    def test_tool_facade_accessible(self) -> None:
        """The tool symbol is importable from goga.commands.tool."""
        assert tool is not None


class TestToolIsClickCommand:
    def test_tool_is_click_command(self) -> None:
        """The tool object is a click.BaseCommand instance."""
        assert isinstance(tool, click.Command)


class TestToolHasNameArgument:
    def test_tool_has_name_argument(self) -> None:
        """The tool command has a 'name' argument."""
        param_names = [p.name for p in tool.params]
        assert "name" in param_names


class TestToolSuccessfulInvocation:
    def test_tool_successful_invocation(self) -> None:
        """Calling tool with a valid package invokes its main with extra args."""
        captured: list[list[str]] = []

        dummy = types.ModuleType("goga_tool_example")
        dummy.main = captured.append  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["example", "arg1", "--flag", "value"])

        assert result.exit_code == 0
        assert captured == [["arg1", "--flag", "value"]]


class TestToolWithNoArgs:
    def test_tool_with_no_args(self) -> None:
        """Calling tool with no extra args invokes main with an empty list."""
        captured: list[list[str]] = []

        dummy = types.ModuleType("goga_tool_empty")
        dummy.main = captured.append  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["empty"])

        assert result.exit_code == 0
        assert captured == [[]]


class TestToolPackageNotFound:
    def test_tool_package_not_found(self) -> None:
        """Missing tool package shows a 'not found' error message."""
        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", side_effect=ModuleNotFoundError("goga_tool_nonexistent")):
            result = runner.invoke(tool, ["nonexistent"])

        assert result.exit_code != 0
        assert "goga_tool_nonexistent" in result.output
        assert "not found" in result.output.lower()


class TestToolNoMainFunction:
    def test_tool_no_main_function(self) -> None:
        """Tool package without a 'main' function shows an error message."""
        dummy = types.ModuleType("goga_tool_nomain")
        # Intentionally no 'main' attribute

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(tool, ["nomain"])

        assert result.exit_code != 0
        assert "goga_tool_nomain" in result.output
        assert "main" in result.output


class TestToolHelpMessage:
    def test_tool_help_message(self) -> None:
        """The --help flag shows usage info with NAME header."""
        runner = CliRunner()
        result = runner.invoke(tool, ["--help"])

        assert result.exit_code == 0
        assert "NAME" in result.output
