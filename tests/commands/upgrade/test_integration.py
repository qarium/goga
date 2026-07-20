from __future__ import annotations

import importlib
from pathlib import Path
from unittest import mock

from click.testing import CliRunner
from goga.cli import app

_upgrade_module = importlib.import_module("goga.commands.upgrade.upgrade")


def _pip_result(returncode: int = 0) -> mock.MagicMock:
    result = mock.MagicMock()
    result.returncode = returncode
    return result


class TestUpgradeCliIntegration:
    """End-to-end CLI tests for ``goga upgrade``.

    These drive the root Click group via ``CliRunner`` so they exercise the CLI
    registration → ``_upgrade`` → delegation boundary wiring. The activation
    routine itself (``resync_registered_agents``) is mocked at the upgrade-module
    boundary here; the routine's internal behaviour and the cross-cell
    ``connect()`` wiring are covered by the routine-level and feature-wide
    integration suites respectively.
    """

    def test_upgrade_cli_command_registered(self) -> None:
        """``goga upgrade --help`` exits 0 and lists all three options."""
        result = CliRunner().invoke(app, ["upgrade", "--help"])
        assert result.exit_code == 0
        assert "--sudo" in result.output
        assert "--user" in result.output
        assert "--tools" in result.output

    def test_upgrade_cli_delegates_to_resync_after_pip_success(self, tmp_path: Path) -> None:
        """Successful pip → ``goga upgrade`` delegates activation to the routine with the resolved home."""
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["upgrade"])
        assert result.exit_code == 0
        mock_resync.assert_called_once_with(tmp_path / ".goga")

    def test_upgrade_cli_resync_outcome_propagates_as_exit_code(self, tmp_path: Path) -> None:
        """The delegated re-sync outcome flows through ``ctx.exit`` as the CLI exit code."""
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=4),
        ):
            result = CliRunner().invoke(app, ["upgrade"])
        assert result.exit_code == 4

    def test_upgrade_cli_sudo_user_combination(self, tmp_path: Path) -> None:
        """``--sudo --user alice --tools`` prefixes sudo, resolves alice's home, appends goga_tool_*."""
        pw = mock.MagicMock()
        pw.pw_dir = str(tmp_path)
        with (
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module.pwd, "getpwnam", return_value=pw),
            mock.patch.object(
                _upgrade_module.importlib.metadata,
                "packages_distributions",
                return_value={"goga_tool_x": ["goga-tool-x"]},
            ),
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["upgrade", "--sudo", "--user", "alice", "--tools"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["sudo", "--preserve-env=HOME"]
        # pip resolves by distribution name (the value), not module name (the key).
        assert "goga-tool-x" in cmd
        assert "goga_tool_x" not in cmd
