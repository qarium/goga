from __future__ import annotations

import importlib
import logging
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
        # Access the package module directly to assert its own ``__all__``
        # (``import ... as`` would resolve to the Click command re-exported into
        # ``goga.commands``, shadowing the submodule). The facade now carries
        # both lifecycle commands of this cell — install and uninstall — pinned
        # as the exact surface. ``resolve_version`` belongs to the ``goga/version``
        # domain cell.
        facade = importlib.import_module("goga.commands.install")
        assert facade.__all__ == ["install", "uninstall"]

    def test_install_is_click_command(self) -> None:
        assert isinstance(install, click.Command)
        assert install.name == "install"

    def test_install_has_four_options(self) -> None:
        names = {p.name for p in install.params if isinstance(p, click.Option)}
        assert names == {"sudo", "version", "local", "no_connect"}

    def test_install_local_default_none(self) -> None:
        param = next(p for p in install.params if p.name == "local")
        assert isinstance(param, click.Option)
        assert param.default is None

    def test_install_local_exposes_long_and_short_flags(self) -> None:
        param = next(p for p in install.params if p.name == "local")
        # Both forms deserialise into the same Option/parameter.
        assert "--local" in param.opts
        assert "-l" in param.opts

    def test_install_exposes_local_option(self) -> None:
        # The --local/-l option is wired onto the CLI surface.
        result = CliRunner().invoke(app, ["install", "--help"])
        assert result.exit_code == 0
        assert "--local" in result.output
        assert "-l" in result.output

    def test_install_no_connect_option_is_flag_default_false(self) -> None:
        param = next(p for p in install.params if p.name == "no_connect")
        assert isinstance(param, click.Option)
        assert param.is_flag
        assert param.default is False

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
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install", "foo", "--version", "1.0.x"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv == [sys.executable, "-m", "pip", "install", "goga-tool-foo~=1.0.0", "-U"]
        assert mock_run.call_args.kwargs.get("check") is False

    def test_install_single_path_with_sudo_prefixes_preserve_env_home(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install", "foo", "--sudo"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv[:3] == ["sudo", "--preserve-env=HOME", sys.executable]
        assert argv[-1] == "-U"

    def test_install_bulk_path_one_pip_call_yaml_order(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_config(
            tmp_path,
            "language: python\ntools:\n  afm: 1.0.x\n  ralphex: 1.x\n  go: 1.0.1\n",
        )
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
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
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install", "--sudo"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv[:3] == ["sudo", "--preserve-env=HOME", sys.executable]

    def test_install_bulk_path_latest_marker_yields_no_specifier(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(
            tmp_path,
            "language: python\ntools:\n  viewer: latest\n  afm: 1.0.x\n",
        )
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
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

    def test_install_empty_path_with_empty_tools_mapping(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        # Wrapped in ClickException — a clean "Error:" line, not a raw traceback.
        assert "Error:" in result.output
        assert "operator" in result.output
        mock_run.assert_not_called()

    def test_install_single_path_empty_version_string_rejected(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "foo", "--version", ""])
        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "malformed" in result.output
        mock_run.assert_not_called()

    def test_install_bulk_path_version_rejected_in_tools_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(
            tmp_path,
            "language: python\ntools:\n  good: 1.0.x\n  bad: '==1.0'\n",
        )
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 1
        # The offending tool name is surfaced, not just a generic message.
        assert "Error:" in result.output
        assert "bad" in result.output
        mock_run.assert_not_called()

    def test_install_bulk_path_load_config_error_wrapped_in_click_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No .goga/config.yml in CWD → load_project_config raises FileNotFoundError → ClickException.
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 1
        assert "Error:" in result.output
        mock_run.assert_not_called()

    def test_install_pip_failure_propagates_exit_code_single(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(1)),
            mock.patch.object(_install_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "foo"])
        assert result.exit_code == 1
        # Pip failed → activation must not run (and must not touch the real ~/.goga).
        mock_resync.assert_not_called()

    def test_install_pip_failure_propagates_exit_code_bulk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "language: python\ntools:\n  afm: 1.0.x\n")
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(42)),
            mock.patch.object(_install_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 42
        mock_resync.assert_not_called()

    def test_install_missing_executable_surfaces_click_exception(self) -> None:
        # sudo/pip binary absent → subprocess.run raises FileNotFoundError →
        # a clean error, not a raw traceback.
        with mock.patch.object(_install_module.subprocess, "run", side_effect=FileNotFoundError("No such file: sudo")):
            result = CliRunner().invoke(app, ["install", "foo", "--sudo"])
        assert result.exit_code == 1
        assert "Error:" in result.output

    def test_install_bulk_path_malformed_yaml_wrapped_in_click_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A syntactically broken config → yaml.YAMLError → ClickException.
        _write_config(tmp_path, "language: python\ntools: [afm\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 1
        assert "Error:" in result.output
        mock_run.assert_not_called()

    def test_install_bulk_path_missing_language_wrapped_in_click_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A config without the required `language` → KeyError → ClickException.
        _write_config(tmp_path, "tools:\n  afm: 1.0.x\n")
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 1
        assert "Error:" in result.output
        mock_run.assert_not_called()

    def test_install_bulk_path_config_is_directory_wrapped_in_click_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # .goga/config.yml exists but is a directory → load_project_config's
        # config_path.open() raises IsADirectoryError (an OSError subclass that
        # is NOT FileNotFoundError) → must surface as a clean error, never as a
        # raw traceback. Pins the contract intent, not just the enumerated list.
        (tmp_path / ".goga" / "config.yml").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "Traceback" not in result.output
        assert not isinstance(result.exception, OSError)
        mock_run.assert_not_called()

    def test_install_missing_executable_names_the_binary(self) -> None:
        # --sudo on a host without the sudo binary: the FileNotFoundError
        # carries the missing binary's name (sudo). The error must name it
        # rather than misblame pip, which is fine on this path.
        err = FileNotFoundError(2, "No such file or directory", "sudo")
        with mock.patch.object(_install_module.subprocess, "run", side_effect=err):
            result = CliRunner().invoke(app, ["install", "foo", "--sudo"])
        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "sudo" in result.output

    def test_install_non_executable_binary_surfaces_click_exception(self) -> None:
        # The executable is present but not executable → subprocess.run raises
        # PermissionError (an OSError subclass that is NOT FileNotFoundError).
        # "The pip/sudo executable could not start" must surface as a clean error
        # for ANY OSError subclass, never as a raw traceback.
        err = PermissionError(13, "Permission denied", "sudo")
        with mock.patch.object(_install_module.subprocess, "run", side_effect=err):
            result = CliRunner().invoke(app, ["install", "foo", "--sudo"])
        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "Traceback" not in result.output
        assert not isinstance(result.exception, OSError)


class TestInstallWiringInvariants:
    """CODEMANIFEST invariants — what each path must (and must not) consult."""

    def test_install_single_path_ignores_config_tools(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # SINGLE path must not read .goga/config.yml — declaring tools must not
        # change the single-tool install argv.
        _write_config(
            tmp_path,
            "language: python\ntools:\n  afm: 1.0.x\n  ralphex: 1.x\n",
        )
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install", "foo"])
        assert result.exit_code == 0
        assert mock_run.call_count == 1
        assert _pkgs_from_argv(mock_run.call_args[0][0]) == ["goga-tool-foo"]

    def test_install_bulk_path_ignores_version_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # BULK path must not consult --version — each tool's own form is used.
        _write_config(tmp_path, "language: python\ntools:\n  afm: 1.0.x\n")
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install", "--version", "2.0"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        # The declared afm form resolves; the --version "2.0" never leaks in.
        assert _pkgs_from_argv(argv) == ["goga-tool-afm~=1.0.0"]
        assert "goga-tool-afm==2.0" not in argv

    def test_install_short_alias_v_resolves_version_in_single_path(self) -> None:
        # The short alias ``-v`` is registered alongside ``--version`` on the
        # same Click Option, so single path must resolve the form via
        # resolve_version exactly as the long form does.
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install", "foo", "-v", "1.0.x"])
        assert result.exit_code == 0
        assert _pkgs_from_argv(mock_run.call_args[0][0]) == ["goga-tool-foo~=1.0.0"]


class TestInstallLocalMode:
    """LOCAL PATH — ``--local``/``-l`` pip-installs a local directory.

    The fourth mode reuses ``_pip_argv([local], sudo)`` (``-U``, never ``-e``),
    ``_run_pip`` (pip owns the missing-path error), and ``_after_pip`` (activation
    follows SINGLE/BULK rules). Mutex VALIDATIONS reject ``name``+``--local`` and
    ``--local``+``--version``.
    """

    def test_install_local_invokes_pip_with_path(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "--local", "./my-tool"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert "./my-tool" in argv
        assert argv[-1] == "-U"
        assert "-e" not in argv
        mock_resync.assert_called_once()

    def test_install_local_short_alias_l(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install", "-l", "./my-tool"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert "./my-tool" in argv

    def test_install_local_no_connect_skips_activation(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "--local", "./my-tool", "--no-connect"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        mock_resync.assert_not_called()

    def test_install_local_propagates_pip_failure(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(1)) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "--local", "./missing"])
        assert result.exit_code == 1
        # pip-rc translated verbatim — no CLI-level existence check short-circuits.
        mock_run.assert_called_once()
        mock_resync.assert_not_called()

    def test_install_rejects_name_and_local_combined(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "foo", "--local", "./x"])
        assert result.exit_code == 1
        assert "mutually exclusive" in result.output
        mock_run.assert_not_called()

    def test_install_rejects_version_in_local_mode(self) -> None:
        with mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run:
            result = CliRunner().invoke(app, ["install", "--local", "./x", "-v", "1.0.1"])
        assert result.exit_code == 1
        assert "version" in result.output.lower()
        mock_run.assert_not_called()

    def test_install_local_does_not_read_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # LOCAL path must not consult .goga/config.yml — declaring tools must not
        # change the local install argv, and a config error must not surface.
        _write_config(
            tmp_path,
            "language: python\ntools:\n  afm: 1.0.x\n  ralphex: 1.x\n",
        )
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install", "--local", "./my-tool"])
        assert result.exit_code == 0
        assert mock_run.call_count == 1
        assert _pkgs_from_argv(mock_run.call_args[0][0]) == ["./my-tool"]

    def test_install_local_sudo_prepends_sudo_preserve_home(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "--local", "./x", "--sudo"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv[:2] == ["sudo", "--preserve-env=HOME"]
        assert "./x" in argv
        assert argv[-1] == "-U"
        # Activation runs once and never under sudo.
        mock_resync.assert_called_once()


class TestInstallHookWiringContract:
    """Contract tests — the release adds NO new CLI option, and every pip path
    hands ``_after_pip`` a hook-targets list (Algorithm step 4 — HOOKS).

    The hook wiring lives inside the existing surface: single targets
    ``[name]``, local the ``:<tool-name>`` suffix value (or an empty list),
    bulk the config keys in YAML order. The empty path never reaches hooks.
    """

    def test_install_facade_still_binds_only_the_four_cli_options(self) -> None:
        names = {p.name for p in install.params if isinstance(p, click.Option)}
        assert names == {"sudo", "version", "local", "no_connect"}

    def test_install_single_path_passes_name_as_hook_targets(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_install_module, "run_install_hooks") as mock_hooks,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install", "viewer"])
        assert result.exit_code == 0
        mock_hooks.assert_called_once_with(["viewer"])

    def test_install_local_path_passes_suffix_tool_as_hook_targets(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_install_module, "run_install_hooks") as mock_hooks,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install", "--local", "./my-tool:mytool"])
        assert result.exit_code == 0
        mock_hooks.assert_called_once_with(["mytool"])

    def test_install_bulk_path_passes_config_keys_as_hook_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "language: python\ntools:\n  viewer: latest\n  afm: 1.0.x\n")
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_install_module, "run_install_hooks") as mock_hooks,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        mock_hooks.assert_called_once_with(["viewer", "afm"])


class TestInstallHookFlow:
    """HOOKS step — pip → hooks → activation, per-path targets, containment.

    After a successful pip in single, local, and bulk mode ``run_install_hooks``
    receives the path's hook-target list. ``--no-connect`` suppresses only the
    re-sync; nothing runs after a failed pip; a hook failure is a user-facing
    non-zero exit with no rollback and no re-sync; a malformed ``--local``
    suffix and the empty path never reach hooks at all.
    """

    def test_install_single_mode_runs_hook_after_pip(self) -> None:
        order: list[str] = []

        def _pip(_argv: list[str], **_kwargs: object) -> mock.MagicMock:
            order.append("pip")
            return _pip_result()

        def _hooks(tools: list[str]) -> None:
            order.append(f"hooks:{','.join(tools)}")

        def _resync(_home: Path) -> int:
            order.append("resync")
            return 0

        with (
            mock.patch.object(_install_module.subprocess, "run", side_effect=_pip) as mock_run,
            mock.patch.object(_install_module, "run_install_hooks", side_effect=_hooks) as mock_hooks,
            mock.patch.object(_install_module, "resync_registered_agents", side_effect=_resync),
        ):
            result = CliRunner().invoke(app, ["install", "viewer"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        mock_hooks.assert_called_once_with(["viewer"])
        # The hook step sits between pip and the agent re-sync.
        assert order == ["pip", "hooks:viewer", "resync"]

    def test_install_local_with_suffix_targets_tool_hook(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "run_install_hooks") as mock_hooks,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install", "--local", "./my-tool:mytool"])
        assert result.exit_code == 0
        # The suffix is stripped from the pip target and names the hook tool.
        assert mock_run.call_count == 1
        assert _pkgs_from_argv(mock_run.call_args[0][0]) == ["./my-tool"]
        mock_hooks.assert_called_once_with(["mytool"])

    def test_install_bulk_hooks_follow_yaml_order(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_config(tmp_path, "language: python\ntools:\n  viewer: latest\n  afm: 1.0.x\n")
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "run_install_hooks") as mock_hooks,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        assert mock_run.call_count == 1
        assert _pkgs_from_argv(mock_run.call_args[0][0]) == ["goga-tool-viewer", "goga-tool-afm~=1.0.0"]
        mock_hooks.assert_called_once_with(["viewer", "afm"])

    def test_install_hook_failure_fails_command_without_rollback_or_resync(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(
                _install_module,
                "run_install_hooks",
                side_effect=RuntimeError("install hook for tool 'viewer' failed: boom"),
            ),
            mock.patch.object(_install_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "viewer"])
        assert result.exit_code == 1
        assert "install hook for tool 'viewer' failed: boom" in result.output
        # No rollback — exactly one pip install, no uninstall anywhere.
        assert mock_run.call_count == 1
        mock_resync.assert_not_called()

    def test_install_no_connect_still_runs_hooks(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_install_module, "run_install_hooks") as mock_hooks,
            mock.patch.object(_install_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "viewer", "--no-connect"])
        assert result.exit_code == 0
        mock_hooks.assert_called_once_with(["viewer"])
        # The flag suppresses ONLY the re-sync — the hooks still ran.
        mock_resync.assert_not_called()

    def test_install_pip_failure_skips_hooks_and_resync(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(2)),
            mock.patch.object(_install_module, "run_install_hooks") as mock_hooks,
            mock.patch.object(_install_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "viewer"])
        assert result.exit_code == 2
        mock_hooks.assert_not_called()
        mock_resync.assert_not_called()

    @pytest.mark.parametrize(
        "argv",
        [
            ["--local", "./x:"],
            ["--local", "./x:a/b"],
            ["--local", "./x:a\\b"],
            ["--local", "./x:a:b"],
        ],
    )
    def test_install_malformed_local_suffix_rejected_before_pip(self, argv: list[str]) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "run_install_hooks") as mock_hooks,
        ):
            result = CliRunner().invoke(app, ["install", *argv])
        assert result.exit_code == 1
        assert "Error: malformed --local value" in result.output
        assert "Traceback" not in result.output
        mock_run.assert_not_called()
        mock_hooks.assert_not_called()

    def test_install_local_without_suffix_warns_and_runs_no_hook(self, caplog: pytest.LogCaptureFixture) -> None:
        with (
            caplog.at_level(logging.WARNING, logger=_install_module.logger.name),
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_install_module, "run_install_hooks") as mock_hooks,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "--local", "./my-tool"])
        assert result.exit_code == 0
        mock_hooks.assert_called_once_with([])
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert warnings[0].message == "install hook skipped for local source"
        assert warnings[0].path == "./my-tool"
        assert warnings[0].hint == "pass :<tool-name> to enable the post-install hook"
        # A missing suffix suppresses the hook, NOT the activation.
        mock_resync.assert_called_once()

    def test_install_empty_mode_touches_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_config(tmp_path, "language: python\ntools: {}\n")
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "run_install_hooks") as mock_hooks,
            mock.patch.object(_install_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        assert "Nothing to install" in result.output
        # The empty path's never-clauses: no pip, no hooks, no activation.
        mock_run.assert_not_called()
        mock_hooks.assert_not_called()
        mock_resync.assert_not_called()


class TestInstallActivation:
    """Post-install activation wiring — ``--no-connect`` flag + ACTIVATION step.

    On a successful pip in the single or bulk path, activation runs once through
    ``resync_registered_agents(Path.home() / ".goga")``; the ``--no-connect``
    flag, a pip failure, and the empty path all skip activation.
    """

    def test_install_single_path_runs_activation_on_pip_success(self) -> None:
        expected_home = Path.home() / ".goga"
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "foo", "--version", "1.0.x"])
        assert result.exit_code == 0
        mock_resync.assert_called_once()
        # Activation targets the current user's ~/.goga.
        assert mock_resync.call_args[0][0] == expected_home

    def test_install_bulk_path_runs_activation_once(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_config(tmp_path, "language: python\ntools:\n  afm: 1.0.x\n  go: 1.0.1\n")
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        assert mock_run.call_count == 1
        assert mock_resync.call_count == 1
        # Resolved packages preserve YAML insertion order in the single pip argv.
        assert _pkgs_from_argv(mock_run.call_args[0][0]) == ["goga-tool-afm~=1.0.0", "goga-tool-go==1.0.1"]

    def test_install_no_connect_skips_activation(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "foo", "--no-connect"])
        assert result.exit_code == 0
        mock_resync.assert_not_called()

    def test_install_pip_failure_skips_activation(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result(42)),
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install", "foo"])
        assert result.exit_code == 42
        mock_resync.assert_not_called()

    def test_install_activation_failure_propagates_exit_code(self) -> None:
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_install_module, "resync_registered_agents", return_value=7),
        ):
            result = CliRunner().invoke(app, ["install", "foo"])
        assert result.exit_code == 7

    def test_install_empty_path_no_activation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_config(tmp_path, "language: python\n")
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_install_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_install_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["install"])
        assert result.exit_code == 0
        assert result.output.strip() == "Nothing to install"
        mock_run.assert_not_called()
        mock_resync.assert_not_called()
