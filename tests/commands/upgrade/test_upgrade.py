from __future__ import annotations

import importlib
import inspect
import os
from pathlib import Path
from unittest import mock

import click
import yaml
from goga.commands.upgrade import upgrade
from goga.commands.upgrade.upgrade import _upgrade

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


class TestUpgradeFacade:
    """Contract tests — verify the upgrade facade and Click command shape."""

    def test_upgrade_importable_from_facade(self) -> None:
        assert upgrade is not None

    def test_upgrade_facade_all(self) -> None:
        # ``import ... as`` would resolve to the Click command re-exported into
        # ``goga.commands`` (shadowing the submodule), so access the package
        # module directly to assert its own ``__all__``.
        facade = importlib.import_module("goga.commands.upgrade")
        assert facade.__all__ == ["upgrade"]

    def test_upgrade_is_click_command(self) -> None:
        assert isinstance(upgrade, click.Command)
        assert upgrade.name == "upgrade"

    def test_upgrade_has_three_options(self) -> None:
        names = {p.name for p in upgrade.params}
        assert {"sudo", "user", "tools"} <= names

    def test_upgrade_sudo_is_flag(self) -> None:
        param = next(p for p in upgrade.params if p.name == "sudo")
        assert isinstance(param, click.Option)
        assert param.is_flag
        assert param.default is False

    def test_upgrade_tools_is_flag(self) -> None:
        param = next(p for p in upgrade.params if p.name == "tools")
        assert isinstance(param, click.Option)
        assert param.is_flag
        assert param.default is False

    def test_upgrade_user_is_string(self) -> None:
        param = next(p for p in upgrade.params if p.name == "user")
        assert isinstance(param, click.Option)
        assert not param.is_flag
        assert param.default is None

    def test_upgrade_routine_signature(self) -> None:
        sig = inspect.signature(_upgrade)
        params = sig.parameters
        assert list(params) == ["use_sudo", "target_user", "include_tools"]
        assert params["use_sudo"].default is False
        assert params["target_user"].default is None
        assert params["include_tools"].default is False
        assert sig.return_annotation is int or sig.return_annotation == "int"


class TestUpgradeLogicPositive:
    """Positive behavioral scenarios (design-doc traces T3, T4, T5)."""

    def test_upgrade_reads_per_agent_force_overwrite(self, tmp_path: Path) -> None:
        _write_registry(tmp_path / ".goga", {"claude": {"force_overwrite": False}, "codex": {"force_overwrite": True}})
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module, "connect", new=_connect_ok()) as mock_connect,
        ):
            rc = _upgrade()
        assert rc == 0
        assert mock_connect.call_args_list == [
            mock.call(agents=["claude"], force_overwrite=False),
            mock.call(agents=["codex"], force_overwrite=True),
        ]

    def test_upgrade_sudo_prepends_preserve_env_home(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module, "connect", new=_connect_ok()),
        ):
            rc = _upgrade(use_sudo=True)
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["sudo", "--preserve-env=HOME"]

    def test_upgrade_target_user_resolves_via_pwd(self, tmp_path: Path) -> None:
        _write_registry(tmp_path / ".goga", {"claude": {"force_overwrite": False}})
        pw = mock.MagicMock()
        pw.pw_dir = str(tmp_path)
        with (
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module.pwd, "getpwnam", return_value=pw) as mock_getpwnam,
            mock.patch.object(_upgrade_module, "connect", new=_connect_ok()) as mock_connect,
        ):
            rc = _upgrade(target_user="alice")
        assert rc == 0
        mock_getpwnam.assert_called_once_with("alice")
        mock_connect.assert_called_once_with(agents=["claude"], force_overwrite=False)

    def test_upgrade_target_user_redirects_resync_to_target_home(self, tmp_path: Path) -> None:
        """``--user`` must point ``$HOME`` at the target user during the re-sync.

        ``connect()`` resolves its central ``~/.goga`` root and each agent's target
        dir via ``Path.home()`` (which reads ``$HOME``). So a ``--user`` re-sync
        only targets the other user if ``$HOME`` is redirected there while
        ``connect()`` runs — otherwise it silently installs into the current
        user's home. HOME must also be restored afterwards.
        """
        alice_home = tmp_path / "alice"
        _write_registry(alice_home / ".goga", {"claude": {"force_overwrite": False}})
        pw = mock.MagicMock()
        pw.pw_dir = str(alice_home)

        seen: dict[str, Path] = {}
        original_home = os.environ.get("HOME")

        def fake_connect(agents: list[str], force_overwrite: bool = False) -> int:
            seen["home"] = Path.home()
            return 0

        with (
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module.pwd, "getpwnam", return_value=pw),
            mock.patch.object(_upgrade_module, "connect", new=fake_connect),
        ):
            rc = _upgrade(target_user="alice")
        assert rc == 0
        assert seen["home"] == Path(pw.pw_dir)
        assert os.environ.get("HOME") == original_home


class TestUpgradeLogicNegative:
    """Negative behavioral scenarios (design-doc traces T6, T7)."""

    def test_upgrade_pip_failure_propagates_exit_code(self) -> None:
        with (
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result(1)),
            mock.patch.object(_upgrade_module, "connect") as mock_connect,
        ):
            rc = _upgrade()
        assert rc == 1
        mock_connect.assert_not_called()

    def test_upgrade_aggregates_failures_continues_remaining_agents(self, tmp_path: Path) -> None:
        _write_registry(tmp_path / ".goga", {"claude": {"force_overwrite": False}, "codex": {"force_overwrite": False}})
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module, "connect", side_effect=[1, 0]) as mock_connect,
        ):
            rc = _upgrade()
        assert rc == 1
        assert mock_connect.call_count == 2


class TestUpgradeLogicEdge:
    """Edge-case behavioral scenarios (design-doc traces T9 and others)."""

    def test_upgrade_missing_connect_yml_exits_zero(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module, "connect") as mock_connect,
        ):
            rc = _upgrade()
        assert rc == 0
        mock_connect.assert_not_called()

    def test_upgrade_include_tools_appends_tool_packages(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(
                _upgrade_module.importlib.metadata,
                "packages_distributions",
                return_value={"goga_tool_x": ["goga-tool-x"]},
            ),
        ):
            rc = _upgrade(include_tools=True)
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        # pip resolves by distribution name (the value), not module name (the key).
        assert "goga-tool-x" in cmd
        assert "goga_tool_x" not in cmd

    def test_upgrade_unknown_user_returns_nonzero(self) -> None:
        with (
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module.pwd, "getpwnam", side_effect=KeyError("unknown")),
            mock.patch.object(_upgrade_module, "connect") as mock_connect,
        ):
            rc = _upgrade(target_user="unknown")
        assert rc != 0
        mock_connect.assert_not_called()

    def test_upgrade_malformed_registry_returns_nonzero(self, tmp_path: Path) -> None:
        goga_home = tmp_path / ".goga"
        goga_home.mkdir(parents=True)
        (goga_home / "connect.yml").write_text("agents: [unclosed")
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module, "connect") as mock_connect,
        ):
            rc = _upgrade()
        assert rc != 0
        mock_connect.assert_not_called()
