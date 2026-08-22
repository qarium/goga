from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest import mock

import click
from click.testing import CliRunner
from goga.cli import app
from goga.commands.install import uninstall

_uninstall_module = importlib.import_module("goga.commands.install.uninstall")


def _pip_result(returncode: int = 0) -> mock.MagicMock:
    result = mock.MagicMock()
    result.returncode = returncode
    return result


class TestUninstallContract:
    """Contract tests — verify the uninstall facade and Click command shape."""

    def test_uninstall_importable_from_facade(self) -> None:
        assert uninstall is not None

    def test_uninstall_facade_all(self) -> None:
        # The install cell facade carries both lifecycle commands — install
        # and uninstall — pinned as the exact declared surface.
        facade = importlib.import_module("goga.commands.install")
        assert facade.__all__ == ["install", "uninstall"]

    def test_uninstall_is_click_command(self) -> None:
        assert isinstance(uninstall, click.Command)
        assert uninstall.name == "uninstall"

    def test_uninstall_has_three_options(self) -> None:
        names = {p.name for p in uninstall.params if isinstance(p, click.Option)}
        assert names == {"sudo", "yes", "target_user"}

    def test_uninstall_argument_name_required(self) -> None:
        arg = next(p for p in uninstall.params if isinstance(p, click.Argument) and p.name == "name")
        assert arg.required is True

    def test_uninstall_yes_exposes_long_and_short_flags(self) -> None:
        param = next(p for p in uninstall.params if p.name == "yes")
        # Both forms deserialise into the same Option/parameter.
        assert "--yes" in param.opts
        assert "-y" in param.opts
        assert param.is_flag is True
        assert param.default is False

    def test_uninstall_sudo_is_flag_default_false(self) -> None:
        param = next(p for p in uninstall.params if p.name == "sudo")
        assert isinstance(param, click.Option)
        assert param.is_flag is True
        assert param.default is False

    def test_uninstall_user_option_binds_target_user_default_none(self) -> None:
        param = next(p for p in uninstall.params if p.name == "target_user")
        assert isinstance(param, click.Option)
        assert param.opts == ["--user"]
        assert param.default is None

    def test_uninstall_help_lists_options(self) -> None:
        # The --sudo / --yes, -y / --user surface is wired onto the root group.
        result = CliRunner().invoke(app, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "--sudo" in result.output
        assert "-y" in result.output
        assert "--yes" in result.output
        assert "--user" in result.output


class TestUninstallLogicPositive:
    """Positive behavioral scenarios — confirmation, argv composition, re-sync."""

    def test_uninstall_empty_input_confirms_removal(self) -> None:
        # Enter on the [Y/n] prompt — the default answer Y — drives the removal.
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo"], input="\n")
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv == [sys.executable, "-m", "pip", "uninstall", "-y", "goga-tool-foo"]
        assert mock_run.call_args.kwargs.get("check") is False
        assert mock_resync.call_args[0][0] == Path.home() / ".goga"

    def test_uninstall_prompt_text_rendered(self) -> None:
        # click renders the default-Y suffix itself; the prompt names the tool.
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo"], input="y\n")
        assert result.exit_code == 0
        assert 'Remove goga tool "foo"? [Y/n]' in result.output

    def test_uninstall_yes_flag_skips_prompt(self) -> None:
        # The scripted form reads no stdin at all — the prompt never renders.
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "--yes"])
        assert result.exit_code == 0
        assert "[Y/n]" not in result.output
        assert mock_run.call_count == 1

    def test_uninstall_short_y_alias_skips_prompt(self) -> None:
        # -y and --yes bind the same Option — identical behavior.
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "-y"])
        assert result.exit_code == 0
        assert "[Y/n]" not in result.output
        assert mock_run.call_args[0][0] == [sys.executable, "-m", "pip", "uninstall", "-y", "goga-tool-foo"]

    def test_uninstall_sudo_prefixes_preserve_env_home(self) -> None:
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "--sudo", "--yes"])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv[:3] == ["sudo", "--preserve-env=HOME", sys.executable]
        assert argv[3:] == ["-m", "pip", "uninstall", "-y", "goga-tool-foo"]
        # The re-sync always runs without sudo against the preserved home.
        assert mock_resync.call_args[0][0] == Path.home() / ".goga"

    def test_uninstall_user_resolves_home_via_pwd(self) -> None:
        pwd_entry = mock.MagicMock(pw_dir="/home/alice")
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module.pwd, "getpwnam", return_value=pwd_entry),
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "--user", "alice", "--yes"])
        assert result.exit_code == 0
        # --user affects only the re-sync home; pip runs as the current user.
        assert mock_run.call_args[0][0][0] == sys.executable
        assert mock_resync.call_args[0][0] == Path("/home/alice") / ".goga"

    def test_uninstall_resync_outcome_is_final_exit_code(self) -> None:
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=3),
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "--yes"])
        assert result.exit_code == 3

    def test_uninstall_resync_receives_isolated_home(self) -> None:
        # The autouse _isolate_home fixture points HOME at a tmp dir — the
        # re-sync must target it, and the command itself never writes the
        # registry (connect is the single writer).
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()),
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "--yes"])
        assert result.exit_code == 0
        assert mock_resync.call_args[0][0] == Path(os.environ["HOME"]) / ".goga"
        assert not (Path(os.environ["HOME"]) / ".goga" / "connect.yml").exists()


class TestUninstallLogicNegative:
    """Negative behavioral scenarios — decline, pip failure, unknown user, EOF."""

    def test_uninstall_declined_confirmation_exits_zero_without_pip(self) -> None:
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo"], input="n\n")
        assert result.exit_code == 0
        assert "cancelled" in result.output
        mock_run.assert_not_called()
        mock_resync.assert_not_called()

    def test_uninstall_pip_failure_propagates_and_skips_resync(self) -> None:
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result(2)),
            mock.patch.object(_uninstall_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "--yes"])
        assert result.exit_code == 2
        # pip's rc is final — the re-sync is suppressed after a failed pip.
        mock_resync.assert_not_called()

    def test_uninstall_unknown_user_fails_fast_before_prompt_and_pip(self) -> None:
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module.pwd, "getpwnam", side_effect=KeyError("ghost")),
            mock.patch.object(_uninstall_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "--user", "ghost"], input="")
        assert result.exit_code == 1
        assert "unknown user" in result.output
        # Validation fires before the confirmation — nothing is prompted or removed.
        assert "[Y/n]" not in result.output
        mock_run.assert_not_called()
        mock_resync.assert_not_called()

    def test_uninstall_stdin_eof_aborts_non_zero(self) -> None:
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo"], input="")
        assert result.exit_code == 1
        mock_run.assert_not_called()
        mock_resync.assert_not_called()

    def test_uninstall_pip_start_failure_is_clean_error(self) -> None:
        # --sudo on a host without the sudo binary: the FileNotFoundError
        # carries the missing binary's name — a clean error naming sudo.
        err = FileNotFoundError(2, "No such file or directory", "sudo")
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", side_effect=err),
            mock.patch.object(_uninstall_module, "resync_registered_agents") as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "--sudo", "--yes"])
        assert result.exit_code == 1
        assert "failed to start" in result.output
        assert "Traceback" not in result.output
        mock_resync.assert_not_called()


class TestUninstallEdgeCases:
    """Edge cases — pip's not-installed skip, combined flags, unvalidated names."""

    def test_uninstall_not_installed_warning_still_resyncs(self) -> None:
        # pip 25.x answers an unknown package with "Skipping ... as it is not
        # installed" and exit 0 — a pip success, so the re-sync still runs and
        # cleans the orphaned artifacts.
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "nope", "--yes"])
        assert result.exit_code == 0
        assert mock_resync.call_count == 1
        assert mock_run.call_args[0][0][-1] == "goga-tool-nope"

    def test_uninstall_sudo_and_user_combined_user_wins_for_home(self) -> None:
        pwd_entry = mock.MagicMock(pw_dir="/home/alice")
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module.pwd, "getpwnam", return_value=pwd_entry),
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0) as mock_resync,
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo", "--sudo", "--user", "alice", "--yes"])
        assert result.exit_code == 0
        # pip runs under sudo; the re-sync home comes from --user.
        assert mock_run.call_args[0][0][:3] == ["sudo", "--preserve-env=HOME", sys.executable]
        assert mock_resync.call_args[0][0] == Path("/home/alice") / ".goga"

    def test_uninstall_name_composed_without_cli_validation(self) -> None:
        # pip owns the unknown-package error — the CLI composes goga-tool-<name>
        # verbatim without pre-validating the identifier.
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["uninstall", "foo-bar", "--yes"])
        assert result.exit_code == 0
        assert mock_run.call_args[0][0][-1] == "goga-tool-foo-bar"
        assert mock_run.call_count == 1

    def test_uninstall_empty_name_composes_identifier_without_validation(self) -> None:
        # Even an empty name is composed as-is — no CLI-level validation of
        # the identifier; exactly one pip invocation is issued.
        with (
            mock.patch.object(_uninstall_module.subprocess, "run", return_value=_pip_result()) as mock_run,
            mock.patch.object(_uninstall_module, "resync_registered_agents", return_value=0),
        ):
            result = CliRunner().invoke(app, ["uninstall", "", "--yes"])
        assert result.exit_code == 0
        assert mock_run.call_args[0][0][-1] == "goga-tool-"
        assert mock_run.call_count == 1
