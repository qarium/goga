"""Contract and logic tests for the entity declared in
``goga/commands/topics/CODEMANIFEST`` with ``location: topics.py``:
the ``topics`` click group with the ``board``/``create``/``switch``/
``delete`` subcommands.

The group is a thin wrapper: the ``--year/-y`` option builds the scope
every subcommand shares, and each subcommand delegates its computation
to the ``goga.topics`` domain — the board collection and rendering for
``board`` (the ``--info/-i`` flag adds the todo column to the rendered
table), the creation and switching procedures for ``create``/``switch``
(``--todo/-t`` is a plain value option whose empty value counts as
absent; the editor entry itself belongs to the domain), and the
resolution plus confirmed removal for ``delete`` (one confirmation for
the whole list). The creation inputs resolve at this layer: the base —
``--base-ref``, the ``topics`` section of ``.goga/config.yml``,
``--from-current`` — and the message template — ``--commit/-c``, the
``topics`` section, the domain default — the configuration being read
lazily, only for values no flag provided. The logic tests mock the
domain at its import site in the command module and drive the CLI
surface through ``CliRunner``; a pinned ``COLUMNS`` keeps the measured
terminal width deterministic, and the configuration cases run against a
``tmp_path`` cwd.
"""

from __future__ import annotations

import inspect
import io
import os
import shutil
import sys
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.commands.topics import render_topic_board, topics
from goga.topics import BoardRecord, DeleteTarget

# goga.commands.topics.topics is shadowed in the package __init__ by the
# topics click group, so attribute access through the package gives the
# group. Resolve the real module via sys.modules (precedent: test_history).
_topics_module = sys.modules["goga.commands.topics.topics"]
# The facade __all__ lives on the cell package itself.
_topics_facade = sys.modules["goga.commands.topics"]


class _TtyStdin(io.BytesIO):
    """A CliRunner input whose isatty() is True — models the confirm gate's terminal.

    CliRunner's isolation replaces ``sys.stdin`` around every invoke, so a
    patched ``sys.stdin`` never survives into the command; an ``input=``
    stream does — click accepts it as the binary reader directly and the
    TextIOWrapper it builds delegates ``isatty()`` to it.
    """

    def isatty(self) -> bool:
        return True


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

    def test_topics_registers_four_subcommands(self) -> None:
        """The group carries exactly the four declared subcommands."""
        assert sorted(topics.commands) == ["board", "create", "delete", "switch"]

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

    def test_board_callback_signature(self) -> None:
        """``board(scope, remote=False, info=False)`` — the scope object and the flags."""
        callback = topics.commands["board"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["scope", "remote", "info"]
        assert signature.parameters["remote"].default is False
        assert signature.parameters["info"].default is False

    def test_board_carries_the_remote_flag(self) -> None:
        """board: --remote/-r flag, defaulting to False."""
        command = topics.commands["board"]
        remote_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "remote")
        assert "-r" in remote_option.opts
        assert "--remote" in remote_option.opts
        assert remote_option.is_flag is True
        assert remote_option.default is False

    def test_board_carries_the_info_flag(self) -> None:
        """board: --info/-i flag, defaulting to False."""
        command = topics.commands["board"]
        info_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "info")
        assert "-i" in info_option.opts
        assert "--info" in info_option.opts
        assert info_option.is_flag is True
        assert info_option.default is False

    def test_create_carries_the_name_positional(self) -> None:
        """create: the required branch_name positional."""
        command = topics.commands["create"]
        argument = next(p for p in command.params if isinstance(p, click.Argument) and p.name == "branch_name")
        assert argument.required is True

    def test_create_todo_option_surface(self) -> None:
        """create: --todo/-t is a plain value option — no optional-value flag."""
        command = topics.commands["create"]
        todo_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "todo")
        assert "-t" in todo_option.opts
        assert "--todo" in todo_option.opts
        assert todo_option.is_flag is False
        assert todo_option.default is None
        # No optional-value flag: a value-less --todo is a usage error, not
        # an entry marker (click keeps an UNSET sentinel here, not a value).
        assert not todo_option.secondary_opts

    def test_create_carries_the_publish_flag(self) -> None:
        """create: --publish/-p flag, defaulting to False."""
        command = topics.commands["create"]
        publish_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "publish")
        assert "-p" in publish_option.opts
        assert "--publish" in publish_option.opts
        assert publish_option.is_flag is True
        assert publish_option.default is False

    def test_create_carries_the_base_ref_option(self) -> None:
        """create: --base-ref option, long form only, defaulting to None."""
        command = topics.commands["create"]
        base_ref_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "base_ref")
        assert base_ref_option.opts == ["--base-ref"]
        assert base_ref_option.is_flag is False
        assert base_ref_option.default is None

    def test_create_carries_the_from_current_flag(self) -> None:
        """create: --from-current flag, long form only, defaulting to False."""
        command = topics.commands["create"]
        from_current_option = next(
            p for p in command.params if isinstance(p, click.Option) and p.name == "from_current"
        )
        assert from_current_option.opts == ["--from-current"]
        assert from_current_option.is_flag is True
        assert from_current_option.default is False

    def test_create_carries_the_commit_option_with_the_explicit_param_name(self) -> None:
        """create: --commit/-c bound to the param name ``commit_message``."""
        command = topics.commands["create"]
        commit_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "commit_message")
        assert commit_option.opts == ["--commit", "-c"]
        assert commit_option.is_flag is False
        assert commit_option.default is None

    def test_create_callback_signature(self) -> None:
        """``create(scope, branch_name, todo, publish, base_ref, from_current, commit_message)``."""
        callback = topics.commands["create"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == [
            "scope",
            "branch_name",
            "todo",
            "publish",
            "base_ref",
            "from_current",
            "commit_message",
        ]
        assert signature.parameters["todo"].default is None
        assert signature.parameters["publish"].default is False
        assert signature.parameters["base_ref"].default is None
        assert signature.parameters["from_current"].default is False
        assert signature.parameters["commit_message"].default is None

    def test_switch_carries_the_identifier_positional(self) -> None:
        """switch: the required identifier positional."""
        command = topics.commands["switch"]
        argument = next(p for p in command.params if isinstance(p, click.Argument) and p.name == "identifier")
        assert argument.required is True

    def test_switch_carries_the_todo_flag(self) -> None:
        """switch: --todo flag, long form only, defaulting to False."""
        command = topics.commands["switch"]
        todo_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "todo")
        assert todo_option.opts == ["--todo"]
        assert todo_option.is_flag is True
        assert todo_option.default is False

    def test_switch_callback_signature(self) -> None:
        """``switch(scope, identifier, todo=False)``."""
        callback = topics.commands["switch"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["scope", "identifier", "todo"]
        assert signature.parameters["todo"].default is False

    def test_delete_carries_the_identifiers_positionals(self) -> None:
        """delete: the required variadic identifiers positional."""
        command = topics.commands["delete"]
        argument = next(p for p in command.params if isinstance(p, click.Argument) and p.name == "identifiers")
        assert argument.required is True
        assert argument.nargs == -1

    def test_delete_carries_the_yes_flag(self) -> None:
        """delete: --yes/-y flag, defaulting to False."""
        command = topics.commands["delete"]
        yes_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "yes")
        assert "-y" in yes_option.opts
        assert "--yes" in yes_option.opts
        assert yes_option.is_flag is True
        assert yes_option.default is False

    def test_delete_callback_signature(self) -> None:
        """``delete(scope, identifiers, yes=False)``."""
        callback = topics.commands["delete"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["scope", "identifiers", "yes"]
        assert signature.parameters["yes"].default is False

    def test_prompt_multiline_and_default_publish_commit_are_gone(self) -> None:
        """The abolished CLI-layer entry, template constant, and publish edge no longer exist."""
        assert not hasattr(_topics_module, "_prompt_multiline")
        assert not hasattr(_topics_module, "_DEFAULT_PUBLISH_COMMIT")
        assert not hasattr(_topics_module, "publish_topic")


# --- Logic tests ---


class TestTopicsGroupSurface:
    def test_topics_group_help_and_year_scope(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--help lists the subcommands and --year/-y; the scope reaches the domain."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(topics, ["--help"])
        assert result.exit_code == 0
        assert "Work with the topics of one year." in result.output
        for subcommand in ("board", "create", "switch", "delete"):
            assert subcommand in result.output
        assert "--year" in result.output
        assert "-y" in result.output

        with mock.patch.object(_topics_module, "create_topic") as mock_create:
            mock_create.return_value = "Created branch X and topic 2025/x"
            scoped = runner.invoke(topics, ["--year", "2025", "create", "X", "--from-current"])
        assert scoped.exit_code == 0
        mock_create.assert_called_once_with("X", "HEAD", None, False, None, "2025")

    @pytest.mark.parametrize("subcommand", ["board", "create", "switch", "delete"])
    def test_subcommand_help_follows_the_cli_docstring_rule(self, subcommand: str) -> None:
        """The rendered help carries no Args/Returns/Raises sections."""
        result = CliRunner().invoke(topics, [subcommand, "--help"])
        assert result.exit_code == 0
        assert result.output.strip() != ""
        for section in ("Args:", "Returns:", "Raises:"):
            assert section not in result.output

    def test_create_help_lists_the_new_flags(self) -> None:
        """create --help lists --todo/-t, --publish/-p, --base-ref, --from-current, and --commit/-c."""
        result = CliRunner().invoke(topics, ["create", "--help"])
        assert result.exit_code == 0
        assert "--todo" in result.output
        assert "-t" in result.output
        assert "--publish" in result.output
        assert "-p" in result.output
        assert "--base-ref" in result.output
        assert "--from-current" in result.output
        assert "--commit" in result.output
        assert "-c" in result.output

    def test_delete_help_lists_the_surface(self) -> None:
        """delete --help lists --yes/-y and the IDENTIFIERS argument."""
        result = CliRunner().invoke(topics, ["delete", "--help"])
        assert result.exit_code == 0
        assert "--yes" in result.output
        assert "-y" in result.output
        assert "IDENTIFIERS" in result.output

    def test_year_defaults_to_none_for_the_domain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without --year the subcommands hand the domain the current-year None."""
        monkeypatch.chdir(tmp_path)

        with mock.patch.object(_topics_module, "create_topic") as mock_create:
            mock_create.return_value = "Created branch X and topic 2026/x"
            result = CliRunner().invoke(topics, ["create", "X", "--from-current"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("X", "HEAD", None, False, None, None)


class TestTopicsBoard:
    def test_board_collects_and_renders_the_board(self) -> None:
        """board hands the domain (scope.year, remote) and renders the records."""
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["planned"], current=True, remote=False),
        ]

        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=records) as mock_collect,
            mock.patch.dict("os.environ", {"COLUMNS": "100"}),
        ):
            result = CliRunner().invoke(topics, ["board"])
        assert result.exit_code == 0
        mock_collect.assert_called_once_with(None, False)
        assert "feat-a" in result.output
        assert "feat/a" in result.output
        assert "[planned]" in result.output
        assert "| Topic" in result.output

    def test_board_passes_the_year_and_the_remote_flag(self) -> None:
        """--year and --remote/-r reach the domain call verbatim."""
        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=[]) as mock_collect,
            mock.patch.dict("os.environ", {"COLUMNS": "100"}),
        ):
            result = CliRunner().invoke(topics, ["--year", "2025", "board", "--remote"])
        assert result.exit_code == 0
        mock_collect.assert_called_once_with("2025", True)

    def test_board_short_forms_bind_the_same_values(self) -> None:
        """-y and -r behave exactly like their long forms."""
        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=[]) as mock_collect,
            mock.patch.dict("os.environ", {"COLUMNS": "100"}),
        ):
            result = CliRunner().invoke(topics, ["-y", "2024", "board", "-r"])
        assert result.exit_code == 0
        mock_collect.assert_called_once_with("2024", True)

    def test_topics_board_info_flag_reaches_renderer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--info reaches the renderer — the table gains the todo column."""
        records = [
            BoardRecord(
                topic="feat-a",
                branch="feat/a",
                statuses=["planned"],
                current=True,
                remote=False,
                todo="Payment retry",
            ),
        ]
        # The lambda tolerates any caller signature: pytest's own terminal
        # writer probes the width with ``fallback=`` while the patch is live,
        # and a zero-arg patch aborts the run as an INTERNALERROR.
        monkeypatch.setattr(shutil, "get_terminal_size", lambda *_args, **_kwargs: os.terminal_size((100, 24)))

        with mock.patch.object(_topics_module, "collect_topic_board", return_value=records):
            result = CliRunner().invoke(topics, ["board", "--info"])
        assert result.exit_code == 0
        header = result.output.splitlines()[0]
        assert "todo" in header
        assert "Topic" in header
        assert "Branch" in header
        assert "Statuses" in header
        assert "Payment retry" in result.output

    def test_topics_board_info_short_form_binds_the_same_table(self) -> None:
        """-i renders the same four-column table as --info."""
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["planned"], current=False, remote=False, todo="T"),
        ]

        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=records),
            mock.patch.dict("os.environ", {"COLUMNS": "100"}),
        ):
            short = CliRunner().invoke(topics, ["board", "-i"])
            long = CliRunner().invoke(topics, ["board", "--info"])
        assert short.exit_code == 0
        assert long.exit_code == 0
        assert short.output == long.output
        assert "todo" in short.output.splitlines()[0]

    def test_board_empty_board_prints_nothing_exit_zero(self) -> None:
        """An empty board is not an error — nothing on stdout, exit 0."""
        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=[]),
            mock.patch.dict("os.environ", {"COLUMNS": "100"}),
        ):
            result = CliRunner().invoke(topics, ["board"])
        assert result.exit_code == 0
        assert result.output == ""

    @pytest.mark.parametrize(("columns", "expected"), [(40, 40), (30, 33)])
    def test_board_measures_the_terminal_width(self, columns: int, expected: int) -> None:
        """The render width is the measured terminal width, not a constant."""
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["planned"], current=False, remote=False),
        ]

        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=records),
            mock.patch.dict("os.environ", {"COLUMNS": str(columns)}),
        ):
            result = CliRunner().invoke(topics, ["board"])
        assert result.exit_code == 0
        # Width 40 lays out in thirds — the table fits it exactly; width 30
        # is the documented ultra-narrow exception where the minimum 8/8/8
        # layout of 33 columns wins. Either way the measurement was taken.
        assert result.output.splitlines() != []
        assert all(len(line) == expected for line in result.output.splitlines())

    def test_board_domain_error_surfaces_clean(self) -> None:
        """A domain ClickException propagates as stderr + exit 1, no traceback."""
        with mock.patch.object(
            _topics_module,
            "collect_topic_board",
            side_effect=click.ClickException("no branch hosts 'x' — run 'goga topics board' to see the board"),
        ):
            result = CliRunner().invoke(topics, ["board"])
        assert result.exit_code == 1
        assert "no branch hosts" in result.stderr
        assert "Traceback" not in result.stderr
        assert result.stdout == ""


def _write_config(tmp_path: Path, body: str) -> None:
    """Write ``.goga/config.yml`` with the given body under tmp_path."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(exist_ok=True)
    (goga_dir / "config.yml").write_text(body, encoding="utf-8")


class TestTopicsCreateAndSwitch:
    def test_create_echoes_the_domain_result_line(self) -> None:
        """create echoes the single result line and exits 0."""
        with mock.patch.object(
            _topics_module,
            "create_topic",
            return_value="Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar",
        ) as mock_create:
            result = CliRunner().invoke(topics, ["create", "Feature/Foo_Bar", "--base-ref", "origin/main"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("Feature/Foo_Bar", "origin/main", None, False, None, None)
        assert result.output.splitlines() == ["Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"]

    def test_topics_create_todo_option_reaches_domain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """-t hands the domain (name, HEAD, todo, publish, template, year) verbatim."""
        monkeypatch.chdir(tmp_path)

        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            result = CliRunner().invoke(topics, ["create", "Feature/Foo_Bar", "--from-current", "-t", "Payment retry"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("Feature/Foo_Bar", "HEAD", "Payment retry", False, None, None)
        assert result.output == "line\n"

    def test_topics_create_todo_long_form_binds_the_same_value(self) -> None:
        """--todo behaves exactly like -t."""
        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            result = CliRunner().invoke(topics, ["create", "feat-a", "--base-ref", "origin/main", "--todo", "T"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("feat-a", "origin/main", "T", False, None, None)
        assert result.output == "line\n"

    @pytest.mark.parametrize(
        "flag_form",
        [["--todo", "Payment retry"], ["--todo=Payment retry"], ["-t", "Payment retry"], ["-tPayment retry"]],
    )
    def test_create_flag_with_value_passes_todo(self, flag_form: list[str]) -> None:
        """Every flag form carrying a value hands the domain the todo verbatim."""
        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            result = CliRunner().invoke(topics, ["create", "feat-a", "--base-ref", "origin/main", *flag_form])
        assert result.exit_code == 0
        assert mock_create.call_args == mock.call("feat-a", "origin/main", "Payment retry", False, None, None)

    def test_create_empty_todo_value_counts_as_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An explicitly empty --todo value is None at the call — never an entry marker.

        The CliRunner stdin is never a TTY, which is the point: without a
        value option there is no CLI-side entry that could need one.
        """
        monkeypatch.chdir(tmp_path)

        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            result = CliRunner().invoke(topics, ["create", "feat-a", "--from-current", "--todo", ""])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("feat-a", "HEAD", None, False, None, None)

    @pytest.mark.parametrize("flag_form", [["--todo"], ["-t"]])
    def test_create_bare_todo_flag_is_usage_error(self, flag_form: list[str]) -> None:
        """A value-less --todo is click's own usage error — no optional-value flag reappears."""
        with mock.patch.object(_topics_module, "create_topic") as mock_create:
            result = CliRunner().invoke(topics, ["create", "feat-a", "--base-ref", "origin/main", *flag_form])
        assert result.exit_code == 2
        assert "requires an argument" in result.output
        mock_create.assert_not_called()

    def test_switch_echoes_the_domain_result_line(self) -> None:
        """switch echoes the single result line and exits 0."""
        with mock.patch.object(
            _topics_module,
            "switch_topic",
            return_value="Switched to branch feat/a",
        ) as mock_switch:
            result = CliRunner().invoke(topics, ["switch", "feat-a"])
        assert result.exit_code == 0
        mock_switch.assert_called_once_with("feat-a", False, None)
        assert result.output.splitlines() == ["Switched to branch feat/a"]

    def test_switch_receives_the_scoped_year(self) -> None:
        """--year reaches switch_topic verbatim."""
        with mock.patch.object(_topics_module, "switch_topic", return_value="Already on branch feat/a") as mock_switch:
            result = CliRunner().invoke(topics, ["--year", "2025", "switch", "feat-a"])
        assert result.exit_code == 0
        mock_switch.assert_called_once_with("feat-a", False, "2025")
        assert result.output.splitlines() == ["Already on branch feat/a"]

    @pytest.mark.parametrize(
        ("argv", "argument"),
        [
            (["create"], "branch_name"),
            (["switch"], "identifier"),
            (["delete"], "identifiers"),
        ],
    )
    def test_missing_positional_is_usage_error(self, argv: list[str], argument: str) -> None:
        """A missing positional is click's own usage error — exit 2, no domain call."""
        with (
            mock.patch.object(_topics_module, "create_topic") as mock_create,
            mock.patch.object(_topics_module, "switch_topic") as mock_switch,
            mock.patch.object(_topics_module, "resolve_delete_targets") as mock_resolve,
        ):
            result = CliRunner().invoke(topics, argv)
        assert result.exit_code == 2
        assert argument.upper() in result.output
        mock_create.assert_not_called()
        mock_switch.assert_not_called()
        mock_resolve.assert_not_called()

    @pytest.mark.parametrize(
        ("argv", "routine"),
        [
            (["create", "x", "--base-ref", "origin/main"], "create_topic"),
            (["switch", "x"], "switch_topic"),
        ],
    )
    def test_domain_error_surfaces_clean(self, argv: list[str], routine: str) -> None:
        """A domain ClickException propagates as stderr + exit 1, no traceback."""
        with mock.patch.object(_topics_module, routine, side_effect=click.ClickException("working tree is dirty")):
            result = CliRunner().invoke(topics, argv)
        assert result.exit_code == 1
        assert "working tree is dirty" in result.stderr
        assert "Traceback" not in result.stderr
        assert result.stdout == ""


class TestTopicsCreateBaseResolution:
    def test_create_base_ref_flag_beats_config_beats_from_current(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The base matrix: --base-ref beats topics.base_ref beats --from-current."""
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            "language: python\ntopics:\n  base_ref: origin/config-base\n  publish_commit: cfg tpl\n",
        )

        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            flag_base = CliRunner().invoke(topics, ["create", "n1", "--base-ref", "origin/flag-base"])
            config_base = CliRunner().invoke(topics, ["create", "n2"])
        assert flag_base.exit_code == 0
        assert config_base.exit_code == 0
        # n1: the base flag wins; the template still comes from the config.
        assert mock_create.call_args_list[0] == mock.call("n1", "origin/flag-base", None, False, "cfg tpl", None)
        assert mock_create.call_args_list[1] == mock.call("n2", "origin/config-base", None, False, "cfg tpl", None)

        # A config without topics.base_ref: --from-current yields the HEAD.
        _write_config(tmp_path, "language: python\n")

        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            from_current = CliRunner().invoke(topics, ["create", "n3", "--from-current"])
        assert from_current.exit_code == 0
        assert mock_create.call_args == mock.call("n3", "HEAD", None, False, None, None)

        # A --commit flag beats the config template (publication-only, so
        # under --publish).
        _write_config(
            tmp_path,
            "language: python\ntopics:\n  base_ref: origin/config-base\n  publish_commit: cfg tpl\n",
        )

        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            flag_template = CliRunner().invoke(topics, ["create", "n4", "--publish", "-t", "T", "--commit", "x {slug}"])
        assert flag_template.exit_code == 0
        assert mock_create.call_args == mock.call("n4", "origin/config-base", "T", True, "x {slug}", None)

        # A missing configuration file counts as unset — the lazy read
        # tolerates it and --from-current still yields the HEAD.
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            missing = CliRunner().invoke(topics, ["create", "n5", "--from-current"])
        assert missing.exit_code == 0
        assert mock_create.call_args == mock.call("n5", "HEAD", None, False, None, None)

    def test_create_no_base_clean_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Nothing set: the error names --base-ref, --from-current, and the config line."""
        monkeypatch.chdir(tmp_path)

        with mock.patch.object(_topics_module, "create_topic") as mock_create:
            result = CliRunner().invoke(topics, ["create", "name"])
        assert result.exit_code == 1
        assert "--base-ref" in result.stderr
        assert "--from-current" in result.stderr
        assert "topics.base_ref" in result.stderr
        assert "Traceback" not in result.stderr
        mock_create.assert_not_called()

    def test_create_from_current_passes_head(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--from-current passes the literal string HEAD — no CLI-side resolution."""
        monkeypatch.chdir(tmp_path)

        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            result = CliRunner().invoke(topics, ["create", "name", "--from-current"])
        assert result.exit_code == 0
        assert mock_create.call_args.args[1] == "HEAD"

    def test_create_commit_without_publish_error(self) -> None:
        """--commit without --publish is a clean error; --base-ref alone is not."""
        with mock.patch.object(_topics_module, "create_topic") as mock_create:
            result = CliRunner().invoke(topics, ["create", "--base-ref", "origin/main", "--commit", "x", "name"])
        assert result.exit_code == 1
        assert "--commit" in result.stderr
        assert "publication-only" in result.stderr
        mock_create.assert_not_called()

        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            base_alone = CliRunner().invoke(topics, ["create", "--base-ref", "origin/main", "name"])
        assert base_alone.exit_code == 0
        mock_create.assert_called_once_with("name", "origin/main", None, False, None, None)

    def test_create_both_values_given_reads_no_configuration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both --base-ref and --commit given: the flag values win and no config read happens."""
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            "language: python\ntopics:\n  base_ref: origin/config-base\n  publish_commit: 'config: {slug}'\n",
        )

        with (
            mock.patch.object(_topics_module, "load_project_config") as mock_load,
            mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create,
        ):
            result = CliRunner().invoke(
                topics,
                [
                    "create",
                    "Feature/Foo_Bar",
                    "--publish",
                    "-t",
                    "T",
                    "--base-ref",
                    "origin/flag-base",
                    "--commit",
                    "flag: {slug}",
                ],
            )
        assert result.exit_code == 0
        mock_create.assert_called_once_with("Feature/Foo_Bar", "origin/flag-base", "T", True, "flag: {slug}", None)
        mock_load.assert_not_called()

    def test_create_publish_config_template_beats_domain_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``topics.publish_commit`` wins over the domain default template."""
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            "language: python\ntopics:\n  base_ref: origin/config-base\n  publish_commit: 'config: {slug}'\n",
        )

        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            result = CliRunner().invoke(topics, ["create", "X", "--publish", "-t", "T"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("X", "origin/config-base", "T", True, "config: {slug}", None)

    def test_create_publish_no_template_anywhere_passes_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No --commit and no topics.publish_commit: the template is None — the domain default."""
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, "language: python\ntopics:\n  base_ref: origin/config-base\n")

        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            result = CliRunner().invoke(topics, ["create", "X", "--publish", "-t", "T"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("X", "origin/config-base", "T", True, None, None)

    def test_create_publish_flag_template_with_config_base(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A config base with a flag template — the flag template wins."""
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, "language: python\ntopics:\n  base_ref: origin/config-base\n")

        with (
            mock.patch.object(
                _topics_module, "load_project_config", wraps=_topics_module.load_project_config
            ) as mock_load,
            mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create,
        ):
            result = CliRunner().invoke(topics, ["create", "X", "--publish", "-t", "T", "--commit", "flag: {slug}"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("X", "origin/config-base", "T", True, "flag: {slug}", None)
        # The base flag is absent, so the config is read for it.
        mock_load.assert_called_once_with()

    def test_create_publish_delegation(self) -> None:
        """The publish path delegates through create_topic with publish=True."""
        with mock.patch.object(
            _topics_module,
            "create_topic",
            return_value="Created branch X and published topic 2026/x",
        ) as mock_create:
            result = CliRunner().invoke(topics, ["create", "X", "--publish", "-t", "T", "--base-ref", "origin/main"])
        assert result.exit_code == 0
        assert mock_create.call_args == mock.call("X", "origin/main", "T", True, None, None)
        assert result.output == "Created branch X and published topic 2026/x\n"

    def test_create_invalid_config_surfaces_its_own_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A malformed topics section surfaces the loader's error, not a 'no base' guess."""
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, "language: python\ntopics: 5\n")

        with mock.patch.object(_topics_module, "create_topic") as mock_create:
            result = CliRunner().invoke(topics, ["create", "X", "--from-current"])
        assert result.exit_code == 1
        assert "'topics' must be a mapping in .goga/config.yml" in result.stderr
        mock_create.assert_not_called()

    def test_create_unreadable_config_surfaces_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unreadable configuration file (a directory in its place)
        surfaces one clean error — not a raw IsADirectoryError traceback, and
        not the 'no base' guess either.
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga").mkdir()
        (tmp_path / ".goga" / "config.yml").mkdir()

        with mock.patch.object(_topics_module, "create_topic") as mock_create:
            result = CliRunner().invoke(topics, ["create", "X", "--from-current"])
        assert result.exit_code == 1
        assert "Is a directory" in result.stderr
        assert not isinstance(result.exception, IsADirectoryError)
        mock_create.assert_not_called()


class TestTopicsSwitchTodo:
    def test_switch_todo_flag_forwarded(self) -> None:
        """--todo forwards the flag verbatim to switch_topic."""
        with mock.patch.object(
            _topics_module,
            "switch_topic",
            return_value="Switched to branch feature-foo",
        ) as mock_switch:
            result = CliRunner().invoke(topics, ["switch", "feature-foo", "--todo"])
        assert result.exit_code == 0
        mock_switch.assert_called_once_with("feature-foo", True, None)
        assert result.output.splitlines() == ["Switched to branch feature-foo"]

    def test_switch_todo_with_scoped_year(self) -> None:
        """--todo and --year travel together to the domain."""
        with mock.patch.object(_topics_module, "switch_topic", return_value="line") as mock_switch:
            result = CliRunner().invoke(topics, ["--year", "2025", "switch", "feature-foo", "--todo"])
        assert result.exit_code == 0
        mock_switch.assert_called_once_with("feature-foo", True, "2025")


class TestTopicsDelete:
    def test_delete_confirmed_delegates_and_echoes(self) -> None:
        """A confirmed list prints the pairs, asks once, delegates with a list, echoes the line."""
        targets = [
            DeleteTarget(topic="feature-foo", branch="feature-foo", remote="feature-foo", has_dir=True),
            DeleteTarget(topic="release-1-3-0", branch=None, remote=None, has_dir=True),
        ]

        with (
            mock.patch.object(click, "confirm", return_value=True) as mock_confirm,
            mock.patch.object(_topics_module, "resolve_delete_targets", return_value=targets) as mock_resolve,
            mock.patch.object(
                _topics_module,
                "delete_topics",
                return_value="Deleted 2 topic(s) of 2026: feature-foo, release-1-3-0",
            ) as mock_delete,
        ):
            result = CliRunner().invoke(topics, ["delete", "feature-foo", "release-1-3-0"], input=_TtyStdin())
        assert result.exit_code == 0
        # The click nargs=-1 tuple becomes a list at the boundary.
        mock_resolve.assert_called_once_with(["feature-foo", "release-1-3-0"], None)
        # One confirmation for the whole list — never per topic.
        mock_confirm.assert_called_once_with("Delete 2 topic(s)?")
        mock_delete.assert_called_once_with(targets, None)
        assert "feature-foo -> feature-foo" in result.output
        assert "release-1-3-0 -> (directory only)" in result.output
        assert "Deleted 2 topic(s) of 2026: feature-foo, release-1-3-0" in result.output

    def test_delete_declined_confirmation_exits_zero(self) -> None:
        """A declined confirmation exits 0 with nothing deleted."""
        targets = [DeleteTarget(topic="feature-foo", branch="feature-foo", remote=None, has_dir=True)]

        with (
            mock.patch.object(click, "confirm", return_value=False) as mock_confirm,
            mock.patch.object(_topics_module, "resolve_delete_targets", return_value=targets) as mock_resolve,
            mock.patch.object(_topics_module, "delete_topics") as mock_delete,
        ):
            result = CliRunner().invoke(topics, ["delete", "feature-foo"], input=_TtyStdin())
        assert result.exit_code == 0
        mock_confirm.assert_called_once_with("Delete 1 topic(s)?")
        mock_resolve.assert_called_once_with(["feature-foo"], None)
        mock_delete.assert_not_called()
        assert "Deleted" not in result.output

    def test_delete_requires_terminal_without_yes(self) -> None:
        """A non-TTY without --yes is a clean error — after the read-only resolution."""
        targets = [DeleteTarget(topic="feature-foo", branch="feature-foo", remote=None, has_dir=True)]

        with (
            mock.patch.object(click, "confirm") as mock_confirm,
            mock.patch.object(_topics_module, "resolve_delete_targets", return_value=targets) as mock_resolve,
            mock.patch.object(_topics_module, "delete_topics") as mock_delete,
        ):
            result = CliRunner().invoke(topics, ["delete", "feature-foo"])
        assert result.exit_code == 1
        assert "interactive terminal" in result.stderr
        assert "Traceback" not in result.stderr
        mock_resolve.assert_called_once_with(["feature-foo"], None)
        mock_confirm.assert_not_called()
        mock_delete.assert_not_called()

    def test_delete_yes_short_form_scoped_to_subcommand(self) -> None:
        """``topics -y 2025 delete -y x``: the group -y binds the year, the subcommand -y the skip."""
        targets = [DeleteTarget(topic="feature-foo", branch="feature-foo", remote="feature-foo", has_dir=True)]

        with (
            mock.patch.object(click, "confirm") as mock_confirm,
            mock.patch.object(_topics_module, "resolve_delete_targets", return_value=targets) as mock_resolve,
            mock.patch.object(
                _topics_module, "delete_topics", return_value="Deleted 1 topic(s) of 2025: feature-foo"
            ) as mock_delete,
        ):
            result = CliRunner().invoke(topics, ["-y", "2025", "delete", "-y", "feature-foo"])
        assert result.exit_code == 0
        mock_resolve.assert_called_once_with(["feature-foo"], "2025")
        mock_confirm.assert_not_called()
        mock_delete.assert_called_once_with(targets, "2025")
        assert "Deleted 1 topic(s) of 2025: feature-foo" in result.output

    def test_delete_resolution_error_surfaces_clean(self) -> None:
        """A resolution error is clean and deletes nothing."""
        with (
            mock.patch.object(
                _topics_module,
                "resolve_delete_targets",
                side_effect=click.ClickException("no topic matches 'nope' — run 'goga topics board'"),
            ) as mock_resolve,
            mock.patch.object(_topics_module, "delete_topics") as mock_delete,
        ):
            result = CliRunner().invoke(topics, ["delete", "nope"])
        assert result.exit_code == 1
        assert "no topic matches" in result.stderr
        assert "Traceback" not in result.stderr
        mock_resolve.assert_called_once_with(["nope"], None)
        mock_delete.assert_not_called()
