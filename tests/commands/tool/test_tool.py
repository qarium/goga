from __future__ import annotations

import importlib
import inspect
import sys
import types
from unittest import mock

import click
from click.testing import CliRunner
from goga.ast import AST
from goga.commands.tool import build_injections, tool


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


class TestBuildInjectionsFacadeExported:
    def test_build_injections_facade_exported(self) -> None:
        """build_injections is importable from the facade, callable, and in __all__."""
        # The module-level `from goga.commands.tool import build_injections, tool`
        # above exercises the facade export path; verify the symbols landed.
        assert callable(build_injections)

        # The goga.commands package shadows the `tool` submodule attribute with the
        # command, so reach the package module via sys.modules for its __all__.
        facade = sys.modules["goga.commands.tool"]
        assert "build_injections" in facade.__all__

        # Signature shape: exactly one parameter named 'main'.
        sig = inspect.signature(build_injections)
        assert list(sig.parameters) == ["main"]


class TestBuildInjectionsPositive:
    def test_build_injections_returns_ast_when_main_declares_ast(self, tmp_path, monkeypatch) -> None:
        """When main declares keyword-only ast, the loaded AST is injected."""
        (tmp_path / "CODEMANIFEST").write_text('Usages: {}\nAnnotations: ""\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        def f(argv, *, ast):
            return ast

        result = build_injections(f)

        assert result.keys() == {"ast"}
        assert isinstance(result["ast"], AST)


class TestBuildInjectionsNegative:
    def test_other_named_parameter_does_not_trigger_ast(self) -> None:
        """A keyword-only param not named 'ast' does not build the AST."""

        def f(argv, *, config): ...

        with mock.patch("goga.commands.tool.tool.AST") as mock_ast:
            result = build_injections(f)

        assert result == {}
        mock_ast.assert_not_called()


class TestBuildInjectionsEdge:
    def test_positional_only_ast_is_not_supplied(self) -> None:
        """A positional-only 'ast' is keyword-incapable and is not injected."""
        # The `/` marks parameters before it as positional-only; placing `ast`
        # before the marker makes it POSITIONAL_ONLY (keyword-incapable).

        def f(argv, ast, /): ...

        assert inspect.signature(f).parameters["ast"].kind == inspect.Parameter.POSITIONAL_ONLY

        with mock.patch("goga.commands.tool.tool.AST") as mock_ast:
            result = build_injections(f)

        assert result == {}
        mock_ast.assert_not_called()

    def test_positional_or_keyword_ast_is_supplied(self, tmp_path, monkeypatch) -> None:
        """A positional-or-keyword 'ast' is keyword-capable and is injected."""
        (tmp_path / "CODEMANIFEST").write_text('Usages: {}\nAnnotations: ""\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        def f(argv, ast=None): ...

        result = build_injections(f)

        assert result.keys() == {"ast"}
        assert isinstance(result["ast"], AST)
