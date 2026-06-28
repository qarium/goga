from __future__ import annotations

import importlib
from pathlib import Path
from unittest import mock

import yaml
from click.testing import CliRunner
from goga.cli import app

_upgrade_module = importlib.import_module("goga.commands.upgrade.upgrade")


def _pip_result(returncode: int = 0) -> mock.MagicMock:
    result = mock.MagicMock()
    result.returncode = returncode
    return result


def _connect_ok() -> mock.MagicMock:
    mock_connect = mock.MagicMock()
    mock_connect.return_value = 0
    return mock_connect


def _write_registry(goga_home: Path, agents: dict[str, dict[str, bool]]) -> None:
    goga_home.mkdir(parents=True, exist_ok=True)
    (goga_home / "connect.yml").write_text(yaml.dump({"agents": agents}))


class TestUpgradeCliIntegration:
    """End-to-end CLI tests for ``goga upgrade`` (design-doc traces T9, T11).

    These drive the root Click group via ``CliRunner`` so they exercise the full
    Cell 2 → Cell 1 wiring: CLI registration, pip invocation, ``connect.yml``
    registry read, and per-agent ``connect()`` re-sync.
    """

    def test_upgrade_cli_command_registered(self) -> None:
        """T11 — ``goga upgrade --help`` exits 0 and lists all three options."""
        result = CliRunner().invoke(app, ["upgrade", "--help"])
        assert result.exit_code == 0
        assert "--sudo" in result.output
        assert "--user" in result.output
        assert "--tools" in result.output

    def test_upgrade_cli_invokes_connect_per_agent(self, tmp_path: Path) -> None:
        """Pre-write a 2-agent registry; ``goga upgrade`` re-syncs each with its own force_overwrite."""
        _write_registry(
            tmp_path / ".goga",
            {"claude": {"force_overwrite": False}, "codex": {"force_overwrite": True}},
        )
        mock_connect = _connect_ok()
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module, "connect", new=mock_connect),
        ):
            result = CliRunner().invoke(app, ["upgrade"])
        assert result.exit_code == 0
        assert mock_connect.call_count == 2
        assert mock_connect.call_args_list == [
            mock.call(agents=["claude"], force_overwrite=False),
            mock.call(agents=["codex"], force_overwrite=True),
        ]

    def test_upgrade_cli_missing_connect_yml_exits_zero(self, tmp_path: Path) -> None:
        """T9 — no ``connect.yml`` present; ``goga upgrade`` exits 0 after a successful pip."""
        mock_connect = mock.MagicMock()
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module, "connect", new=mock_connect),
        ):
            result = CliRunner().invoke(app, ["upgrade"])
        assert result.exit_code == 0
        mock_connect.assert_not_called()

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
            mock.patch.object(_upgrade_module, "connect", new=_connect_ok()),
        ):
            result = CliRunner().invoke(app, ["upgrade", "--sudo", "--user", "alice", "--tools"])
        assert result.exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["sudo", "--preserve-env=HOME"]
        assert "goga_tool_x" in cmd
