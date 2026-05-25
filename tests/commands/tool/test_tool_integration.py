from __future__ import annotations

import importlib
import types
from unittest import mock

from click.testing import CliRunner
from goga.cli import app


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
