from __future__ import annotations

import importlib
import types
from unittest import mock

from click.testing import CliRunner
from goga.ast import AST
from goga.cli import app

# Resolve the inner `tool.py` submodule via importlib. The facade `goga.commands.tool`
# re-exports the click Command `tool`, which shadows the submodule attribute in the
# package `__dict__`. On Python 3.10 `mock.patch("goga.commands.tool.tool.AST")` resolves
# the dotted path through sequential `getattr`, finds the Command where it expects the
# submodule, and raises `AttributeError`. Holding a direct reference to the module makes
# `mock.patch.object` work uniformly across Python versions.
tool_module = importlib.import_module("goga.commands.tool.tool")


class TestToolRegisteredInApp:
    def test_tool_registered_in_app(self) -> None:
        """The 'tool' subcommand is listed in app's help output."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "tool" in result.output


class TestToolInvocationThroughApp:
    def test_tool_invocation_through_app(self) -> None:
        """End-to-end: invoking app tool <name> <args> reaches module.main."""
        captured: list[list[str]] = []

        dummy = types.ModuleType("goga_tool_example")

        def _main(argv: list[str]) -> None:
            captured.append(argv)

        dummy.main = _main  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(app, ["tool", "example", "arg1"])

        assert result.exit_code == 0
        assert captured == [["arg1"]]


class TestToolNotFoundThroughApp:
    def test_tool_not_found_through_app(self) -> None:
        """End-to-end: missing tool package via app shows 'not found' error."""
        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", side_effect=ModuleNotFoundError("goga_tool_nonexistent")):
            result = runner.invoke(app, ["tool", "nonexistent"])

        assert result.exit_code != 0
        assert "goga_tool_nonexistent" in result.output
        assert "not found" in result.output.lower()


class TestAstInjectionThroughApp:
    def test_ast_injection_through_app(self, tmp_path, monkeypatch) -> None:
        """End-to-end through app: main(argv, *, ast) receives argv plus the loaded AST."""
        (tmp_path / "CODEMANIFEST").write_text('Usages: {}\nAnnotations: ""\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        captured: dict[str, object] = {}

        def main(argv, *, ast):
            captured["argv"] = argv
            captured["ast"] = ast

        dummy = types.ModuleType("goga_tool_asttool")
        dummy.main = main  # type: ignore[attr-defined]

        runner = CliRunner()
        with mock.patch.object(importlib, "import_module", return_value=dummy):
            result = runner.invoke(app, ["tool", "asttool", "--flag", "value"])

        assert result.exit_code == 0
        assert captured["argv"] == ["--flag", "value"]
        assert isinstance(captured["ast"], AST)
        # Verify .load() actually ran: a fresh AST has an empty tree.
        assert len(captured["ast"].tree) >= 1


class TestNoAstInjectionThroughApp:
    def test_no_ast_injection_through_app(self) -> None:
        """End-to-end through app: a minimal main(argv) never triggers AST construction."""
        captured: list[list[str]] = []
        dummy = types.ModuleType("goga_tool_min")
        dummy.main = captured.append  # type: ignore[attr-defined]

        runner = CliRunner()
        with (
            mock.patch.object(tool_module, "AST") as mock_ast,
            mock.patch.object(importlib, "import_module", return_value=dummy),
        ):
            result = runner.invoke(app, ["tool", "min", "a"])

        assert result.exit_code == 0
        mock_ast.assert_not_called()
