from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.commands.install import install

_install_module = importlib.import_module("goga.commands.install.install")


def _pip_result(returncode: int = 0) -> mock.MagicMock:
    result = mock.MagicMock()
    result.returncode = returncode
    return result


def _write_config(tmp_path: Path, body: str) -> Path:
    """Write ``.goga/config.yml`` under ``tmp_path`` and return its path."""
    config_dir = tmp_path / ".goga"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yml"
    config_file.write_text(body)
    return config_file


def _pkgs_from_argv(argv: list[str]) -> list[str]:
    """Slice the package identifiers out of a composed pip argv (between the
    ``install`` subcommand and the trailing ``-U``)."""
    return argv[argv.index("install") + 1 : -1]


class TestInstallFacade:
    """Contract tests — verify the install facade and Click command shape."""

    def test_install_importable_from_facade(self) -> None:
        assert install is not None

    def test_install_facade_all(self) -> None:
        # ``import ... as`` would resolve to the Click command re-exported into
        # ``goga.commands`` (shadowing the submodule), so access the package
        # module directly to assert its own ``__all__``. ``resolve_version`` is
        # also a declared routine of this cell, so it shares the facade.
        facade = importlib.import_module("goga.commands.install")
        assert "install" in facade.__all__

    def test_install_is_click_command(self) -> None:
        assert isinstance(install, click.Command)
        assert install.name == "install"

    def test_install_has_two_options(self) -> None:
        names = {p.name for p in install.params if isinstance(p, click.Option)}
        assert {"sudo", "version"} <= names

    def test_install_argument_name_present(self) -> None:
        arg = next(p for p in install.params if isinstance(p, click.Argument) and p.name == "name")
        assert arg.required is False

    def test_install_sudo_is_flag(self) -> None:
        param = next(p for p in install.params if p.name == "sudo")
        assert isinstance(param, click.Option)
        assert param.is_flag
        assert param.default is False

    def test_install_version_default_none(self) -> None:
        param = next(p for p in install.params if p.name == "version")
        assert isinstance(param, click.Option)
        assert param.default is None


class TestInstallLogicPositive:
    """Positive behavioral scenarios — single / bulk / empty argv composition."""

    def test_install_single_path_composes_argv(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "foo", "--version", "1.0.x"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv == [sys.executable, "-m", "pip", "install", "goga-tool-foo~=1.0.0", "-U"]
        assert mock_run.call_args.kwargs.get("check") is False

    def test_install_single_path_with_sudo_prefixes_preserve_env_home(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "foo", "--sudo"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv[:3] == ["sudo", "--preserve-env=HOME", sys.executable]
        assert argv[-1] == "-U"

    def test_install_bulk_path_one_pip_call_yaml_order(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_config(
            tmp_path,
            "language: python\n"
            "tools:\n"
            "  afm: 1.0.x\n"
            "  ralphex: 1.x\n"
            "  go: 1.0.1\n",
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        assert mock_run.call_count == 1
        argv = mock_run.call_args[0][0]
        assert _pkgs_from_argv(argv) == [
            "goga-tool-afm~=1.0.0",
            "goga-tool-ralphex~=1.0",
            "goga-tool-go==1.0.1",
        ]

    def test_install_bulk_path_with_sudo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_config(tmp_path, "language: python\ntools:\n  afm: 1.0.x\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "--sudo"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv[:3] == ["sudo", "--preserve-env=HOME", sys.executable]

    def test_install_bulk_path_latest_marker_yields_no_specifier(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(
            tmp_path,
            "language: python\n"
            "tools:\n"
            "  viewer: latest\n"
            "  afm: 1.0.x\n",
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert _pkgs_from_argv(argv) == ["goga-tool-viewer", "goga-tool-afm~=1.0.0"]

    def test_install_empty_path_prints_message_and_exits_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "language: python\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        assert result.output.strip() == "Nothing to install"
        mock_run.assert_not_called()

    def test_install_empty_path_with_empty_tools_mapping(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "language: python\ntools: {}\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        assert result.output.strip() == "Nothing to install"
        mock_run.assert_not_called()


class TestInstallLogicNegative:
    """Negative behavioral scenarios — grammar rejection and pip-failure paths."""

    def test_install_single_path_version_rejected_surfaces_click_exception(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "foo", "--version", "==1.0"])
        assert result.exit_code == 1
        mock_run.assert_not_called()

    def test_install_single_path_empty_version_string_rejected(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "foo", "--version", ""])
        assert result.exit_code == 1
        mock_run.assert_not_called()

    def test_install_bulk_path_version_rejected_in_tools_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(
            tmp_path,
            "language: python\n"
            "tools:\n"
            "  good: 1.0.x\n"
            "  bad: '==1.0'\n",
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 1
        mock_run.assert_not_called()

    def test_install_bulk_path_load_config_error_wrapped_in_click_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No .goga/config.yml in CWD → load_config raises FileNotFoundError → ClickException.
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 1
        mock_run.assert_not_called()

    def test_install_pip_failure_propagates_exit_code_single(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(1)):
            result = CliRunner().invoke(app, ["install", "foo"])
        assert result.exit_code == 1

    def test_install_pip_failure_propagates_exit_code_bulk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "language: python\ntools:\n  afm: 1.0.x\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(42)):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 42
