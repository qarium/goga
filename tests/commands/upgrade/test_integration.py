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

    def test_upgrade_cli_help_lists_line_flags(self) -> None:
        """``goga upgrade --help`` exits 0 and lists all five options including the line flags."""
        result = CliRunner().invoke(app, ["upgrade", "--help"])
        assert result.exit_code == 0
        assert "--sudo" in result.output
        assert "--user" in result.output
        assert "--tools" in result.output
        assert "--patch" in result.output
        assert "--minor" in result.output

    def test_upgrade_cli_patch_end_to_end(self, tmp_path: Path) -> None:
        """``--patch`` reads the installed base, constrains argv to the minor line, and re-syncs."""
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value="1.2.3"),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["upgrade", "--patch"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert "goga~=1.2.0" in cmd
        mock_resync.assert_called_once_with(tmp_path / ".goga")

    def test_upgrade_cli_minor_end_to_end(self, tmp_path: Path) -> None:
        """``--minor`` constrains argv to the major line and re-syncs the resolved home."""
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value="1.2.3"),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["upgrade", "--minor"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert "goga~=1.0" in cmd
        mock_resync.assert_called_once_with(tmp_path / ".goga")

    def test_upgrade_cli_mutex_rejected(self) -> None:
        """``--patch --minor`` exits 1 with a clean error before pip or re-sync run."""
        with (
            mock.patch.object(_upgrade_module.subprocess, "run") as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["upgrade", "--patch", "--minor"])
        assert result.exit_code == 1
        assert "mutually exclusive" in result.output
        mock_run.assert_not_called()
        mock_resync.assert_not_called()

    def test_upgrade_cli_undeterminable_base_rejected(self) -> None:
        """An unreadable installed base exits 1 with a clean error — no fallback, no pip."""
        with (
            mock.patch.object(
                _upgrade_module.importlib.metadata,
                "version",
                side_effect=importlib.metadata.PackageNotFoundError("goga"),
            ),
            mock.patch.object(_upgrade_module.subprocess, "run") as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["upgrade", "--minor"])
        assert result.exit_code == 1
        assert "cannot determine the installed goga version" in result.output
        mock_run.assert_not_called()
        mock_resync.assert_not_called()

    def test_upgrade_cli_none_base_rejected(self) -> None:
        """A broken dist-info (``version() -> None``) exits 1 with a clean error — no traceback, no pip."""
        with (
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value=None),
            mock.patch.object(_upgrade_module.subprocess, "run") as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["upgrade", "--minor"])
        assert result.exit_code == 1
        assert "cannot determine the installed goga version" in result.output
        mock_run.assert_not_called()
        mock_resync.assert_not_called()

    def test_upgrade_cli_unresolvable_line_rejected(self) -> None:
        """A readable base without a minor segment exits 1 under ``--patch`` — no invented line, no pip."""
        with (
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value="1"),
            mock.patch.object(_upgrade_module.subprocess, "run") as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["upgrade", "--patch"])
        assert result.exit_code == 1
        assert "cannot resolve the version line" in result.output
        assert "no minor segment" in result.output
        mock_run.assert_not_called()
        mock_resync.assert_not_called()

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
