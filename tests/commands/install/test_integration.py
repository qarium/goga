from __future__ import annotations

import importlib
import sys
from unittest import mock

from click.testing import CliRunner
from goga.cli import app

_install_module = importlib.import_module("goga.commands.install.install")


def _pip_result(returncode: int = 0) -> mock.MagicMock:
    result = mock.MagicMock()
    result.returncode = returncode
    return result


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
