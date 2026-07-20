from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.cli import app

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


class TestInstallCliIntegration:
    """End-to-end CLI tests for ``goga install``.

    Drive the root Click group via ``CliRunner`` so they exercise the full
    Cell 3 (``goga/cli.py``) -> Cell 1 (``goga/commands/install/install.py``)
    wiring: click group dispatch, option parsing (``--sudo`` / ``--version``),
    argv composition, and exit-code propagation through ``ctx.exit``. The pip
    boundary is mocked so no real ``subprocess.run`` happens.
    """

    def test_install_cli_help_lists_options(self) -> None:
        """``goga install --help`` exits 0 and lists both options and the NAME argument."""
        result = CliRunner().invoke(app, ["install", "--help"])
        assert result.exit_code == 0
        assert "--sudo" in result.output
        assert "--version" in result.output
        # Click uppercases the argument metavar (NAME) in the usage line and
        # emits an ``Arguments:`` section; either marker confirms the required
        # positional argument is declared.
        assert "NAME" in result.output.upper() or "Arguments" in result.output

    def test_install_cli_plain_dispatch(self) -> None:
        """``goga install foo`` composes the canonical argv and exits with pip's returncode."""
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "foo"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv == [sys.executable, "-m", "pip", "install", "goga-tool-foo", "-U"]

    def test_install_cli_with_sudo_and_version(self) -> None:
        """``goga install foo --sudo --version 1.2.3`` prefixes sudo and grammar-resolves the version."""
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "foo", "--sudo", "--version", "1.2.3"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv[:3] == ["sudo", "--preserve-env=HOME", sys.executable]
        assert "goga-tool-foo==1.2.3" in argv

    def test_install_cli_propagates_pip_failure(self) -> None:
        """A non-zero pip returncode propagates through ``ctx.exit`` (no CalledProcessError)."""
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(1)):
            result = CliRunner().invoke(app, ["install", "foo"])
        assert result.exit_code == 1


class TestInstallEndToEndPaths:
    """End-to-end paths exercising cross-entity wiring (install -> resolve_version
    -> load_config -> subprocess.run) plus regressions the bulk/empty rewrite
    introduces: optional ``name``, no ``~/.goga`` writes, and empty-path isolation
    from ``--sudo``. The pip boundary is mocked so no real install runs and the
    real home dir (redirected to ``tmp_path/.pytest_home`` by the autouse
    ``_isolate_home`` fixture) is observable for side-effect assertions.
    """

    def test_install_no_name_runs_bulk_or_empty_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Regression: ``goga install`` without NAME no longer parse-errors.

        Previously ``name`` was a required argument, so ``["install"]`` exited 2
        with Click's "Missing argument" usage error. With ``name`` optional the
        empty path runs instead: a config without ``tools:`` prints
        ``Nothing to install`` and exits 0 without invoking pip.
        """
        _write_config(tmp_path, "language: python\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        # Exit 0 (empty path), not 2 (Click usage error).
        assert result.exit_code == 0
        assert result.output.strip() == "Nothing to install"
        mock_run.assert_not_called()

    def test_install_single_path_empty_name_propagates_to_pip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``goga install ""`` drives the SINGLE path with ``pkg = "goga-tool-"``.

        An empty string is not ``None``, so Click dispatches it as a name: the
        version resolves to ``None`` (no specifier) and pip is handed the bare
        ``goga-tool-`` identifier. pip's non-zero returncode propagates as-is.
        """
        # An empty string must be passed verbatim through the shell-free CliRunner.
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(1)) as mock_run:
            result = CliRunner().invoke(app, ["install", ""])
        assert result.exit_code == 1
        assert mock_run.call_count == 1
        assert _pkgs_from_argv(mock_run.call_args[0][0]) == ["goga-tool-"]

    def test_install_no_resync_does_not_touch_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Single-path install writes nothing under ``~/.goga``.

        The install command installs a tool via pip; it never runs the
        connect/resync step that materializes ``~/.goga``. ``_isolate_home``
        redirects HOME to ``tmp_path/.pytest_home``, so the absence of a
        ``.goga`` directory there proves no home writes occurred.
        """
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()):
            CliRunner().invoke(app, ["install", "foo"])
        assert not (tmp_path / ".pytest_home" / ".goga").exists()

    def test_install_does_not_read_connect_yml_in_bulk_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bulk-path install does not create ``~/.goga/connect.yml``.

        Resolving ``cfg.tools`` and invoking pip must not trigger the connect
        step that writes ``connect.yml``. After a bulk install no such file
        exists under the isolated home.
        """
        _write_config(tmp_path, "language: python\ntools:\n  afm: 1.0.x\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()):
            CliRunner().invoke(app, ["install"])
        assert not (tmp_path / ".pytest_home" / ".goga" / "connect.yml").exists()

    def test_install_bulk_path_full_cross_entity_argv(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cross-entity: a real ``.goga/config.yml`` drives load_config ->
        resolve_version -> one ``subprocess.run`` with composed argv.

        Three tools, three grammar forms (minor x-range, latest, concrete),
        resolved in YAML insertion order into a single pip invocation.
        """
        _write_config(
            tmp_path,
            "language: python\ntools:\n  afm: 1.0.x\n  viewer: latest\n  go: 1.2.3\n",
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        assert mock_run.call_count == 1
        argv = mock_run.call_args[0][0]
        assert argv[:3] == [sys.executable, "-m", "pip"]
        assert argv[3] == "install"
        assert argv[-1] == "-U"
        assert _pkgs_from_argv(argv) == ["goga-tool-afm~=1.0.0", "goga-tool-viewer", "goga-tool-go==1.2.3"]

    def test_install_empty_path_with_sudo_still_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Edge: empty path + ``--sudo`` stays empty — sudo never materializes.

        With no ``tools:`` the empty branch fires before argv composition, so
        ``--sudo`` is never consulted and pip is never invoked.
        """
        _write_config(tmp_path, "language: python\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "--sudo"])
        assert result.exit_code == 0
        assert result.output.strip() == "Nothing to install"
        mock_run.assert_not_called()
