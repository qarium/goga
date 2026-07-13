from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from unittest import mock

import click
from goga.commands.install import install
from goga.commands.install.install import _install

_install_module = importlib.import_module("goga.commands.install.install")


def _pip_result(returncode: int = 0) -> mock.MagicMock:
    result = mock.MagicMock()
    result.returncode = returncode
    return result


class TestInstallFacade:
    """Contract tests — verify the install facade and Click command shape."""

    def test_install_importable_from_facade(self) -> None:
        assert install is not None

    def test_install_facade_all(self) -> None:
        # ``import ... as`` would resolve to the Click command re-exported into
        # ``goga.commands`` (shadowing the submodule), so access the package
        # module directly to assert its own ``__all__``.
        facade = importlib.import_module("goga.commands.install")
        assert facade.__all__ == ["install"]

    def test_install_is_click_command(self) -> None:
        assert isinstance(install, click.Command)
        assert install.name == "install"

    def test_install_has_two_options(self) -> None:
        names = {p.name for p in install.params}
        assert {"sudo", "version"} <= names

    def test_install_argument_name_present(self) -> None:
        assert any(isinstance(p, click.Argument) and p.name == "name" for p in install.params)

    def test_install_sudo_is_flag(self) -> None:
        param = next(p for p in install.params if p.name == "sudo")
        assert isinstance(param, click.Option)
        assert param.is_flag
        assert param.default is False

    def test_install_version_default_none(self) -> None:
        param = next(p for p in install.params if p.name == "version")
        assert isinstance(param, click.Option)
        assert param.default is None

    def test_install_routine_signature(self) -> None:
        sig = inspect.signature(_install)
        params = sig.parameters
        assert list(params) == ["name", "use_sudo", "version"]
        assert params["use_sudo"].default is False
        assert params["version"].default is None
        assert sig.return_annotation is int or sig.return_annotation == "int"


class TestInstallLogicPositive:
    """Positive behavioral scenarios — argv composition per the Algorithm."""

    def test_install_composes_dash_form_package_identifier(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            _install(name="foo")
        argv = mock_run.call_args[0][0]
        assert argv == [sys.executable, "-m", "pip", "install", "goga-tool-foo", "-U"]
        assert "goga_tool_foo" not in argv
        assert argv[-1] == "-U"

    def test_install_appends_version_raw(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            _install(name="foo", version="==1.2.3")
        argv = mock_run.call_args[0][0]
        assert "goga-tool-foo==1.2.3" in argv
        assert argv[-1] == "-U"

    def test_install_sudo_prepends_preserve_env_home(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            _install(name="foo", use_sudo=True)
        argv = mock_run.call_args[0][0]
        assert argv[:3] == ["sudo", "--preserve-env=HOME", sys.executable]

    def test_install_combined_sudo_and_version(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            _install(name="foo", use_sudo=True, version=">=1.0")
        argv = mock_run.call_args[0][0]
        assert argv[0] == "sudo"
        assert argv[1] == "--preserve-env=HOME"
        assert "goga-tool-foo>=1.0" in argv


class TestInstallLogicNegative:
    """Negative behavioral scenarios — pip failure propagation (check=False)."""

    def test_install_pip_failure_propagates_exit_code(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(1)):
            rc = _install(name="foo")
        assert rc == 1

    def test_install_pip_non_zero_does_not_raise(self) -> None:
        # check=False means a non-zero pip returncode must surface as the return
        # value, NOT as a CalledProcessError — reaching the assertion proves no raise.
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(42)):
            rc = _install(name="foo")
        assert rc == 42


class TestInstallLogicEdge:
    """Edge-case behavioral scenarios — version/no-re-sync invariants."""

    def test_install_check_false_is_set_on_subprocess_run(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            _install(name="foo")
        assert mock_run.call_args.kwargs.get("check") is False

    def test_install_no_version_keeps_pkg_id_clean(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            _install(name="foo", version=None)
        argv = mock_run.call_args[0][0]
        assert "goga-tool-foo" in argv
        assert not any(a.startswith("goga-tool-foo==") for a in argv)
        assert not any(a.startswith("goga-tool-foo>") for a in argv)

    def test_install_bare_version_appended_verbatim(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            _install(name="foo", version="1.0")
        argv = mock_run.call_args[0][0]
        assert "goga-tool-foo1.0" in argv

    def test_install_empty_version_string_is_noop(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            _install(name="foo", version="")
        argv = mock_run.call_args[0][0]
        assert "goga-tool-foo" in argv
        assert argv[-2] == "goga-tool-foo"

    def test_install_empty_name_propagates_to_pip(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(1)) as mock_run:
            rc = _install(name="")
        argv = mock_run.call_args[0][0]
        assert "goga-tool-" in argv
        assert rc == 1

    def test_install_does_not_read_connect_yml(self, tmp_path: Path) -> None:
        # The autouse ``_isolate_home`` fixture redirects HOME to
        # ``tmp_path / ".pytest_home"``. install must not touch ``~/.goga`` at all
        # (no connect re-sync — that is upgrade's concern, not install's).
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()):
            _install(name="foo")
        assert not (tmp_path / ".pytest_home" / ".goga" / "connect.yml").exists()
        assert not (tmp_path / ".pytest_home" / ".goga").exists()
