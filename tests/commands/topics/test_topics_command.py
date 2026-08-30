"""Contract and logic tests for the entity declared in
``goga/commands/topics/CODEMANIFEST`` with ``location: topics.py``:
the ``topics`` click group with the ``status``/``create``/``switch``
subcommands.

The group is a thin wrapper: the ``--year/-y`` option builds the scope every
subcommand shares, and each subcommand delegates its computation to the
``goga.topics`` domain — the board collection and rendering for ``status``
(the ``--info/-i`` flag adds the title column to the rendered table), the
creation (``--title/-t`` writes the topic title file) and switching
procedures for ``create``/``switch``. ``create`` also carries the fast
creation-and-publication mode — ``--publish/-p`` with ``--base-ref`` and
``--commit/-c`` — whose values resolve as flag beats the ``topics`` section
of ``.goga/config.yml`` beats the built-in default, the configuration being
read on the publish path only. The logic tests mock the domain at its
import site in the command module and drive the CLI surface through
``CliRunner``; a pinned ``COLUMNS`` keeps the measured terminal width
deterministic.
"""

from __future__ import annotations

import inspect
import os
import shutil
import sys
from pathlib import Path
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
        """``status(scope, remote=False, info=False)`` — the scope object and the flags."""
        callback = topics.commands["status"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["scope", "remote", "info"]
        assert signature.parameters["remote"].default is False
        assert signature.parameters["info"].default is False

    def test_status_carries_the_remote_flag(self) -> None:
        """status: --remote/-r flag, defaulting to False."""
        command = topics.commands["status"]
        remote_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "remote")
        assert "-r" in remote_option.opts
        assert "--remote" in remote_option.opts
        assert remote_option.is_flag is True
        assert remote_option.default is False

    def test_status_carries_the_info_flag(self) -> None:
        """status: --info/-i flag, defaulting to False."""
        command = topics.commands["status"]
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

    def test_create_carries_the_title_option(self) -> None:
        """create: --title/-t option, defaulting to None."""
        command = topics.commands["create"]
        title_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "title")
        assert "-t" in title_option.opts
        assert "--title" in title_option.opts
        assert title_option.is_flag is False
        assert title_option.default is None

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

    def test_create_carries_the_commit_option_with_the_explicit_param_name(self) -> None:
        """create: --commit/-c bound to the param name ``commit_message``."""
        command = topics.commands["create"]
        commit_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "commit_message")
        assert commit_option.opts == ["--commit", "-c"]
        assert commit_option.is_flag is False
        assert commit_option.default is None

    def test_create_callback_signature(self) -> None:
        """``create(scope, branch_name, title=None, publish=False, base_ref=None, commit_message=None)``."""
        callback = topics.commands["create"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == [
            "scope",
            "branch_name",
            "title",
            "publish",
            "base_ref",
            "commit_message",
        ]
        assert signature.parameters["title"].default is None
        assert signature.parameters["publish"].default is False
        assert signature.parameters["base_ref"].default is None
        assert signature.parameters["commit_message"].default is None

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
        mock_create.assert_called_once_with("X", "2025", None)

    @pytest.mark.parametrize("subcommand", ["status", "create", "switch"])
    def test_subcommand_help_follows_the_cli_docstring_rule(self, subcommand: str) -> None:
        """The rendered help carries no Args/Returns/Raises sections."""
        result = CliRunner().invoke(topics, [subcommand, "--help"])
        assert result.exit_code == 0
        assert result.output.strip() != ""
        for section in ("Args:", "Returns:", "Raises:"):
            assert section not in result.output

    def test_create_help_lists_the_new_flags(self) -> None:
        """create --help lists --publish/-p, --base-ref, and --commit/-c."""
        result = CliRunner().invoke(topics, ["create", "--help"])
        assert result.exit_code == 0
        assert "--publish" in result.output
        assert "-p" in result.output
        assert "--base-ref" in result.output
        assert "--commit" in result.output
        assert "-c" in result.output

    def test_year_defaults_to_none_for_the_domain(self) -> None:
        """Without --year the subcommands hand the domain the current-year None."""
        with mock.patch.object(_topics_module, "create_topic") as mock_create:
            mock_create.return_value = "Created branch X and topic 2026/x"
            result = CliRunner().invoke(topics, ["create", "X"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("X", None, None)


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

    def test_topics_status_info_flag_reaches_renderer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--info reaches the renderer — the table gains the Title column."""
        records = [
            BoardRecord(
                topic="feat-a",
                branch="feat/a",
                statuses=["planned"],
                current=True,
                remote=False,
                title="Payment retry",
            ),
        ]
        monkeypatch.setattr(shutil, "get_terminal_size", lambda: os.terminal_size((100, 24)))
        with mock.patch.object(_topics_module, "collect_topic_board", return_value=records):
            result = CliRunner().invoke(topics, ["status", "--info"])
        assert result.exit_code == 0
        header = result.output.splitlines()[0]
        assert "Title" in header
        assert "Topic" in header
        assert "Branch" in header
        assert "Statuses" in header
        assert "Payment retry" in result.output

    def test_topics_status_info_short_form_binds_the_same_table(self) -> None:
        """-i renders the same four-column table as --info."""
        records = [
            BoardRecord(topic="feat-a", branch="feat/a", statuses=["planned"], current=False, remote=False, title="T"),
        ]
        with (
            mock.patch.object(_topics_module, "collect_topic_board", return_value=records),
            mock.patch.dict("os.environ", {"COLUMNS": "100"}),
        ):
            short = CliRunner().invoke(topics, ["status", "-i"])
            long = CliRunner().invoke(topics, ["status", "--info"])
        assert short.exit_code == 0
        assert long.exit_code == 0
        assert short.output == long.output
        assert "Title" in short.output.splitlines()[0]

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
        mock_create.assert_called_once_with("Feature/Foo_Bar", None, None)
        assert result.output.splitlines() == ["Created branch Feature/Foo_Bar and topic 2026/feature-foo-bar"]

    def test_topics_create_title_option_reaches_domain(self) -> None:
        """-t hands the domain (name, scoped year, title) verbatim."""
        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            result = CliRunner().invoke(topics, ["create", "Feature/Foo_Bar", "-t", "Payment retry"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("Feature/Foo_Bar", None, "Payment retry")
        assert result.output == "line\n"

    def test_topics_create_title_long_form_binds_the_same_value(self) -> None:
        """--title behaves exactly like -t."""
        with mock.patch.object(_topics_module, "create_topic", return_value="line") as mock_create:
            result = CliRunner().invoke(topics, ["create", "feat-a", "--title", "T"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("feat-a", None, "T")
        assert result.output == "line\n"

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


def _write_config(tmp_path: Path, body: str) -> None:
    """Write ``.goga/config.yml`` with the given body under tmp_path."""
    goga_dir = tmp_path / ".goga"
    goga_dir.mkdir(exist_ok=True)
    (goga_dir / "config.yml").write_text(body, encoding="utf-8")


class TestTopicsCreatePublish:
    def test_create_publish_flag_beats_config_section(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Both publication flags given: the flag values win and no config read happens."""
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            "language: python\ntopics:\n  base_ref: origin/config-base\n  publish_commit: 'config: {slug}'\n",
        )
        with (
            mock.patch.object(_topics_module, "load_project_config") as mock_load,
            mock.patch.object(_topics_module, "create_topic") as mock_create,
            mock.patch.object(
                _topics_module,
                "publish_topic",
                return_value="Created branch Feature/Foo_Bar and published topic 2026/feature-foo-bar",
            ) as mock_publish,
        ):
            result = CliRunner().invoke(
                topics,
                [
                    "create",
                    "Feature/Foo_Bar",
                    "--publish",
                    "--title",
                    "T",
                    "--base-ref",
                    "origin/flag-base",
                    "--commit",
                    "flag: {slug}",
                ],
            )
        assert result.exit_code == 0
        mock_publish.assert_called_once_with("Feature/Foo_Bar", "T", "origin/flag-base", "flag: {slug}", None)
        mock_load.assert_not_called()
        mock_create.assert_not_called()
        assert result.output.splitlines() == ["Created branch Feature/Foo_Bar and published topic 2026/feature-foo-bar"]

    def test_create_publish_resolves_config_and_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No flags: the base comes from the config, the template from the built-in default."""
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, "language: python\ntopics:\n  base_ref: origin/config-base\n")
        with mock.patch.object(_topics_module, "publish_topic", return_value="line") as mock_publish:
            result = CliRunner().invoke(topics, ["create", "Feature/Foo_Bar", "--publish", "--title", "T"])
        assert result.exit_code == 0
        mock_publish.assert_called_once_with(
            "Feature/Foo_Bar", "T", "origin/config-base", "goga: create topic {slug}", None
        )
        assert result.output == "line\n"

    def test_create_publish_config_template_beats_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``topics.publish_commit`` wins over the built-in default template."""
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            "language: python\ntopics:\n  base_ref: origin/config-base\n  publish_commit: 'config: {slug}'\n",
        )
        with mock.patch.object(_topics_module, "publish_topic", return_value="line") as mock_publish:
            result = CliRunner().invoke(topics, ["create", "Feature/Foo_Bar", "--publish", "--title", "T"])
        assert result.exit_code == 0
        mock_publish.assert_called_once_with(
            "Feature/Foo_Bar", "T", "origin/config-base", "config: {slug}", None
        )

    def test_create_publish_flag_base_with_config_template(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A flag base with a config template — each value resolves on its own row."""
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            "language: python\ntopics:\n  base_ref: origin/config-base\n  publish_commit: 'config: {slug}'\n",
        )
        with (
            mock.patch.object(
                _topics_module, "load_project_config", wraps=_topics_module.load_project_config
            ) as mock_load,
            mock.patch.object(_topics_module, "publish_topic", return_value="line") as mock_publish,
        ):
            result = CliRunner().invoke(
                topics,
                ["create", "Feature/Foo_Bar", "--publish", "--title", "T", "--base-ref", "origin/flag-base"],
            )
        assert result.exit_code == 0
        mock_publish.assert_called_once_with(
            "Feature/Foo_Bar", "T", "origin/flag-base", "config: {slug}", None
        )
        # The template flag is absent, so the config is read for it.
        mock_load.assert_called_once_with()

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
            mock.patch.object(_topics_module, "publish_topic", return_value="line") as mock_publish,
        ):
            result = CliRunner().invoke(
                topics,
                ["create", "Feature/Foo_Bar", "--publish", "--title", "T", "--commit", "flag: {slug}"],
            )
        assert result.exit_code == 0
        mock_publish.assert_called_once_with(
            "Feature/Foo_Bar", "T", "origin/config-base", "flag: {slug}", None
        )
        # The base flag is absent, so the config is read for it.
        mock_load.assert_called_once_with()

    @pytest.mark.parametrize("extra", [["--commit", "m"], ["--base-ref", "origin/main"]])
    def test_create_publication_flags_without_publish_are_clean_error(self, extra: list[str]) -> None:
        """--base-ref or --commit without --publish is a clean error; no domain routine runs."""
        with (
            mock.patch.object(_topics_module, "load_project_config") as mock_load,
            mock.patch.object(_topics_module, "create_topic") as mock_create,
            mock.patch.object(_topics_module, "publish_topic") as mock_publish,
        ):
            result = CliRunner().invoke(topics, ["create", "X", *extra])
        assert result.exit_code == 1
        assert "--base-ref and --commit act only together with --publish" in result.stderr
        mock_load.assert_not_called()
        mock_create.assert_not_called()
        mock_publish.assert_not_called()

    def test_create_publish_without_title_is_clean_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--publish without a title is a clean error asking for it; the domain is untouched."""
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_topics_module, "publish_topic") as mock_publish:
            result = CliRunner().invoke(topics, ["create", "X", "--publish"])
        assert result.exit_code == 1
        assert "--publish needs a topic title" in result.stderr
        assert "--title" in result.stderr
        mock_publish.assert_not_called()

    def test_create_publish_without_base_names_config_and_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing set: the error names the configuration line, the flag, and a yaml example."""
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, "language: python\n")
        with mock.patch.object(_topics_module, "publish_topic") as mock_publish:
            result = CliRunner().invoke(topics, ["create", "X", "--publish", "--title", "T"])
        assert result.exit_code == 1
        assert "topics.base_ref" in result.stderr
        assert "--base-ref" in result.stderr
        assert "topics:" in result.stderr
        assert "base_ref: origin/main" in result.stderr
        mock_publish.assert_not_called()

    def test_create_publish_invalid_config_surfaces_its_own_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A malformed topics section surfaces the loader's error, not a 'no base' guess."""
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, "language: python\ntopics: 5\n")
        with mock.patch.object(_topics_module, "publish_topic") as mock_publish:
            result = CliRunner().invoke(topics, ["create", "X", "--publish", "--title", "T"])
        assert result.exit_code == 1
        assert "'topics' must be a mapping in .goga/config.yml" in result.stderr
        mock_publish.assert_not_called()

    def test_create_publish_unreadable_config_surfaces_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unreadable configuration file (a directory in its place)
        surfaces one clean error — not a raw IsADirectoryError traceback, and
        not the 'no base' guess either.
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".goga").mkdir()
        (tmp_path / ".goga" / "config.yml").mkdir()
        with mock.patch.object(_topics_module, "publish_topic") as mock_publish:
            result = CliRunner().invoke(topics, ["create", "X", "--publish", "--title", "T"])
        assert result.exit_code == 1
        assert "Is a directory" in result.stderr
        assert not isinstance(result.exception, IsADirectoryError)
        mock_publish.assert_not_called()

    def test_create_default_path_never_reads_configuration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without --publish the configuration is never read — a config-less repository works."""
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_topics_module, "load_project_config") as mock_load,
            mock.patch.object(
                _topics_module, "create_topic", return_value="Created branch Feature/Foo_Bar and topic 2026/x"
            ) as mock_create,
        ):
            result = CliRunner().invoke(topics, ["create", "Feature/Foo_Bar"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with("Feature/Foo_Bar", None, None)
        mock_load.assert_not_called()

    def test_create_publish_missing_config_counts_as_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing configuration file counts as unset — the flag and the default act."""
        monkeypatch.chdir(tmp_path)
        with mock.patch.object(_topics_module, "publish_topic", return_value="line") as mock_publish:
            result = CliRunner().invoke(
                topics, ["create", "X", "--publish", "--title", "T", "--base-ref", "origin/main"]
            )
        assert result.exit_code == 0
        mock_publish.assert_called_once_with("X", "T", "origin/main", "goga: create topic {slug}", None)

    def test_create_publish_explicit_empty_title_is_not_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--title '' is a deliberate empty title, not a missing one — the gate checks None."""
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, "language: python\ntopics:\n  base_ref: origin/main\n")
        with (
            mock.patch.object(_topics_module, "publish_topic", return_value="line") as mock_publish,
            mock.patch.object(_topics_module, "create_topic") as mock_create,
        ):
            result = CliRunner().invoke(topics, ["create", "X", "--publish", "--title", ""])
        assert result.exit_code == 0
        assert mock_publish.call_args.args[1] == ""
        mock_create.assert_not_called()
