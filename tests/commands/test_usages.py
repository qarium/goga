"""Tests for the goga usages command group and its sync subcommand."""

from __future__ import annotations

from unittest import mock

import click
from click.testing import CliRunner
from goga.commands.usages import usages as usages_cli

# sync_logic is imported into the usages.py module as ``sync_logic``; patch it
# there so delegation tests do not touch the real domain orchestrator.
_logic = "goga.commands.usages.usages.sync_logic"


class TestContract:
    """Contract-level tests for the usages command group."""

    def test_usages_importable_from_facade(self) -> None:
        from goga.commands.usages import usages as facade_usages

        assert facade_usages is usages_cli

    def test_usages_is_click_group(self) -> None:
        assert isinstance(usages_cli, click.Group)

    def test_usages_sync_subcommand_registered(self) -> None:
        assert "sync" in usages_cli.commands

    def test_usages_sync_force_flag_contract(self) -> None:
        sync_cmd = usages_cli.commands["sync"]
        force_param = {p.name: p for p in sync_cmd.params}["force"]
        assert isinstance(force_param, click.Option)
        assert force_param.is_flag is True
        assert force_param.default is False


class TestLogic:
    """Logic-level tests for usages sync delegation."""

    def test_cli_usages_sync_delegates_and_propagates_exit(self) -> None:
        with mock.patch(_logic, return_value=1) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync"])

        mock_logic.assert_called_once_with(False)
        assert result.exit_code == 1

    def test_cli_usages_sync_long_force_flag_passes_true(self) -> None:
        with mock.patch(_logic, return_value=0) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync", "--force"])

        mock_logic.assert_called_once_with(True)
        assert result.exit_code == 0

    def test_cli_usages_sync_short_force_flag_passes_true(self) -> None:
        with mock.patch(_logic, return_value=0) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync", "-f"])

        mock_logic.assert_called_once_with(True)
        assert result.exit_code == 0

    def test_cli_usages_sync_config_error_converts_to_clickexception(self) -> None:
        with mock.patch(_logic, side_effect=ValueError("boom")):
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync"])

        assert result.exit_code != 0
        assert "boom" in result.output

    def test_cli_usages_sync_yaml_error_converts_to_clickexception(self) -> None:
        import yaml as yaml_mod

        with mock.patch(_logic, side_effect=yaml_mod.YAMLError("bad yaml")):
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync"])

        assert result.exit_code != 0
        assert "bad yaml" in result.output

    def test_cli_usages_help_lists_sync(self) -> None:
        runner = CliRunner()
        result = runner.invoke(usages_cli, ["--help"])
        assert result.exit_code == 0
        assert "sync" in result.output
