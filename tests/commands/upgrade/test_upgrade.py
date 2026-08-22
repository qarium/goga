from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from unittest import mock

import click
import pytest
import yaml
from goga.commands.upgrade import upgrade
from goga.commands.upgrade.upgrade import _upgrade

_upgrade_module = importlib.import_module("goga.commands.upgrade.upgrade")


def _pip_result(returncode: int = 0) -> mock.MagicMock:
    result = mock.MagicMock()
    result.returncode = returncode
    return result


def _write_registry(goga_home: Path, agents: dict[str, dict[str, bool]]) -> None:
    goga_home.mkdir(parents=True, exist_ok=True)
    (goga_home / "connect.yml").write_text(yaml.dump({"agents": agents}))


class TestUpgradeFacade:
    """Contract tests — verify the upgrade facade and Click command shape."""

    def test_upgrade_reads_host_version_via_single_reading_point(self) -> None:
        """The host version is read through the version cell's single reading
        point — the upgrade module binds the facade function object itself, so
        no second metadata-reading call site can reappear unnoticed."""
        facade = importlib.import_module("goga.version")
        assert _upgrade_module.host_goga_version is facade.host_goga_version

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

    def test_upgrade_has_five_options(self) -> None:
        names = {p.name for p in upgrade.params if isinstance(p, click.Option)}
        assert names == {"sudo", "user", "tools", "patch", "minor"}

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

    def test_upgrade_patch_is_flag(self) -> None:
        param = next(p for p in upgrade.params if p.name == "patch")
        assert isinstance(param, click.Option)
        assert param.is_flag
        assert param.default is False

    def test_upgrade_minor_is_flag(self) -> None:
        param = next(p for p in upgrade.params if p.name == "minor")
        assert isinstance(param, click.Option)
        assert param.is_flag
        assert param.default is False

    def test_upgrade_routine_signature(self) -> None:
        sig = inspect.signature(_upgrade)
        params = sig.parameters
        assert list(params) == ["use_sudo", "target_user", "include_tools", "patch_line", "minor_line"]
        assert params["use_sudo"].default is False
        assert params["target_user"].default is None
        assert params["include_tools"].default is False
        assert params["patch_line"].default is False
        assert params["minor_line"].default is False
        assert sig.return_annotation is int or sig.return_annotation == "int"


class TestUpgradeLogicPositive:
    """Positive behavioral scenarios (pip argv composition, version lines, pwd resolution)."""

    def test_upgrade_sudo_prepends_preserve_env_home(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0),
        ):
            rc = _upgrade(use_sudo=True)
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["sudo", "--preserve-env=HOME"]

    def test_upgrade_patch_line_composes_minor_line_specifier(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value="1.2.3"),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            rc = _upgrade(patch_line=True)
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        assert "goga~=1.2.0" in cmd
        # The line specifier replaces the bare identifier — no bare "goga" element.
        assert "goga" not in cmd
        mock_resync.assert_called_once()

    def test_upgrade_minor_line_composes_major_line_specifier(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value="1.2.3"),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0),
        ):
            rc = _upgrade(minor_line=True)
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        # --minor does not inherit the minor-line form of --patch: same base, wider line.
        assert "goga~=1.0" in cmd
        assert "goga~=1.2.0" not in cmd

    def test_upgrade_flagless_reads_no_metadata_and_argv_unchanged(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.importlib.metadata, "version") as mock_version,
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0),
        ):
            rc = _upgrade()
        assert rc == 0
        # No line flag → the installed version is never read (byte-identical argv).
        mock_version.assert_not_called()
        cmd = mock_run.call_args[0][0]
        assert cmd == [sys.executable, "-m", "pip", "install", "goga", "-U"]

    def test_upgrade_patch_with_tools_constrains_only_goga(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value="1.2.3"),
            mock.patch.object(
                _upgrade_module.importlib.metadata,
                "packages_distributions",
                return_value={"goga_tool_x": ["goga-tool-x"]},
            ),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0),
        ):
            rc = _upgrade(include_tools=True, patch_line=True)
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        assert "goga~=1.2.0" in cmd
        assert "goga-tool-x" in cmd
        # Exactly one constrained identifier: the specifier never leaks onto goga_tool_*.
        assert sum("~=" in a or "==" in a for a in cmd) == 1

    def test_upgrade_patch_with_sudo_preserves_home_and_specifier(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value="1.2.3"),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0),
        ):
            rc = _upgrade(use_sudo=True, patch_line=True)
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["sudo", "--preserve-env=HOME"]
        assert "goga~=1.2.0" in cmd

    def test_upgrade_patch_with_user_combination(self, tmp_path: Path) -> None:
        pw = mock.MagicMock()
        pw.pw_dir = str(tmp_path)
        with (
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value="1.2.3"),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module.pwd, "getpwnam", return_value=pw) as mock_getpwnam,
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            rc = _upgrade(target_user="alice", patch_line=True)
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        assert "goga~=1.2.0" in cmd
        mock_getpwnam.assert_called_once_with("alice")
        mock_resync.assert_called_once_with(tmp_path / ".goga")

    def test_upgrade_target_user_resolves_via_pwd(self, tmp_path: Path) -> None:
        pw = mock.MagicMock()
        pw.pw_dir = str(tmp_path)
        with (
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module.pwd, "getpwnam", return_value=pw) as mock_getpwnam,
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            rc = _upgrade(target_user="alice")
        assert rc == 0
        mock_getpwnam.assert_called_once_with("alice")
        # The pwd-resolved goga_home is forwarded verbatim to the delegated routine;
        # the default-path delegation is covered separately, so this test must keep
        # the --user (pwd) path under coverage.
        mock_resync.assert_called_once_with(Path(pw.pw_dir) / ".goga")


class TestUpgradeLogicNegative:
    """Negative behavioral scenarios (line-flag rejections, pip failure short-circuits)."""

    def test_upgrade_pip_failure_propagates_exit_code(self) -> None:
        with (
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result(1)),
            mock.patch.object(_upgrade_module, "resync_registered_agents") as mock_resync,
        ):
            rc = _upgrade()
        assert rc == 1
        mock_resync.assert_not_called()

    def test_upgrade_mutex_flags_raise_before_any_action(self) -> None:
        with (
            mock.patch.object(_upgrade_module.importlib.metadata, "version") as mock_version,
            mock.patch.object(_upgrade_module.subprocess, "run") as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents") as mock_resync,
            pytest.raises(click.ClickException, match="mutually exclusive"),
        ):
            _upgrade(patch_line=True, minor_line=True)
        # The mutex fires before the metadata read — nothing ran at all.
        mock_version.assert_not_called()
        mock_run.assert_not_called()
        mock_resync.assert_not_called()

    def test_upgrade_undeterminable_base_raises_before_pip(self) -> None:
        with (
            mock.patch.object(
                _upgrade_module.importlib.metadata,
                "version",
                side_effect=importlib.metadata.PackageNotFoundError("goga"),
            ),
            mock.patch.object(_upgrade_module.subprocess, "run") as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents") as mock_resync,
            pytest.raises(click.ClickException, match="cannot determine the installed goga version"),
        ):
            _upgrade(patch_line=True)
        # An unreadable installed base is a hard fail — no fallback to latest, no pip.
        mock_run.assert_not_called()
        mock_resync.assert_not_called()

    def test_upgrade_none_base_raises_before_pip(self) -> None:
        with (
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value=None),
            mock.patch.object(_upgrade_module.subprocess, "run") as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents") as mock_resync,
            pytest.raises(click.ClickException, match="cannot determine the installed goga version"),
        ):
            _upgrade(patch_line=True)
        # A broken dist-info yields None instead of raising — same hard fail as
        # the missing-package case: no fallback to latest, no pip, no TypeError.
        mock_run.assert_not_called()
        mock_resync.assert_not_called()

    def test_upgrade_unresolvable_line_raises_before_pip(self) -> None:
        with (
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value="1"),
            mock.patch.object(_upgrade_module.subprocess, "run") as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents") as mock_resync,
            pytest.raises(click.ClickException, match=r"cannot resolve the version line: .* no minor segment"),
        ):
            _upgrade(patch_line=True)
        # A readable base whose line cannot be resolved is a hard fail — a
        # major-only installed version has no minor line, and none is invented.
        mock_run.assert_not_called()
        mock_resync.assert_not_called()


class TestUpgradeLogicEdge:
    """Edge-case behavioral scenarios (delegation wiring, unknown user, rich installed bases)."""

    def test_upgrade_include_tools_appends_tool_packages(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(
                _upgrade_module.importlib.metadata,
                "packages_distributions",
                return_value={"goga_tool_x": ["goga-tool-x"]},
            ),
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0),
        ):
            rc = _upgrade(include_tools=True)
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        # pip resolves by distribution name (the value), not module name (the key).
        assert "goga-tool-x" in cmd
        assert "goga_tool_x" not in cmd

    def test_upgrade_rich_installed_base_truncated(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.importlib.metadata, "version", return_value="1.2.1.dev0"),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0),
        ):
            rc = _upgrade(patch_line=True)
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        # A dev install still resolves to its release line (1.2), never rejected.
        assert "goga~=1.2.0" in cmd

    def test_upgrade_delegates_to_resync_with_resolved_goga_home(self, tmp_path: Path) -> None:
        _write_registry(tmp_path / ".goga", {"claude": {"force_overwrite": False}})
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            rc = _upgrade()
        assert rc == 0
        # Default path: goga_home is Path.home() / ".goga", forwarded to the routine.
        mock_resync.assert_called_once_with(tmp_path / ".goga")

    def test_upgrade_unknown_user_returns_nonzero_no_resync(self) -> None:
        with (
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module.pwd, "getpwnam", side_effect=KeyError("unknown")),
            mock.patch.object(_upgrade_module, "resync_registered_agents") as mock_resync,
        ):
            rc = _upgrade(target_user="unknown")
        assert rc != 0
        mock_resync.assert_not_called()

    def test_upgrade_pwd_lookup_oserror_returns_nonzero_no_resync(self) -> None:
        # OSError (NIS/LDAP backend failure) from pwd.getpwnam is the other arm of
        # _resolve_goga_home's except tuple; it must surface a non-zero exit
        # without crashing and without invoking activation.
        with (
            mock.patch.object(_upgrade_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_upgrade_module.pwd, "getpwnam", side_effect=OSError("nis failure")),
            mock.patch.object(_upgrade_module, "resync_registered_agents") as mock_resync,
        ):
            rc = _upgrade(target_user="ghost")
        assert rc != 0
        mock_resync.assert_not_called()
