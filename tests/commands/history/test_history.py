"""Contract and logic tests for the entity declared in
``goga/commands/history/CODEMANIFEST`` with ``location: history.py``:
the ``history`` click group with the ``list``/``status``/``path``/``ensure``/
``prune`` subcommands.

The group is a thin wrapper: it carries the shared ``-y/--year`` option,
inputs are resolved here, every computation is delegated to the
``goga.history`` domain, and output goes through the ``render`` module.
The logic tests cover the negative paths — domain errors (``ValueError``),
an undetermined git branch, and validation failures must surface as
``click.ClickException`` (stderr, exit 1, no traceback), while the removed
year forms (a positional YEAR, a year option after the subcommand) are
click's own usage errors (exit 2). The positive cross-entity scenarios
live in ``tests/integration/test_history_command.py``.
"""

from __future__ import annotations

import inspect
import sys
import typing
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.commands.history import history, render_history_tree, render_topic_statuses
from goga.history import prune_topics

# goga.commands.history.history is shadowed in the package __init__ by the
# history click group, so attribute access through the package gives the
# group. Resolve the real module via sys.modules (precedent: test_pipeline).
_history_module = sys.modules["goga.commands.history.history"]
# The facade __all__ lives on the cell package itself.
_history_facade = sys.modules["goga.commands.history"]

# --- Contract tests ---


class TestHistoryGroupContract:
    def test_history_importable_from_facade(self) -> None:
        """history is importable from the goga.commands.history facade."""
        assert _history_module.history is history

    def test_facade_exports_three_names(self) -> None:
        """The cell facade carries the three declared names, alphabetically."""
        assert _history_facade.__all__ == ["history", "render_history_tree", "render_topic_statuses"]
        assert callable(history)
        assert callable(render_history_tree)
        assert callable(render_topic_statuses)

    def test_history_is_a_click_group(self) -> None:
        """history is a click.Group container for the subcommands."""
        assert isinstance(history, click.Group)

    def test_history_registers_five_subcommands(self) -> None:
        """The group carries exactly the five declared subcommands."""
        assert sorted(history.commands) == ["ensure", "list", "path", "prune", "status"]

    def test_history_module_binds_domain_prune_topics(self) -> None:
        """The command module imports the domain cleanup routine at its site."""
        assert _history_module.prune_topics is prune_topics

    def test_history_group_carries_only_the_year_option(self) -> None:
        """The group owns the shared -y/--year option — and nothing else."""
        assert len(history.params) == 1
        year_option = history.params[0]
        assert isinstance(year_option, click.Option)
        assert year_option.name == "year"
        assert {"-y", "--year"} <= set(year_option.opts)
        assert year_option.default is None

    def test_history_group_callback_signature(self) -> None:
        """``history(ctx, year)`` — the context and the scoped year."""
        callback = history.callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["ctx", "year"]
        assert signature.parameters["year"].default is None

    def test_history_scope_is_a_kw_only_dataclass_with_year(self) -> None:
        """``_HistoryScope`` is a kw_only dataclass carrying the year field."""
        scope = _history_module._HistoryScope(year="2025")
        assert scope.year == "2025"
        assert _history_module._HistoryScope().year is None
        # Not frozen — the group assigns the year after ensure_object.
        scope.year = None
        assert scope.year is None

    def test_list_topics_does_not_shadow_builtin_list(self) -> None:
        """The list subcommand callback is named list_topics, not list."""
        assert callable(_history_module.list_topics)
        assert not hasattr(_history_module, "list")

    def test_list_callback_signature(self) -> None:
        """``list_topics(scope)`` — the scope object alone."""
        callback = history.commands["list"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["scope"]
        hints = typing.get_type_hints(callback)
        assert hints == {
            "scope": _history_module._HistoryScope,
            "return": type(None),
        }

    def test_status_callback_signature(self) -> None:
        """``status(scope, topic, statuses)`` with the tuple default ``()``."""
        callback = history.commands["status"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["scope", "topic", "statuses"]
        assert signature.parameters["statuses"].default == ()
        hints = typing.get_type_hints(callback)
        assert hints == {
            "scope": _history_module._HistoryScope,
            "topic": str | None,
            "statuses": tuple[str, ...],
            "return": type(None),
        }

    def test_path_callback_signature(self) -> None:
        """``path(scope, topic, filename)``."""
        callback = history.commands["path"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["scope", "topic", "filename"]
        hints = typing.get_type_hints(callback)
        assert hints == {
            "scope": _history_module._HistoryScope,
            "topic": str | None,
            "filename": str | None,
            "return": type(None),
        }

    def test_ensure_callback_signature(self) -> None:
        """``ensure(scope, name)``."""
        callback = history.commands["ensure"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["scope", "name"]
        hints = typing.get_type_hints(callback)
        assert hints == {
            "scope": _history_module._HistoryScope,
            "name": str | None,
            "return": type(None),
        }

    def test_prune_callback_signature(self) -> None:
        """``prune(scope, dry_run)`` with the declared default ``False``."""
        callback = history.commands["prune"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["scope", "dry_run"]
        assert signature.parameters["dry_run"].default is False
        hints = typing.get_type_hints(callback)
        assert hints == {
            "scope": _history_module._HistoryScope,
            "dry_run": bool,
            "return": type(None),
        }

    def test_status_options(self) -> None:
        """status: -t/--topic and repeatable -s/--status — no year surface."""
        command = history.commands["status"]
        assert all(param.name != "year" for param in command.params)
        topic_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "topic")
        assert "-t" in topic_option.opts
        assert "--topic" in topic_option.opts
        status_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "statuses")
        assert "-s" in status_option.opts
        assert "--status" in status_option.opts
        assert status_option.multiple is True

    def test_path_options(self) -> None:
        """path: optional TOPIC positional and -f/--file — no year option."""
        command = history.commands["path"]
        assert all(param.name != "year" for param in command.params)
        topic_argument = next(p for p in command.params if isinstance(p, click.Argument) and p.name == "topic")
        assert topic_argument.required is False
        file_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "filename")
        assert "-f" in file_option.opts
        assert "--file" in file_option.opts

    def test_ensure_argument(self) -> None:
        """ensure: optional NAME positional."""
        command = history.commands["ensure"]
        name_argument = next(p for p in command.params if isinstance(p, click.Argument) and p.name == "name")
        assert name_argument.required is False

    def test_prune_options(self) -> None:
        """prune: the --dry-run flag alone — no arguments, no year surface."""
        command = history.commands["prune"]
        assert len(command.params) == 1
        dry_run_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "dry_run")
        assert "--dry-run" in dry_run_option.opts
        assert dry_run_option.is_flag is True
        assert dry_run_option.default is False


# --- Logic tests (negative paths, via CliRunner) ---


class TestHistoryNegativePaths:
    def test_history_status_unknown_status_name(self) -> None:
        """An unknown -s name is a clean error — no traceback, exit 1."""
        result = CliRunner().invoke(history, ["status", "-s", "bogus"])
        assert result.exit_code == 1
        assert "unknown status name" in result.stderr
        assert "Traceback" not in result.stderr

    def test_history_status_broken_scale_assembly_fails_cleanly(self) -> None:
        """A fatal scale assembly error (broken goga_tool_* import) surfaces clean."""
        runner = CliRunner()

        with mock.patch.object(
            _history_module,
            "assemble_status_scale",
            side_effect=ImportError("package goga_tool_bad failed to import: boom"),
        ):
            result = runner.invoke(history, ["status"])
        assert result.exit_code == 1
        assert "goga_tool_bad" in result.stderr
        assert "Traceback" not in result.stderr

    def test_history_status_empty_topic_filter_is_error(self) -> None:
        """A -t value normalizing to an empty slug is an error, not match-all."""
        result = CliRunner().invoke(history, ["status", "-t", "Релиз"])
        assert result.exit_code == 1
        assert "empty topic slug" in result.stderr
        assert result.stdout == ""

    @pytest.mark.parametrize(
        ("argv", "stderr_fragment"),
        [
            (["-y", "2026", "status", "-t", "Релиз"], "empty topic slug"),
            (["path", "Релиз/Один", "-f", "plan.md"], "empty topic slug"),
            (["ensure", "Релиз/Один"], "empty topic slug"),
        ],
    )
    def test_history_empty_slug_inputs_are_clean_errors(self, argv: list[str], stderr_fragment: str) -> None:
        """Every subcommand converts the domain empty-slug error to exit 1."""
        result = CliRunner().invoke(history, argv)
        assert result.exit_code == 1
        assert stderr_fragment in result.stderr
        assert "Traceback" not in result.stderr

    def test_history_path_no_branch_fails_cleanly(self) -> None:
        """path without a positional and without a determinable branch fails clean."""
        runner = CliRunner()

        with mock.patch.object(_history_module, "resolve_current_branch_name", return_value=None):
            result = runner.invoke(history, ["path"])
        assert result.exit_code == 1
        assert "cannot determine the current git branch" in result.stderr
        assert result.stdout == ""
        assert "Traceback" not in result.stderr

    def test_history_path_extensionless_file_fails(self) -> None:
        """An extensionless -f value surfaces the domain error as a clean error."""
        result = CliRunner().invoke(history, ["path", "feat-x", "-f", "noext"])
        assert result.exit_code == 1
        assert "must carry an extension" in result.stderr

    def test_history_ensure_no_branch_fails_cleanly(self) -> None:
        """ensure without a positional and without a determinable branch fails clean."""
        runner = CliRunner()

        with mock.patch.object(_history_module, "resolve_current_branch_name", return_value=None):
            result = runner.invoke(history, ["ensure"])
        assert result.exit_code == 1
        assert "cannot determine the current git branch" in result.stderr
        assert result.stdout == ""


class TestHistoryYearUsageErrors:
    def test_history_status_positional_year_is_usage_error(self) -> None:
        """status 2025 — the removed positional YEAR is click's usage error."""
        result = CliRunner().invoke(history, ["status", "2025"])
        assert result.exit_code == 2
        assert "Usage" in result.stderr
        assert "extra argument" in result.stderr
        assert "Traceback" not in result.stderr

    def test_history_prune_positional_year_is_usage_error(self) -> None:
        """prune 2025 — the removed positional YEAR is click's usage error."""
        result = CliRunner().invoke(history, ["prune", "2025"])
        assert result.exit_code == 2
        assert "Usage" in result.stderr
        assert "extra argument" in result.stderr
        assert "Traceback" not in result.stderr

    def test_history_path_year_option_is_usage_error(self) -> None:
        """path -y 2025 — the removed local year option is click's usage error."""
        result = CliRunner().invoke(history, ["path", "feat-x", "-y", "2025"])
        assert result.exit_code == 2
        assert "No such option" in result.stderr
        assert "Traceback" not in result.stderr

    def test_history_status_year_option_after_subcommand_is_usage_error(self) -> None:
        """status -y 2025 — the year option belongs to the group, before the subcommand."""
        result = CliRunner().invoke(history, ["-y", "2026", "status", "-y", "2025"])
        assert result.exit_code == 2
        assert "No such option" in result.stderr
        assert "Traceback" not in result.stderr
