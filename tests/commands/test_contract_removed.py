"""Tests verifying renamed commands are properly registered and old names are gone."""

from __future__ import annotations

import pathlib
import re

from click.testing import CliRunner
from goga.cli import app


def test_no_init_command_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_no_compare_command_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["compare"])
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_no_init_command_in_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    command_lines = re.findall(r"^\s{2,}(\S+)", result.output, re.MULTILINE)
    assert "init" not in command_lines
    assert "compare" not in command_lines


def test_new_commands_work() -> None:
    runner = CliRunner()
    for command in ["linter", "build", "install", "schema", "contract"]:
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, f"Command '{command}' failed: {result.output}"


def test_comparator_directory_removed() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    assert not (root / "goga" / "comparator").exists()
    assert not (root / "tests" / "goga" / "comparator").exists()
