"""Tests for the goga usages command group and its subcommands."""

from __future__ import annotations

import importlib
from unittest import mock

import click
from click.testing import CliRunner
from goga.cli import app
from goga.commands.usages import usages as usages_cli
from goga.usages import DepStatus, FolderStatus, UsageState, UsageStatusReport

# The facade goga.commands.usages re-exports the click Group ``usages``, shadowing
# the ``usages`` submodule in the package __dict__. On Python 3.10
# ``mock.patch("goga.commands.usages.usages.sync_logic")`` resolves the dotted path
# through sequential ``getattr``, finds the Group where it expects the submodule,
# and raises ``AttributeError``. Holding a direct module reference makes
# ``mock.patch.object`` work uniformly across Python versions.
_usages_mod = importlib.import_module("goga.commands.usages.usages")


class TestContract:
    """Contract-level tests for the usages command group."""

    def test_usages_importable_from_facade(self) -> None:
        from goga.commands.usages import usages as facade_usages

        assert facade_usages is usages_cli

    def test_usages_is_click_group(self) -> None:
        assert isinstance(usages_cli, click.Group)

    def test_usages_sync_subcommand_registered(self) -> None:
        assert "sync" in usages_cli.commands

    def test_usages_sync_force_flag_contract(self) -> None:
        sync_cmd = usages_cli.commands["sync"]
        force_param = {p.name: p for p in sync_cmd.params}["force"]
        assert isinstance(force_param, click.Option)
        assert force_param.is_flag is True
        assert force_param.default is False


class TestLogic:
    """Logic-level tests for usages sync delegation."""

    def test_cli_usages_sync_delegates_and_propagates_exit(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", return_value=1) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync"])

        mock_logic.assert_called_once_with(False)
        assert result.exit_code == 1

    def test_cli_usages_sync_long_force_flag_passes_true(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync", "--force"])

        mock_logic.assert_called_once_with(True)
        assert result.exit_code == 0

    def test_cli_usages_sync_short_force_flag_passes_true(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync", "-f"])

        mock_logic.assert_called_once_with(True)
        assert result.exit_code == 0

    def test_cli_usages_sync_config_error_converts_to_clickexception(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", side_effect=ValueError("boom")):
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync"])

        assert result.exit_code != 0
        assert "boom" in result.output

    def test_cli_usages_sync_yaml_error_converts_to_clickexception(self) -> None:
        import yaml as yaml_mod

        with mock.patch.object(_usages_mod, "sync_logic", side_effect=yaml_mod.YAMLError("bad yaml")):
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync"])

        assert result.exit_code != 0
        assert "bad yaml" in result.output

    def test_cli_usages_sync_keyerror_converts_to_clickexception(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", side_effect=KeyError("language is required")):
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync"])

        assert result.exit_code != 0
        assert "language is required" in result.output
        # click.ClickException produces a clean message, not a raw traceback.
        assert "Traceback" not in result.output

    def test_cli_usages_help_lists_sync(self) -> None:
        runner = CliRunner()
        result = runner.invoke(usages_cli, ["--help"])
        assert result.exit_code == 0
        assert "sync" in result.output


class TestAppIntegration:
    """App-level integration: usages is registered on the root ``app`` and
    delegates end-to-end through ``goga usages sync``."""

    def test_app_usages_help_lists_sync(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["usages", "--help"])

        assert result.exit_code == 0
        assert "sync" in result.output

    def test_app_usages_sync_help_shows_force(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["usages", "sync", "--help"])

        assert result.exit_code == 0
        assert "--force" in result.output

    def test_app_usages_sync_delegates_to_sync_logic(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(app, ["usages", "sync"])

        mock_logic.assert_called_once_with(False)
        assert result.exit_code == 0

    def test_app_usages_sync_force_delegates_true(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(app, ["usages", "sync", "--force"])

        mock_logic.assert_called_once_with(True)
        assert result.exit_code == 0

    def test_app_usages_sync_config_error_converts_to_clickexception(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", side_effect=FileNotFoundError("no config")):
            runner = CliRunner()
            result = runner.invoke(app, ["usages", "sync"])

        assert result.exit_code != 0
        assert "no config" in result.output
        # click.ClickException produces a clean message, not a raw traceback.
        assert "Traceback" not in result.output


def _report(exit_code_deps: list[DepStatus] | None = None) -> UsageStatusReport:
    """Build a UsageStatusReport (by default a single up_to_date dep → exit 0)."""
    if exit_code_deps is None:
        exit_code_deps = [
            DepStatus(group="libs", dep="click", state=UsageState.up_to_date, folders=[])
        ]
    return UsageStatusReport(deps=exit_code_deps)


class TestStatusContract:
    """Contract-level tests for the usages.status subcommand."""

    def test_usages_status_subcommand_registered(self) -> None:
        assert "status" in usages_cli.commands

    def test_usages_status_info_flag_contract(self) -> None:
        status_cmd = usages_cli.commands["status"]
        info_param = {p.name: p for p in status_cmd.params}["info"]
        assert isinstance(info_param, click.Option)
        assert info_param.is_flag is True
        assert info_param.default is False

    def test_usages_status_group_option_contract(self) -> None:
        status_cmd = usages_cli.commands["status"]
        group_param = {p.name: p for p in status_cmd.params}["group"]
        assert isinstance(group_param, click.Option)
        assert group_param.default is None

    def test_usages_status_dep_option_contract(self) -> None:
        status_cmd = usages_cli.commands["status"]
        dep_param = {p.name: p for p in status_cmd.params}["dep"]
        assert isinstance(dep_param, click.Option)
        assert dep_param.default is None

    def test_render_status_report_importable_and_callable(self) -> None:
        from goga.commands.usages.usages import render_status_report

        assert callable(render_status_report)


class TestStatusLogic:
    """Logic-level tests for usages.status delegation and rendering."""

    def test_cli_usages_status_delegates_and_propagates_exit(self) -> None:
        with mock.patch.object(_usages_mod, "status_logic", return_value=_report()) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["status"])

        mock_logic.assert_called_once_with(None, None)
        assert result.exit_code == 0

    def test_cli_usages_status_exit_code_propagates_drift(self) -> None:
        report = _report(
            [DepStatus(group="libs", dep="click", state=UsageState.out_of_date, folders=[])]
        )
        with mock.patch.object(_usages_mod, "status_logic", return_value=report):
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["status"])

        assert result.exit_code == 1

    def test_cli_usages_status_info_flag_passes_true(self) -> None:
        with mock.patch.object(_usages_mod, "status_logic", return_value=_report()) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["status", "--info"])
        assert mock_logic.call_args.args == (None, None)

        with mock.patch.object(_usages_mod, "status_logic", return_value=_report()) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["status", "-i"])
        assert mock_logic.call_args.args == (None, None)

    def test_cli_usages_status_group_passes_through(self) -> None:
        with mock.patch.object(_usages_mod, "status_logic", return_value=_report()) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["status", "--group", "libs"])

        assert mock_logic.call_args.args == ("libs", None)

    def test_cli_usages_status_dep_passes_through(self) -> None:
        with mock.patch.object(_usages_mod, "status_logic", return_value=_report()) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["status", "-d", "click"])

        assert mock_logic.call_args.args == (None, "click")

    def test_cli_usages_status_group_and_dep_pass_through(self) -> None:
        with mock.patch.object(_usages_mod, "status_logic", return_value=_report()) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["status", "-g", "libs", "--dep", "click"])

        assert mock_logic.call_args.args == ("libs", "click")

    def test_cli_usages_status_config_error_converts_to_clickexception(self) -> None:
        with mock.patch.object(_usages_mod, "status_logic", side_effect=ValueError("boom")):
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["status"])

        assert result.exit_code != 0
        assert "boom" in result.output
        assert "Traceback" not in result.output

    def test_cli_usages_status_yaml_error_converts_to_clickexception(self) -> None:
        import yaml as yaml_mod

        with mock.patch.object(_usages_mod, "status_logic", side_effect=yaml_mod.YAMLError("bad yaml")):
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["status"])

        assert result.exit_code != 0
        assert "bad yaml" in result.output
        assert "Traceback" not in result.output

    def test_cli_usages_status_keyerror_converts_to_clickexception(self) -> None:
        with mock.patch.object(_usages_mod, "status_logic", side_effect=KeyError("language is required")):
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["status"])

        assert result.exit_code != 0
        assert "language is required" in result.output
        assert "Traceback" not in result.output

    def test_cli_usages_status_help_lists_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(usages_cli, ["status", "--help"])

        assert result.exit_code == 0
        assert "--info" in result.output
        assert "--group" in result.output
        assert "--dep" in result.output


class TestRenderStatusReport:
    """Logic-level tests for render_status_report output ordering and content."""

    @staticmethod
    def _sample_report() -> UsageStatusReport:
        # Declared out of order to exercise the renderer's sorting.
        return UsageStatusReport(
            deps=[
                DepStatus(
                    group="tools",
                    dep="broken",
                    state=UsageState.error,
                    folders=[],
                    error="failed to check usages status for tools/broken",
                ),
                DepStatus(group="tools", dep="cli", state=UsageState.new, folders=[]),
                DepStatus(group="libs", dep="ansi", state=UsageState.out_of_date, folders=[]),
                DepStatus(
                    group="libs",
                    dep="click",
                    state=UsageState.up_to_date,
                    folders=[
                        FolderStatus(path="src", state=UsageState.up_to_date),
                        FolderStatus(path="", state=UsageState.out_of_date),
                    ],
                ),
            ]
        )

    def test_render_sorts_by_group_then_dep(self, capsys) -> None:  # type: ignore[no-untyped-def]
        from goga.commands.usages.usages import render_status_report

        render_status_report(self._sample_report(), info=False)
        out = capsys.readouterr().out
        lines = [ln for ln in out.splitlines() if ln]

        # Groups sorted: libs before tools.
        assert lines.index("libs") < lines.index("tools")
        # Within libs: ansi before click.
        assert next(i for i, ln in enumerate(lines) if ln.startswith("  ansi ")) < next(
            i for i, ln in enumerate(lines) if ln.startswith("  click ")
        )
        # Within tools: broken before cli.
        assert next(i for i, ln in enumerate(lines) if ln.startswith("  broken ")) < next(
            i for i, ln in enumerate(lines) if ln.startswith("  cli ")
        )

    def test_render_error_dep_appends_message(self, capsys) -> None:  # type: ignore[no-untyped-def]
        from goga.commands.usages.usages import render_status_report

        render_status_report(self._sample_report(), info=False)
        out = capsys.readouterr().out

        assert "(failed to check usages status for tools/broken)" in out

    def test_render_info_false_omits_folders(self, capsys) -> None:  # type: ignore[no-untyped-def]
        from goga.commands.usages.usages import render_status_report

        render_status_report(self._sample_report(), info=False)
        out = capsys.readouterr().out

        # Folder content of the click dep is never printed when info is False.
        assert "src up to date" not in out

    def test_render_info_true_prints_folders_sorted(self, capsys) -> None:  # type: ignore[no-untyped-def]
        from goga.commands.usages.usages import render_status_report

        render_status_report(self._sample_report(), info=True)
        out = capsys.readouterr().out
        lines = [ln for ln in out.splitlines() if ln]

        # The click dep line precedes its folder lines; folders are sorted by
        # path (root-level "" before "src").
        click_idx = next(i for i, ln in enumerate(lines) if ln.startswith("  click "))
        root_folder_idx = next(i for i, ln in enumerate(lines) if "out of date" in ln and ln.startswith("    "))
        src_folder_idx = next(i for i, ln in enumerate(lines) if ln.startswith("    src "))
        assert click_idx < root_folder_idx < src_folder_idx

    def test_render_no_color_codes_outside_tty(self, capsys) -> None:  # type: ignore[no-untyped-def]
        from goga.commands.usages.usages import render_status_report

        render_status_report(self._sample_report(), info=True)
        out = capsys.readouterr().out

        # capsys is not a TTY, so click strips ANSI escape codes.
        assert "\x1b[" not in out
