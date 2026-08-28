"""Contract and logic tests for the entity declared in
``goga/commands/history/CODEMANIFEST`` with ``location: history.py``:
the ``history`` click group with the ``list``/``status``/``path``/``ensure``
subcommands.

The group is a thin wrapper: inputs are resolved here, every computation is
delegated to the ``goga.history`` domain, and output goes through the
``render`` module. The logic tests cover the negative paths — domain errors
(``ValueError``), an undetermined git branch, and validation failures must
surface as ``click.ClickException`` (stderr, exit 1, no traceback). The
positive cross-entity scenarios live in ``test_history_command.py``.
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

    def test_history_registers_four_subcommands(self) -> None:
        """The group carries exactly the four declared subcommands."""
        assert sorted(history.commands) == ["ensure", "list", "path", "status"]

    def test_history_group_carries_no_options(self) -> None:
        """Every subcommand owns its arguments — the group has none."""
        assert history.params == []

    def test_list_topics_does_not_shadow_builtin_list(self) -> None:
        """The list subcommand callback is named list_topics, not list."""
        assert callable(_history_module.list_topics)
        assert not hasattr(_history_module, "list")

    def test_list_callback_signature(self) -> None:
        """``list_topics(ctx)`` — no arguments beyond the click context."""
        callback = history.commands["list"].callback
        assert list(inspect.signature(callback).parameters) == ["ctx"]

    def test_status_callback_signature(self) -> None:
        """``status(ctx, year, topic, statuses)`` with the tuple default ``()``."""
        callback = history.commands["status"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["ctx", "year", "topic", "statuses"]
        assert signature.parameters["statuses"].default == ()
        hints = typing.get_type_hints(callback)
        assert hints == {
            "ctx": click.Context,
            "year": str | None,
            "topic": str | None,
            "statuses": tuple[str, ...],
            "return": type(None),
        }

    def test_path_callback_signature(self) -> None:
        """``path(ctx, topic, filename, year)``."""
        callback = history.commands["path"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["ctx", "topic", "filename", "year"]
        hints = typing.get_type_hints(callback)
        assert hints == {
            "ctx": click.Context,
            "topic": str | None,
            "filename": str | None,
            "year": str | None,
            "return": type(None),
        }

    def test_ensure_callback_signature(self) -> None:
        """``ensure(ctx, name)``."""
        callback = history.commands["ensure"].callback
        assert list(inspect.signature(callback).parameters) == ["ctx", "name"]

    def test_status_options(self) -> None:
        """status: optional YEAR positional, -t/--topic, repeatable -s/--status."""
        command = history.commands["status"]
        year_argument = next(p for p in command.params if isinstance(p, click.Argument) and p.name == "year")
        assert year_argument.required is False
        topic_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "topic")
        assert "-t" in topic_option.opts
        assert "--topic" in topic_option.opts
        status_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "statuses")
        assert "-s" in status_option.opts
        assert "--status" in status_option.opts
        assert status_option.multiple is True

    def test_path_options(self) -> None:
        """path: optional TOPIC positional, -f/--file, -y/--year."""
        command = history.commands["path"]
        topic_argument = next(p for p in command.params if isinstance(p, click.Argument) and p.name == "topic")
        assert topic_argument.required is False
        file_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "filename")
        assert "-f" in file_option.opts
        assert "--file" in file_option.opts
        year_option = next(p for p in command.params if isinstance(p, click.Option) and p.name == "year")
        assert "-y" in year_option.opts
        assert "--year" in year_option.opts

    def test_ensure_argument(self) -> None:
        """ensure: optional NAME positional."""
        command = history.commands["ensure"]
        name_argument = next(p for p in command.params if isinstance(p, click.Argument) and p.name == "name")
        assert name_argument.required is False


# --- Logic tests (negative paths, via CliRunner) ---


class TestHistoryNegativePaths:
    def test_history_status_unknown_status_name(self) -> None:
        """An unknown -s name is a clean error — no traceback, exit 1."""
        result = CliRunner().invoke(history, ["status", "-s", "bogus"])
        assert result.exit_code == 1
        assert "unknown status name" in result.stderr
        assert "Traceback" not in result.stderr

    def test_history_status_empty_topic_filter_is_error(self) -> None:
        """A -t value normalizing to an empty slug is an error, not match-all."""
        result = CliRunner().invoke(history, ["status", "-t", "Релиз"])
        assert result.exit_code == 1
        assert "empty topic slug" in result.stderr
        assert result.stdout == ""

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


@pytest.mark.parametrize(
    ("argv", "stderr_fragment"),
    [
        (["status", "2026", "-t", "Релиз"], "empty topic slug"),
        (["path", "Релиз/Один", "-f", "plan.md"], "empty topic slug"),
        (["ensure", "Релиз/Один"], "empty topic slug"),
    ],
)
def test_history_empty_slug_inputs_are_clean_errors(argv: list[str], stderr_fragment: str) -> None:
    """Every subcommand converts the domain empty-slug error to exit 1."""
    result = CliRunner().invoke(history, argv)
    assert result.exit_code == 1
    assert stderr_fragment in result.stderr
    assert "Traceback" not in result.stderr
