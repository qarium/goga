"""Tests for the goga usages command group and its subcommands."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.commands.usages import usages as usages_cli
from goga.usages import DepStatus, FolderStatus, UsageState, UsageStatusReport
from goga.usages import status as status_logic

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

    def test_info_flag_leaves_group_dep_as_none(self) -> None:
        """``--info``/``-i`` only feeds the renderer; group/dep stay at their
        None defaults (the flag is not forwarded to ``status_logic``)."""
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

    def test_render_state_color_mapping(self) -> None:
        """The documented state -> foreground color is applied per dep line.

        Locks ``_STATE_COLOR`` (a documented part of the status contract: new ->
        yellow, up_to_date -> green, out_of_date -> red, error -> bright_red) and
        confirms each dep renders with that exact ``fg`` (capsys is not a TTY, so
        click strips the escape sequence and the value is only observable here).
        """
        assert {
            UsageState.new: "yellow",
            UsageState.up_to_date: "green",
            UsageState.out_of_date: "red",
            UsageState.error: "bright_red",
        } == _usages_mod._STATE_COLOR

        report = UsageStatusReport(
            deps=[
                DepStatus(group="g", dep="a", state=UsageState.new, folders=[]),
                DepStatus(group="g", dep="b", state=UsageState.up_to_date, folders=[]),
                DepStatus(group="g", dep="c", state=UsageState.out_of_date, folders=[]),
                DepStatus(
                    group="g",
                    dep="d",
                    state=UsageState.error,
                    error="failed to check usages status for g/d",
                    folders=[],
                ),
            ]
        )
        with mock.patch.object(_usages_mod.click, "secho") as secho_mock:
            _usages_mod.render_status_report(report, info=False)

        # one secho call per dep (sorted a..d), each carrying its state's fg
        fgs = [call.kwargs.get("fg") for call in secho_mock.call_args_list]
        assert fgs == ["yellow", "green", "red", "bright_red"]


class TestStatusAppIntegration:
    """App-level integration for ``goga usages status``: real ``status_logic``
    (config -> clone (mocked git) -> deploy -> hash_tree -> compare) driven
    end-to-end through the click CLI, plus the help surface. Git is mocked
    (``patch_clone``); ``deploy_usages`` and ``hash_tree`` run for real.
    """

    @staticmethod
    def _scenario(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
    ) -> tuple[Path, Path]:
        """Build a two-group, two-dep project: ``libs/click`` matches its remote
        (``up_to_date``, folder ``src``) and ``tools/cli`` drifts (``out_of_date``).

        Groups are declared out of sorted order to exercise the renderer's sorting.
        Returns the two fake-repo roots for ``patch_clone``.
        """
        click_repo = make_repo("click", {".usages/src/click.md": "C1"})
        cli_repo = make_repo("cli", {".usages/cli.md": "D1"})
        write_config(
            "usages:\n"
            "  tools:\n"
            "    cli:\n"
            "      git: https://x/cli.git\n"
            "  libs:\n"
            "    click:\n"
            "      git: https://x/click.git\n",
        )
        monkeypatch.chdir(tmp_path)

        usages_root = tmp_path / ".goga" / "usages"
        click_target = usages_root / "libs" / "click" / "src"
        click_target.mkdir(parents=True)
        (click_target / "click.md").write_text("C1")  # matches -> up_to_date
        cli_target = usages_root / "tools" / "cli"
        cli_target.mkdir(parents=True)
        (cli_target / "cli.md").write_text("D2")  # differs -> out_of_date

        return click_repo, cli_repo

    def test_status_prints_sorted_groups_deps_no_color(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ) -> None:
        """``goga usages status`` prints groups then deps sorted, propagates the
        report exit code, and emits no ANSI codes (CliRunner is not a TTY)."""
        click_repo, cli_repo = self._scenario(tmp_path, monkeypatch, make_repo, write_config)

        runner = CliRunner()
        with patch_clone({"https://x/click.git": click_repo, "https://x/cli.git": cli_repo}):
            result = runner.invoke(app, ["usages", "status"])

        assert result.exit_code == 1  # the cli dep is out_of_date
        # groups sorted: libs before tools (declared in the opposite order)
        assert result.output.index("libs") < result.output.index("tools")
        # deps rendered with their display states
        assert "click  up to date" in result.output
        assert "cli  out of date" in result.output
        # without --info, folders are not expanded
        assert "    src" not in result.output
        # CliRunner is not a TTY, so click strips ANSI escape codes
        assert "\x1b[" not in result.output

    def test_status_info_prints_folders_and_matches_exit_code(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ) -> None:
        """``--info`` expands each dep into its folders (sorted by path); the CLI
        exit code equals the report's derived exit code."""
        click_repo, cli_repo = self._scenario(tmp_path, monkeypatch, make_repo, write_config)

        runner = CliRunner()
        with patch_clone({"https://x/click.git": click_repo, "https://x/cli.git": cli_repo}):
            report = status_logic()
            result = runner.invoke(app, ["usages", "status", "--info"])

        assert result.exit_code == report.exit_code == 1
        # --info expands the up_to_date click dep into its "src" folder
        assert "    src up to date" in result.output

    def test_app_usages_status_help_lists_options(self) -> None:
        """``goga usages status --help`` lists all three options."""
        runner = CliRunner()
        result = runner.invoke(app, ["usages", "status", "--help"])

        assert result.exit_code == 0
        assert "--info" in result.output
        assert "--group" in result.output
        assert "--dep" in result.output

    def test_app_usages_help_lists_status(self) -> None:
        """``goga usages --help`` lists the ``status`` subcommand."""
        runner = CliRunner()
        result = runner.invoke(app, ["usages", "--help"])

        assert result.exit_code == 0
        assert "status" in result.output
