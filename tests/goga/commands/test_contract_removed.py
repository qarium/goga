"""Tests verifying the contract command has been removed and remaining commands work."""

from __future__ import annotations

import pathlib

from click.testing import CliRunner
from goga.cli import app


def test_no_contract_command_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["contract"])
    assert result.exit_code != 0
    assert "No such command" in result.output or "Error" in result.output


def test_no_contract_in_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "contract" not in result.output


def test_remaining_commands_still_work() -> None:
    runner = CliRunner()
    for command in ["linter", "build", "init", "schema"]:
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, f"Command '{command}' failed: {result.output}"


def test_comparator_directory_removed() -> None:
    assert not pathlib.Path("goga/comparator").exists()
    assert not pathlib.Path("tests/goga/comparator").exists()
