"""Tests verifying the contract command has been removed and remaining commands work."""

from __future__ import annotations

import pathlib
import re

from click.testing import CliRunner
from goga.cli import app


def test_no_contract_command_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["contract"])
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_no_contract_command_in_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    command_lines = re.findall(r"^\s{2,}(\S+)", result.output, re.MULTILINE)
    assert "contract" not in command_lines


def test_remaining_commands_still_work() -> None:
    runner = CliRunner()
    for command in ["linter", "build", "init", "schema"]:
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, f"Command '{command}' failed: {result.output}"


def test_comparator_directory_removed() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    assert not (root / "goga" / "comparator").exists()
    assert not (root / "tests" / "goga" / "comparator").exists()
