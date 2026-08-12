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
from goga.usages import DepStatus, EntryChange, EntryKind, EntryStatus, UsageState, UsageStatusReport
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

    def test_usages_group_carries_group_option(self) -> None:
        """The ``--group/-g`` option is declared on the ``usages`` GROUP callback,
        not on any subcommand."""
        group_params = {p.name: p for p in usages_cli.params}
        assert "group" in group_params
        group_param = group_params["group"]
        assert isinstance(group_param, click.Option)
        assert group_param.default is None
        assert "--group" in group_param.opts
        assert "-g" in group_param.opts
        # not declared on the subcommands
        for sub in ("sync", "status"):
            assert "group" not in {p.name for p in usages_cli.commands[sub].params}

    def test_usages_group_carries_dep_option(self) -> None:
        """The ``--dep/-d`` option is declared on the ``usages`` GROUP callback,
        not on any subcommand."""
        group_params = {p.name: p for p in usages_cli.params}
        assert "dep" in group_params
        dep_param = group_params["dep"]
        assert isinstance(dep_param, click.Option)
        assert dep_param.default is None
        assert "--dep" in dep_param.opts
        assert "-d" in dep_param.opts
        # not declared on the subcommands
        for sub in ("sync", "status"):
            assert "dep" not in {p.name for p in usages_cli.commands[sub].params}


class TestLogic:
    """Logic-level tests for usages sync delegation."""

    def test_cli_usages_sync_delegates_and_propagates_exit(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", return_value=1) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync"])

        mock_logic.assert_called_once_with(False, None, None)
        assert result.exit_code == 1

    def test_cli_usages_sync_long_force_flag_passes_true(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync", "--force"])

        mock_logic.assert_called_once_with(True, None, None)
        assert result.exit_code == 0

    def test_cli_usages_sync_short_force_flag_passes_true(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["sync", "-f"])

        mock_logic.assert_called_once_with(True, None, None)
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

    def test_cli_usages_group_threads_group_dep_to_sync(self) -> None:
        """``--group``/``--dep`` (declared on the group) thread to ``sync_logic``
        as ``(force, group, dep)`` alongside the subcommand's ``--force``."""
        with mock.patch.object(_usages_mod, "sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(usages_cli, ["--group", "libs", "--dep", "click", "sync", "--force"])

        mock_logic.assert_called_once_with(True, "libs", "click")
        assert result.exit_code == 0

    def test_cli_usages_group_threads_none_when_absent_to_sync(self) -> None:
        """``--group``/``--dep`` absent → ``sync_logic`` receives ``None``."""
        with mock.patch.object(_usages_mod, "sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["sync"])

        mock_logic.assert_called_once_with(False, None, None)

    def test_cli_usages_group_threads_group_dep_short_flags_to_sync(self) -> None:
        """The short ``-g``/``-d`` forms also thread to ``sync_logic``."""
        with mock.patch.object(_usages_mod, "sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["-g", "libs", "-d", "click", "sync"])

        mock_logic.assert_called_once_with(False, "libs", "click")


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

        mock_logic.assert_called_once_with(False, None, None)
        assert result.exit_code == 0

    def test_app_usages_sync_force_delegates_true(self) -> None:
        with mock.patch.object(_usages_mod, "sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(app, ["usages", "sync", "--force"])

        mock_logic.assert_called_once_with(True, None, None)
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
        exit_code_deps = [DepStatus(group="libs", dep="click", state=UsageState.up_to_date, entries=[])]
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
        """``--group`` is on the ``usages`` GROUP, not on ``status``."""
        status_cmd = usages_cli.commands["status"]
        assert "group" not in {p.name for p in status_cmd.params}

    def test_usages_status_dep_option_contract(self) -> None:
        """``--dep`` is on the ``usages`` GROUP, not on ``status``."""
        status_cmd = usages_cli.commands["status"]
        assert "dep" not in {p.name for p in status_cmd.params}

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
        report = _report([DepStatus(group="libs", dep="click", state=UsageState.out_of_date, entries=[])])
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
            runner.invoke(usages_cli, ["--group", "libs", "status"])

        assert mock_logic.call_args.args == ("libs", None)

    def test_cli_usages_status_dep_passes_through(self) -> None:
        with mock.patch.object(_usages_mod, "status_logic", return_value=_report()) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["--dep", "click", "status"])

        assert mock_logic.call_args.args == (None, "click")

    def test_cli_usages_status_group_and_dep_pass_through(self) -> None:
        with mock.patch.object(_usages_mod, "status_logic", return_value=_report()) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["-g", "libs", "--dep", "click", "status"])

        assert mock_logic.call_args.args == ("libs", "click")

    def test_cli_usages_group_threads_group_dep_to_status(self) -> None:
        """``--group``/``--dep`` thread to ``status_logic`` unchanged in shape:
        ``(group, dep)``."""
        with mock.patch.object(_usages_mod, "status_logic", return_value=_report()) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["--group", "libs", "--dep", "click", "status"])

        assert mock_logic.call_args.args == ("libs", "click")

    def test_cli_usages_group_threads_none_when_absent_to_status(self) -> None:
        """``--group``/``--dep`` absent → ``status_logic`` receives ``(None, None)``."""
        with mock.patch.object(_usages_mod, "status_logic", return_value=_report()) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["status"])

        assert mock_logic.call_args.args == (None, None)

    def test_cli_usages_status_info_still_threads_with_group_dep(self) -> None:
        """Regression: lifting the options did not break ``status``'s filter
        wiring or ``--info/-i`` — ``--info`` only feeds the renderer, while
        ``--group``/``--dep`` still reach ``status_logic``."""
        with mock.patch.object(_usages_mod, "status_logic", return_value=_report()) as mock_logic:
            runner = CliRunner()
            runner.invoke(usages_cli, ["--group", "libs", "status", "--info"])

        assert mock_logic.call_args.args == ("libs", None)

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
        """``status --help`` shows only ``--info`` (group/dep moved to the group)."""
        runner = CliRunner()
        result = runner.invoke(usages_cli, ["status", "--help"])

        assert result.exit_code == 0
        assert "--info" in result.output
        assert "--group" not in result.output
        assert "--dep" not in result.output

    def test_cli_usages_group_help_lists_group_dep_options(self) -> None:
        """``--group``/``--dep`` now appear in ``usages --help`` (group level)."""
        runner = CliRunner()
        result = runner.invoke(usages_cli, ["--help"])

        assert result.exit_code == 0
        assert "--group" in result.output
        assert "--dep" in result.output


class TestRenderStatusReport:
    """Logic-level tests for render_status_report output ordering and content."""

    @staticmethod
    def _sample_report() -> UsageStatusReport:
        # Declared out of order to exercise the renderer's sorting. The ``click``
        # dep carries a per-node entry tree (modified dir + unchanged sibling) so
        # ``--info`` expansion is exercised.
        return UsageStatusReport(
            deps=[
                DepStatus(
                    group="tools",
                    dep="broken",
                    state=UsageState.error,
                    entries=[],
                    error="failed to check usages status for tools/broken",
                ),
                DepStatus(group="tools", dep="cli", state=UsageState.new, entries=[]),
                DepStatus(group="libs", dep="ansi", state=UsageState.out_of_date, entries=[]),
                DepStatus(
                    group="libs",
                    dep="click",
                    state=UsageState.up_to_date,
                    entries=[
                        EntryStatus(path="README.md", kind=EntryKind.file, change=EntryChange.unchanged),
                        EntryStatus(path="docs", kind=EntryKind.dir, change=EntryChange.modified),
                        EntryStatus(path="docs/main.md", kind=EntryKind.file, change=EntryChange.modified),
                        EntryStatus(path="docs/utils.md", kind=EntryKind.file, change=EntryChange.unchanged),
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
        assert lines.index("libs/") < lines.index("tools/")
        # Within libs: ansi before click.
        assert next(i for i, ln in enumerate(lines) if "[*] ansi/" in ln) < next(
            i for i, ln in enumerate(lines) if "[ ] click/" in ln
        )
        # Within tools: broken before cli.
        assert next(i for i, ln in enumerate(lines) if "[!] broken/" in ln) < next(
            i for i, ln in enumerate(lines) if "[+] cli/" in ln
        )

    def test_render_dep_markers_map_to_state(self, capsys) -> None:  # type: ignore[no-untyped-def]
        """Each dep marker reflects its UsageState: new->[+], up_to_date->[ ],
        out_of_date->[*], error->[!]."""
        from goga.commands.usages.usages import render_status_report

        render_status_report(self._sample_report(), info=False)
        out = capsys.readouterr().out

        assert "[+] cli/" in out  # new
        assert "[ ] click/" in out  # up_to_date
        assert "[*] ansi/" in out  # out_of_date
        assert "[!] broken/" in out  # error

    def test_render_error_dep_appends_message(self, capsys) -> None:  # type: ignore[no-untyped-def]
        from goga.commands.usages.usages import render_status_report

        render_status_report(self._sample_report(), info=False)
        out = capsys.readouterr().out

        assert "(failed to check usages status for tools/broken)" in out

    def test_render_info_false_omits_entries(self, capsys) -> None:  # type: ignore[no-untyped-def]
        from goga.commands.usages.usages import render_status_report

        render_status_report(self._sample_report(), info=False)
        out = capsys.readouterr().out

        # The click dep's entry tree is never printed when info is False.
        assert "main.md" not in out
        assert "docs/" not in out

    def test_render_info_true_prints_entries_sorted(self, capsys) -> None:  # type: ignore[no-untyped-def]
        from goga.commands.usages.usages import render_status_report

        render_status_report(self._sample_report(), info=True)
        out = capsys.readouterr().out
        lines = [ln for ln in out.splitlines() if ln]

        # The click dep line precedes its entry tree; children are sorted by name
        # (README.md before docs), and within docs main.md before utils.md.
        click_idx = next(i for i, ln in enumerate(lines) if "[ ] click/" in ln)
        readme_idx = next(i for i, ln in enumerate(lines) if "[ ] README.md" in ln)
        docs_idx = next(i for i, ln in enumerate(lines) if "[*] docs/" in ln)
        main_idx = next(i for i, ln in enumerate(lines) if "[*] main.md" in ln)
        utils_idx = next(i for i, ln in enumerate(lines) if "[ ] utils.md" in ln)
        assert click_idx < readme_idx < docs_idx < main_idx < utils_idx

    def test_render_dirs_carry_trailing_slash(self, capsys) -> None:  # type: ignore[no-untyped-def]
        from goga.commands.usages.usages import render_status_report

        render_status_report(self._sample_report(), info=True)
        out = capsys.readouterr().out

        # Directories render with a trailing slash; files do not.
        assert "[*] docs/" in out
        assert "main.md" in out
        assert "main.md/" not in out

    def test_render_no_color_codes_outside_tty(self, capsys) -> None:  # type: ignore[no-untyped-def]
        from goga.commands.usages.usages import render_status_report

        render_status_report(self._sample_report(), info=True)
        out = capsys.readouterr().out

        # capsys is not a TTY, so color is disabled and no ANSI escape codes leak.
        assert "\x1b[" not in out

    def test_marker_color_map_contract(self) -> None:
        """Only the changed markers carry a foreground color; ``[ ]`` is absent."""
        assert _usages_mod._MARKER_COLOR == {
            "[*]": "yellow",  # modified / out of date
            "[+]": "green",  # added / new
            "[-]": "red",  # removed
            "[!]": "magenta",  # error
        }
        assert "[ ]" not in _usages_mod._MARKER_COLOR

    def test_style_colors_only_changed_markers(self) -> None:
        """_style colors [*]/[+]/[-]/[!] when color is on, never [ ]."""
        from goga.commands.usages.usages import _style

        for marker in ("[*]", "[+]", "[-]", "[!]"):
            assert _style(marker, True) != marker  # ANSI-wrapped
        assert _style("[ ]", True) == "[ ]"  # unchanged stays plain
        # color off -> every marker is plain
        for marker in ("[*]", "[+]", "[-]", "[!]", "[ ]"):
            assert _style(marker, False) == marker


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
        assert result.output.index("libs/") < result.output.index("tools/")
        # deps rendered as tree nodes with markers mapped from their state
        assert "[ ] click/" in result.output  # up_to_date
        assert "[*] cli/" in result.output  # out_of_date
        # without --info, the per-node entry tree is not expanded
        assert "src/" not in result.output
        # CliRunner is not a TTY, so color is disabled and no ANSI codes leak
        assert "\x1b[" not in result.output

    def test_status_info_prints_entries_and_matches_exit_code(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ) -> None:
        """``--info`` expands each dep into its per-node entry tree (sorted); the CLI
        exit code equals the report's derived exit code."""
        click_repo, cli_repo = self._scenario(tmp_path, monkeypatch, make_repo, write_config)

        runner = CliRunner()
        with patch_clone({"https://x/click.git": click_repo, "https://x/cli.git": cli_repo}):
            report = status_logic()
            result = runner.invoke(app, ["usages", "status", "--info"])

        assert result.exit_code == report.exit_code == 1
        # --info expands the up_to_date click dep into its "src" folder tree
        assert "[ ] src/" in result.output
        assert "[ ] click.md" in result.output

    def test_app_usages_status_help_lists_options(self) -> None:
        """``status --help`` shows only ``--info`` (group/dep moved to the group)."""
        runner = CliRunner()
        result = runner.invoke(app, ["usages", "status", "--help"])

        assert result.exit_code == 0
        assert "--info" in result.output
        assert "--group" not in result.output
        assert "--dep" not in result.output

    def test_app_usages_group_help_lists_group_dep_options(self) -> None:
        """``--group``/``--dep`` appear in ``goga usages --help`` (group level)."""
        runner = CliRunner()
        result = runner.invoke(app, ["usages", "--help"])

        assert result.exit_code == 0
        assert "--group" in result.output
        assert "--dep" in result.output

    def test_app_usages_help_lists_status(self) -> None:
        """``goga usages --help`` lists the ``status`` subcommand."""
        runner = CliRunner()
        result = runner.invoke(app, ["usages", "--help"])

        assert result.exit_code == 0
        assert "status" in result.output


class TestUsagesGroupEndToEnd:
    """Whole-feature Part A integration: the real ``usages`` group drives the
    real ``sync_logic`` (config load -> filter loop -> clone + deploy) end-to-end
    via the click CLI, with the git boundary (``clone_repository``) and the
    filesystem side-effect of ``deploy_usages`` mocked. Exercises the
    ``goga usages --group G --dep D sync`` flow (only the matching ``(G,D)``
    pair is deployed) and the symmetric ``status`` path through the group
    context (call shape unchanged).
    """

    @staticmethod
    def _two_group_config() -> str:
        """Two-group, multi-dep usages block.

        ``libs`` carries ``click`` + ``common`` and ``apps`` carries ``common``,
        so a ``--group`` filter narrows to one group and a ``--dep`` filter
        crosses group boundaries.
        """
        return (
            "usages:\n"
            "  libs:\n"
            "    click:\n"
            "      git: https://x/click.git\n"
            "      ref: main\n"
            "    common:\n"
            "      git: https://x/common.git\n"
            "      ref: main\n"
            "  apps:\n"
            "    common:\n"
            "      git: https://x/common.git\n"
            "      ref: main\n"
        )

    def test_sync_group_dep_filter_deploys_only_matching_pair(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
    ) -> None:
        """``goga usages --group libs --dep click sync --force`` deploys ONLY
        ``libs/click`` — the real ``sync_logic`` filter loop runs through the
        group context, so the non-matching ``libs/common`` and ``apps/common``
        are skipped (never cloned or deployed)."""
        write_config(self._two_group_config())
        monkeypatch.chdir(tmp_path)

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()
        sync_mod = importlib.import_module("goga.usages.sync.sync")

        with (
            mock.patch.object(sync_mod, "clone_repository", return_value=fake_repo) as clone_mock,
            mock.patch.object(sync_mod, "deploy_usages") as deploy_mock,
        ):
            runner = CliRunner()
            result = runner.invoke(app, ["usages", "--group", "libs", "--dep", "click", "sync", "--force"])

        assert result.exit_code == 0
        # Only the matching (libs, click) pair is synced.
        clone_mock.assert_called_once_with("https://x/click.git", "main")
        deploy_mock.assert_called_once_with(fake_repo, Path(".goga/usages/libs/click"), None)

    def test_sync_dep_only_filter_applies_across_groups(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
    ) -> None:
        """``goga usages --dep common sync --force`` deploys ``common`` in every
        group (``libs/common`` AND ``apps/common``); ``libs/click`` is skipped."""
        write_config(self._two_group_config())
        monkeypatch.chdir(tmp_path)

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()
        sync_mod = importlib.import_module("goga.usages.sync.sync")

        with (
            mock.patch.object(sync_mod, "clone_repository", return_value=fake_repo) as clone_mock,
            mock.patch.object(sync_mod, "deploy_usages") as deploy_mock,
        ):
            runner = CliRunner()
            result = runner.invoke(app, ["usages", "--dep", "common", "sync", "--force"])

        assert result.exit_code == 0
        # ``common`` in both groups; every clone targets the common URL.
        assert clone_mock.call_count == 2
        assert {call.args for call in clone_mock.call_args_list} == {("https://x/common.git", "main")}
        deploy_targets = {call.args[1] for call in deploy_mock.call_args_list}
        assert deploy_targets == {Path(".goga/usages/libs/common"), Path(".goga/usages/apps/common")}

    def test_sync_no_filter_deploys_all(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
    ) -> None:
        """``goga usages sync --force`` (no filter) deploys every declared dep."""
        write_config(self._two_group_config())
        monkeypatch.chdir(tmp_path)

        fake_repo = tmp_path / "fake_clone"
        fake_repo.mkdir()
        sync_mod = importlib.import_module("goga.usages.sync.sync")

        with (
            mock.patch.object(sync_mod, "clone_repository", return_value=fake_repo) as clone_mock,
            mock.patch.object(sync_mod, "deploy_usages") as deploy_mock,
        ):
            runner = CliRunner()
            result = runner.invoke(app, ["usages", "sync", "--force"])

        assert result.exit_code == 0
        # All three deps deployed: libs/click, libs/common, apps/common.
        assert clone_mock.call_count == 3
        deploy_targets = {call.args[1] for call in deploy_mock.call_args_list}
        assert deploy_targets == {
            Path(".goga/usages/libs/click"),
            Path(".goga/usages/libs/common"),
            Path(".goga/usages/apps/common"),
        }

    def test_status_group_dep_filter_threaded_through_context(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ) -> None:
        """Symmetric Part A ``status`` path: ``goga usages --group G --dep D
        status`` threads the filters through the group context to the real
        ``status_logic`` (call shape ``(group, dep)`` unchanged). Only the
        matching dep is inspected.

        Builds two groups; pre-seeds every target so every dep resolves to a
        concrete state, then filters to ``libs/click`` and asserts only that
        dep appears in the rendered output.
        """
        click_repo = make_repo("click", {".usages/src/click.md": "C1"})
        common_repo = make_repo("common", {".usages/common.md": "COMMON"})
        write_config(self._two_group_config())
        monkeypatch.chdir(tmp_path)

        # Pre-seed every dep target to match its remote → all up_to_date.
        usages_root = tmp_path / ".goga" / "usages"
        for group, dep, rel, content in (
            ("libs", "click", "src/click.md", "C1"),
            ("libs", "common", "common.md", "COMMON"),
            ("apps", "common", "common.md", "COMMON"),
        ):
            target = usages_root / group / dep
            target.mkdir(parents=True, exist_ok=True)
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            (target / rel).write_text(content)

        runner = CliRunner()
        sources = {
            "https://x/click.git": click_repo,
            "https://x/common.git": common_repo,
        }
        with patch_clone(sources):
            result = runner.invoke(app, ["usages", "--group", "libs", "--dep", "click", "status"])

        assert result.exit_code == 0
        # Only the filtered libs/click dep is rendered; the others are excluded.
        assert "click/" in result.output
        assert "common/" not in result.output

    def test_status_no_filter_includes_all_groups(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_repo,
        write_config,
        patch_clone,
    ) -> None:
        """Symmetric Part A ``status`` path with no filter: both groups render."""
        click_repo = make_repo("click", {".usages/src/click.md": "C1"})
        common_repo = make_repo("common", {".usages/common.md": "COMMON"})
        write_config(self._two_group_config())
        monkeypatch.chdir(tmp_path)

        usages_root = tmp_path / ".goga" / "usages"
        for group, dep, rel, content in (
            ("libs", "click", "src/click.md", "C1"),
            ("libs", "common", "common.md", "COMMON"),
            ("apps", "common", "common.md", "COMMON"),
        ):
            target = usages_root / group / dep
            target.mkdir(parents=True, exist_ok=True)
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            (target / rel).write_text(content)

        runner = CliRunner()
        sources = {
            "https://x/click.git": click_repo,
            "https://x/common.git": common_repo,
        }
        with patch_clone(sources):
            result = runner.invoke(app, ["usages", "status"])

        assert result.exit_code == 0
        # Both groups render (sorted: apps before libs).
        assert "apps/" in result.output
        assert "libs/" in result.output
        assert result.output.index("apps/") < result.output.index("libs/")
