"""Contract and logic tests for the entity declared in
``goga/commands/topics/CODEMANIFEST`` with ``location: topics.py``:
the ``topics`` click group with the ``status``/``create``/``switch``
subcommands.

The group is a thin wrapper: the ``--year/-y`` option builds the scope every
subcommand shares, and each subcommand delegates its computation to the
``goga.topics`` domain — the board collection and rendering for ``status``,
the creation and switching procedures for ``create``/``switch``. The logic
tests mock the domain at its import site in the command module and drive
the CLI surface through ``CliRunner``; a pinned ``COLUMNS`` keeps the
measured terminal width deterministic.
"""

from __future__ import annotations

import inspect
import sys
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.commands.topics import render_topic_board, topics
from goga.topics import BoardRecord

# goga.commands.topics.topics is shadowed in the package __init__ by the
# topics click group, so attribute access through the package gives the
# group. Resolve the real module via sys.modules (precedent: test_history).
_topics_module = sys.modules["goga.commands.topics.topics"]
# The facade __all__ lives on the cell package itself.
_topics_facade = sys.modules["goga.commands.topics"]

# --- Contract tests ---


class TestTopicsGroupContract:
    def test_topics_importable_from_facade(self) -> None:
        """topics is importable from the goga.commands.topics facade."""
        assert _topics_module.topics is topics

    def test_facade_exports_two_names(self) -> None:
        """The cell facade carries the two declared names, alphabetically."""
        assert _topics_facade.__all__ == ["render_topic_board", "topics"]
        assert callable(topics)
        assert callable(render_topic_board)

    def test_topics_is_a_click_group(self) -> None:
        """topics is a click.Group container for the subcommands."""
        assert isinstance(topics, click.Group)

    def test_topics_registers_three_subcommands(self) -> None:
        """The group carries exactly the three declared subcommands."""
        assert sorted(topics.commands) == ["create", "status", "switch"]

    def test_topics_group_carries_the_year_option(self) -> None:
        """The group owns the shared --year/-y option, defaulting to None."""
        assert len(topics.params) == 1
        year_option = next(p for p in topics.params if isinstance(p, click.Option) and p.name == "year")
        assert "-y" in year_option.opts
        assert "--year" in year_option.opts
        assert year_option.default is None

    def test_topics_group_callback_signature(self) -> None:
        """``topics(ctx, year)`` — the context and the scoped year."""
        callback = topics.callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["ctx", "year"]
        assert signature.parameters["year"].default is None

    def test_scope_is_a_kw_only_dataclass_with_year(self) -> None:
        """``_TopicsScope`` is a kw_only dataclass carrying the year field."""
        scope = _topics_module._TopicsScope(year="2025")
        assert scope.year == "2025"
        assert _topics_module._TopicsScope().year is None

    def test_status_callback_signature(self) -> None:
        """``status(scope, remote=False)`` — the scope object and the flag."""
        callback = topics.commands["status"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["scope", "remote"]
        assert signature.parameters["remote"].default is False

    def test_status_carries_the_remote_flag(self) -> None:
        """status: --remote/-r flag, defaulting to False."""
        command = topics.commands["status"]
        remote_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "remote")
        assert "-r" in remote_option.opts
        assert "--remote" in remote_option.opts
        assert remote_option.is_flag is True
        assert remote_option.default is False

    def test_create_carries_the_name_positional(self) -> None:
        """create: the required branch_name positional."""
        command = topics.commands["create"]
        argument = next(p for p in command.params if isinstance(p, click.Argument) and p.name == "branch_name")
        assert argument.required is True

    def test_create_callback_signature(self) -> None:
        """``create(scope, branch_name)``."""
        callback = topics.commands["create"].callback
        assert list(inspect.signature(callback).parameters) == ["scope", "branch_name"]

    def test_switch_carries_the_identifier_positional(self) -> None:
        """switch: the required identifier positional."""
        command = topics.commands["switch"]
        argument = next(p for p in command.params if isinstance(p, click.Argument) and p.name == "identifier")
        assert argument.required is True

    def test_switch_callback_signature(self) -> None:
        """``switch(scope, identifier)``."""
        callback = topics.commands["switch"].callback
        assert list(inspect.signature(callback).parameters) == ["scope", "identifier"]


# --- Logic tests ---


class TestTopicsGroupSurface:
    def test_topics_group_help_and_year_scope(self) -> None:
        """--help lists the subcommands and --year/-y; the scope reaches the domain."""
        runner = CliRunner()
        result = runner.invoke(topics, ["--help"])
        assert result.exit_code == 0
        assert "Work with the topics of one year." in result.output
        for subcommand in ("status", "create", "switch"):
            assert subcommand in result.output
        assert "--year" in result.output
        assert "-y" in result.output

        with mock.patch.object(_topics_module, "create_topic") as mock_create:
            mock_create.return_value = "Created branch X and topic 2025/x"
            scoped = runner.invoke(topics, ["--year", "2025", "create", "X"])
        assert scoped.exit_code == 0
        mock_create.assert_called_once_with("X", "2025")

    @pytest.mark.parametrize("subcommand", ["status", "create", "switch"])
    def test_subcommand_help_follows_the_cli_docstring_rule(self, subcommand: str) -> None:
        """The rendered help carries no Args/Returns/Raises sections."""
        result = CliRunner().invoke(topics, [subcommand, "--help"])
        assert result.exit_code == 0
        assert result.output.strip() != ""
        for section in ("Args:", "Returns:", "Raises:"):
            assert section not in result.output

    def test_year_defaults_to_none_for_the_domain(self) -> None:
        """Without --year the subcommands hand the domain the current-year None."""
        with mock.patch.object(_topics_module, "create_topic") as mock_create:
            mock_create.return_value = "Created branch X and topic 2026/x"
            result = CliRunner().invoke(topics, ["create", "X"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("X", None)


class TestTopicsStatus:
    def test_status_collects_and_renders_the_board(self) -> None:
        """status hands the domain (scope.year, remote) and renders the records."""
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["planned"], current=True, remote=False),
        ]
        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=records) as mock_collect,
            mock.patch.dict("os.environ", {"COLUMNS": "100"}),
        ):
            result = CliRunner().invoke(topics, ["status"])
        assert result.exit_code == 0
        mock_collect.assert_called_once_with(None, False)
        assert "feat-a" in result.output
        assert "feat/a" in result.output
        assert "[planned]" in result.output
        assert "| Topic" in result.output

    def test_status_passes_the_year_and_the_remote_flag(self) -> None:
        """--year and --remote/-r reach the domain call verbatim."""
        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=[]) as mock_collect,
            mock.patch.dict("os.environ", {"COLUMNS": "100"}),
        ):
            result = CliRunner().invoke(topics, ["--year", "2025", "status", "--remote"])
        assert result.exit_code == 0
        mock_collect.assert_called_once_with("2025", True)

    def test_status_short_forms_bind_the_same_values(self) -> None:
        """-y and -r behave exactly like their long forms."""
        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=[]) as mock_collect,
            mock.patch.dict("os.environ", {"COLUMNS": "100"}),
        ):
            result = CliRunner().invoke(topics, ["-y", "2024", "status", "-r"])
        assert result.exit_code == 0
        mock_collect.assert_called_once_with("2024", True)

    def test_status_empty_board_prints_nothing_exit_zero(self) -> None:
        """An empty board is not an error — nothing on stdout, exit 0."""
        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=[]),
            mock.patch.dict("os.environ", {"COLUMNS": "100"}),
        ):
            result = CliRunner().invoke(topics, ["status"])
        assert result.exit_code == 0
        assert result.output == ""

    @pytest.mark.parametrize(("columns", "expected"), [(40, 40), (30, 33)])
    def test_status_measures_the_terminal_width(self, columns: int, expected: int) -> None:
        """The render width is the measured terminal width, not a constant."""
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["planned"], current=False, remote=False),
        ]
        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=records),
            mock.patch.dict("os.environ", {"COLUMNS": str(columns)}),
        ):
            result = CliRunner().invoke(topics, ["status"])
        assert result.exit_code == 0
        # Width 40 lays out in thirds — the table fits it exactly; width 30
        # is the documented ultra-narrow exception where the minimum 8/8/8
        # layout of 33 columns wins. Either way the measurement was taken.
        assert result.output.splitlines() != []
        assert all(len(line) == expected for line in result.output.splitlines())

    def test_status_domain_error_surfaces_clean(self) -> None:
        """A domain ClickException propagates as stderr + exit 1, no traceback."""
        with mock.patch.object(
            _topics_module,
            "collect_topic_board",
            side_effect=click.ClickException("no branch hosts 'x' — run 'goga topics status' to see the board"),
        ):
            result = CliRunner().invoke(topics, ["status"])
        assert result.exit_code == 1
        assert "no branch hosts" in result.stderr
        assert "Traceback" not in result.stderr
        assert result.stdout == ""


class TestTopicsCreateAndSwitch:
    def test_create_echoes_the_domain_result_line(self) -> None:
        """create echoes the single result line and exits 0."""
        with mock.patch.object(
            _topics_module,
            "create_topic",
            return_value="Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar",
        ) as mock_create:
            result = CliRunner().invoke(topics, ["create", "Feature/Foo_Bar"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("Feature/Foo_Bar", None)
        assert result.output.splitlines() == ["Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"]

    def test_switch_echoes_the_domain_result_line(self) -> None:
        """switch echoes the single result line and exits 0."""
        with mock.patch.object(
            _topics_module,
            "switch_topic",
            return_value="Switched to branch feat/a",
        ) as mock_switch:
            result = CliRunner().invoke(topics, ["switch", "feat-a"])
        assert result.exit_code == 0
        mock_switch.assert_called_once_with("feat-a", None)
        assert result.output.splitlines() == ["Switched to branch feat/a"]

    def test_switch_receives_the_scoped_year(self) -> None:
        """--year reaches switch_topic verbatim."""
        with mock.patch.object(_topics_module, "switch_topic", return_value="Already on branch feat/a") as mock_switch:
            result = CliRunner().invoke(topics, ["--year", "2025", "switch", "feat-a"])
        assert result.exit_code == 0
        mock_switch.assert_called_once_with("feat-a", "2025")
        assert result.output.splitlines() == ["Already on branch feat/a"]

    @pytest.mark.parametrize(("subcommand", "argument"), [("create", "branch_name"), ("switch", "identifier")])
    def test_missing_positional_is_usage_error(self, subcommand: str, argument: str) -> None:
        """A missing positional is click's own usage error — exit 2, no domain call."""
        with (
            mock.patch.object(_topics_module, "create_topic") as mock_create,
            mock.patch.object(_topics_module, "switch_topic") as mock_switch,
        ):
            result = CliRunner().invoke(topics, [subcommand])
        assert result.exit_code == 2
        assert argument.upper() in result.output
        mock_create.assert_not_called()
        mock_switch.assert_not_called()

    @pytest.mark.parametrize(("subcommand", "routine"), [("create", "create_topic"), ("switch", "switch_topic")])
    def test_domain_error_surfaces_clean(self, subcommand: str, routine: str) -> None:
        """A domain ClickException propagates as stderr + exit 1, no traceback."""
        with mock.patch.object(_topics_module, routine, side_effect=click.ClickException("working tree is dirty")):
            result = CliRunner().invoke(topics, [subcommand, "x"])
        assert result.exit_code == 1
        assert "working tree is dirty" in result.stderr
        assert "Traceback" not in result.stderr
        assert result.stdout == ""
