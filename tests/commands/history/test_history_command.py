"""Integration tests for the ``goga history`` command group.

Cross-entity scenarios — group → subcommand → domain → render →
stdout/filesystem: the command layer resolves the inputs, the
``goga.history`` domain computes, the ``render`` module prints. The negative
paths live in ``test_history.py``; this file drives the happy paths and the
empty-result edges through the real command objects.

Setup follows the cell conventions: ``tmp_path`` + ``monkeypatch.chdir`` for
the filesystem, ``CliRunner`` for the CLI surface (captured output is not a
TTY, so ANSI is stripped), the pinned clock ``naming.datetime`` wherever the
year must be deterministic, and the branch reader mocked at its import site
in the command module.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.commands.history import history
from goga.history import naming

# goga.commands.history.history is shadowed in the package __init__ by the
# history click group, so attribute access through the package gives the
# group. Resolve the real module via sys.modules (precedent: test_history.py).
_history_module = sys.modules["goga.commands.history.history"]


class _FixedClock:
    """Stand-in for ``datetime`` answering a fixed naive date."""

    @staticmethod
    def now() -> datetime:
        return datetime(2031, 6, 15)  # noqa: DTZ001 — a fixed naive date is the point of the clock


def _fake_tool_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the scale assembly to one fake tool package.

    ``goga_tool_mkdocs`` subscribes ``published`` on the status action and
    registers it anchored after ``planned``, so a topic carrying both
    ``plan.md`` and ``mkdocs/published.md`` has the single maximal status
    ``mkdocs.published``. The enumeration patch keeps the real tool packages
    of the environment out of the assembled scale.
    """

    def register_hooks(hooks: Any) -> None:
        hooks.subscribe(
            "statuses",
            "register_statuses",
            "published",
            lambda context: context.register(name="published", filepath="mkdocs/published.md", after="planned"),
        )

    module = ModuleType("goga_tool_mkdocs")
    module.register_hooks = register_hooks
    monkeypatch.setitem(sys.modules, "goga_tool_mkdocs", module)
    monkeypatch.setattr(
        "goga.hooks.tools.packages.packages_distributions",
        lambda: {"goga_tool_mkdocs": ["goga-tool-mkdocs"]},
    )


# --- Cross-entity interactions ---


class TestHistoryList:
    def test_history_list_renders_tree(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """list prints the inventory: years with topics, no statuses, no non-years."""
        root = tmp_path / ".goga" / "history"
        for relative in ("2025/b-topic", "2025/a-topic", "2026/history-commands", "backups", "20a6"):
            (root / relative).mkdir(parents=True)
        (root / "notes.md").write_text("not a year\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["list"])

        assert result.exit_code == 0
        assert "2025/" in result.output
        assert " └── a-topic" in result.output
        assert "2026/" in result.output
        assert " └── history-commands" in result.output
        assert result.output.splitlines() == [
            "2025/",
            " └── a-topic",
            " └── b-topic",
            "2026/",
            " └── history-commands",
        ]
        assert "[planned]" not in result.output

    def test_history_list_scoped_year_renders_one_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """-y scopes the inventory to one year — the other years never print."""
        root = tmp_path / ".goga" / "history"
        (root / "2025" / "release-1-3-0").mkdir(parents=True)
        (root / "2026" / "feat-x").mkdir(parents=True)
        (root / "2026" / "history-commands").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["-y", "2025", "list"])

        assert result.exit_code == 0
        assert result.output.splitlines() == ["2025/", " └── release-1-3-0"]
        assert "2026" not in result.output


class TestHistoryStatus:
    def test_status_signature_defaults(self) -> None:
        """``status(scope, topic=None, statuses=())`` — the declared shape."""
        callback = history.commands["status"].callback
        signature = inspect.signature(callback)
        assert list(signature.parameters) == ["scope", "topic", "statuses"]
        # scope is the pass_obj injection — click supplies it, no default.
        assert signature.parameters["scope"].default is inspect.Parameter.empty
        assert signature.parameters["topic"].default is None
        assert signature.parameters["statuses"].default == ()

    def test_history_status_scoped_year_collects_that_year(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The scoped year is the year collected — a registered tool status is maximal and filterable."""
        year_dir = tmp_path / ".goga" / "history" / "2026"
        (year_dir / "release-1-3-0" / "mkdocs").mkdir(parents=True)
        (year_dir / "release-1-3-0" / "plan.md").write_text("plan\n", encoding="utf-8")
        (year_dir / "release-1-3-0" / "mkdocs" / "published.md").write_text("pub\n", encoding="utf-8")
        (year_dir / "alpha").mkdir()
        (year_dir / "alpha" / "prd.md").write_text("prd\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        _fake_tool_packages(monkeypatch)

        result = CliRunner().invoke(history, ["-y", "2026", "status", "-s", "mkdocs.published"])

        assert result.exit_code == 0
        assert result.output.splitlines() == ["release-1-3-0 [mkdocs.published]"]
        assert "alpha" not in result.output

    def test_history_status_unknown_filter_name_clean_error(self) -> None:
        """An unknown -s name fails before any collection — clean, exit 1."""
        with mock.patch.object(_history_module, "collect_topic_statuses") as collect_mock:
            result = CliRunner().invoke(history, ["status", "-s", "bogus"])

        assert result.exit_code == 1
        assert "unknown status name: 'bogus'" in result.stderr
        assert "Traceback" not in result.stderr
        collect_mock.assert_not_called()

    def test_history_status_empty_topic_filter_rejected(self) -> None:
        """A -t value normalizing to an empty slug is rejected, not match-all."""
        result = CliRunner().invoke(history, ["status", "-t", "???"])

        assert result.exit_code == 1
        assert "empty topic slug" in result.stderr
        assert result.stdout == ""

    def test_history_status_filters_and(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """-t and -s combine by AND; the year is resolved, never printed."""
        year_dir = tmp_path / ".goga" / "history" / "2026"
        (year_dir / "release-1-3-0" / "completed").mkdir(parents=True)
        (year_dir / "release-1-3-0" / "completed" / "plan.md").write_text("done\n", encoding="utf-8")
        (year_dir / "history-commands").mkdir()
        (year_dir / "history-commands" / "plan.md").write_text("plan\n", encoding="utf-8")
        (year_dir / "other").mkdir()
        (year_dir / "other" / "prd.md").write_text("prd\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["-y", "2026", "status", "-t", "Release/1.3.0", "-s", "done"])

        assert result.exit_code == 0
        assert result.output.strip() == "release-1-3-0 [done]"
        assert "history-commands" not in result.output
        assert "other" not in result.output
        assert "2026" not in result.output

    def test_history_status_defaults_to_current_year_unfiltered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Plain status: the current year, no filters — every topic alphabetically."""
        history_root = tmp_path / ".goga" / "history"
        (history_root / "2025" / "old-topic").mkdir(parents=True)
        year_dir = history_root / "2031"
        for topic in ("alpha", "mid", "zeta"):
            (year_dir / topic).mkdir(parents=True)
        (year_dir / "alpha" / "plan.md").write_text("plan\n", encoding="utf-8")
        (year_dir / "mid" / "prd.md").write_text("prd\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        with mock.patch.object(naming, "datetime", _FixedClock):
            result = CliRunner().invoke(history, ["status"])

        assert result.exit_code == 0
        assert result.output.splitlines() == ["alpha [planned]", "mid [defined]", "zeta [empty]"]
        assert "old-topic" not in result.output

    def test_history_status_repeatable_status_filter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """-s repeats: one -s per name keeps several statuses, drops the rest."""
        year_dir = tmp_path / ".goga" / "history" / "2026"
        for topic in ("done-topic", "planned-topic", "defined-topic"):
            (year_dir / topic).mkdir(parents=True)
        (year_dir / "done-topic" / "completed").mkdir()
        (year_dir / "done-topic" / "completed" / "plan.md").write_text("done\n", encoding="utf-8")
        (year_dir / "planned-topic" / "plan.md").write_text("plan\n", encoding="utf-8")
        (year_dir / "defined-topic" / "prd.md").write_text("prd\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["-y", "2026", "status", "-s", "planned", "-s", "done"])

        assert result.exit_code == 0
        assert result.output.splitlines() == ["done-topic [done]", "planned-topic [planned]"]
        assert "defined-topic" not in result.output

    def test_history_status_filter_todo_selects_todo_topics(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """-s todo selects the topics a todo file puts into the built-in todo status."""
        year_dir = tmp_path / ".goga" / "history" / "2026"
        (year_dir / "feat-a").mkdir(parents=True)
        (year_dir / "feat-a" / "todo.md").write_text("Payment retry\n", encoding="utf-8")
        (year_dir / "feat-b").mkdir()
        (year_dir / "feat-b" / "prd.md").write_text("prd\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("goga.hooks.tools.packages.packages_distributions", lambda: {})

        result = CliRunner().invoke(history, ["-y", "2026", "status", "-s", "todo"])

        assert result.exit_code == 0
        assert result.output.splitlines() == ["feat-a [todo]"]
        assert "feat-b" not in result.output

    def test_history_status_filter_todo_skips_defined_topics(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A topic with prd.md is defined, not todo — the maximal status wins through the CLI."""
        year_dir = tmp_path / ".goga" / "history" / "2026"
        (year_dir / "feat-b").mkdir(parents=True)
        (year_dir / "feat-b" / "todo.md").write_text("Todo\n", encoding="utf-8")
        (year_dir / "feat-b" / "prd.md").write_text("prd\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("goga.hooks.tools.packages.packages_distributions", lambda: {})

        result = CliRunner().invoke(history, ["-y", "2026", "status", "-s", "todo"])

        assert result.exit_code == 0
        assert result.output == ""
        assert (year_dir / "feat-b" / "todo.md").exists()

    def test_history_status_filter_new_unknown(self) -> None:
        """The retired new name is rejected — unknown status, clean error, no collection."""
        with mock.patch.object(_history_module, "collect_topic_statuses") as collect_mock:
            result = CliRunner().invoke(history, ["-y", "2026", "status", "-s", "new"])

        assert result.exit_code == 1
        assert "unknown status name: 'new'" in result.stderr
        assert "Traceback" not in result.stderr
        collect_mock.assert_not_called()


class TestHistoryPath:
    def test_history_path_prints_file_path_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """path answers the branch-defaulted artifact path — one line, nothing created."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(naming, "datetime", _FixedClock),
            mock.patch.object(_history_module, "resolve_current_branch_name", return_value="history-commands"),
        ):
            result = runner.invoke(history, ["path", "-f", "plan.md"])

        expected = str(Path(".goga/history") / "2031" / "history-commands" / "plan.md")
        assert result.exit_code == 0
        assert result.output.splitlines() == [expected]
        assert result.output.endswith("\n")
        assert not (tmp_path / ".goga").exists()

    def test_history_path_without_file_prints_topic_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """path without -f answers the branch-defaulted topic directory."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(naming, "datetime", _FixedClock),
            mock.patch.object(_history_module, "resolve_current_branch_name", return_value="Feature/Foo_Bar"),
        ):
            result = runner.invoke(history, ["path"])

        expected = str(Path(".goga/history") / "2031" / "feature-foo-bar")
        assert result.exit_code == 0
        assert result.output.splitlines() == [expected]
        assert result.output.endswith("\n")
        assert not (tmp_path / ".goga").exists()

    def test_history_path_scoped_year_composes_that_year(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """path takes an explicit branch-name topic; the scoped year composes the path."""
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["-y", "2025", "path", "release/1.3.0", "-f", "plan.md"])

        expected = str(Path(".goga/history") / "2025" / "release-1-3-0" / "plan.md")
        assert result.exit_code == 0
        assert result.output.splitlines() == [expected]
        assert not (tmp_path / ".goga").exists()


class TestHistoryEnsure:
    def test_history_ensure_creates_dir_silently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ensure normalizes the branch name and is idempotent — stdout stays empty."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with (
            mock.patch.object(naming, "datetime", _FixedClock),
            mock.patch.object(_history_module, "resolve_current_branch_name", return_value="Feature/Foo_Bar"),
        ):
            first = runner.invoke(history, ["ensure"])
            second = runner.invoke(history, ["ensure"])

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert first.output == ""
        assert second.output == ""
        assert (tmp_path / ".goga" / "history" / "2031" / "feature-foo-bar").is_dir()

    def test_history_ensure_explicit_name_creates_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ensure with an explicit NAME normalizes it — no git involved."""
        monkeypatch.chdir(tmp_path)

        with mock.patch.object(naming, "datetime", _FixedClock):
            result = CliRunner().invoke(history, ["ensure", "Feature/Foo_Bar"])

        assert result.exit_code == 0
        assert result.output == ""
        assert (tmp_path / ".goga" / "history" / "2031" / "feature-foo-bar").is_dir()

    def test_history_ensure_scoped_year_creates_and_is_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ensure addresses the scoped year: created there, twice a success, stdout empty."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        first = runner.invoke(history, ["-y", "2025", "ensure", "Feature/Foo_Bar"])
        second = runner.invoke(history, ["-y", "2025", "ensure", "Feature/Foo_Bar"])

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert first.output == ""
        assert second.output == ""
        assert (tmp_path / ".goga" / "history" / "2025" / "feature-foo-bar").is_dir()


class TestHistoryPrune:
    def test_history_prune_command_prints_slugs(self) -> None:
        """prune echoes one slug per line and forwards --dry-run to the domain."""
        runner = CliRunner()
        with mock.patch.object(
            _history_module, "prune_topics", return_value=["done-c", "orphan-b"]
        ) as prune_mock:
            result = runner.invoke(history, ["prune", "--dry-run"])

        assert result.exit_code == 0
        assert result.output == "done-c\norphan-b\n"
        prune_mock.assert_called_once_with(None, True)

    def test_history_prune_scoped_year_passes_year(self) -> None:
        """prune forwards the scoped year and --dry-run; the slug list prints."""
        runner = CliRunner()
        with mock.patch.object(_history_module, "prune_topics", return_value=["orphan-topic"]) as prune_mock:
            result = runner.invoke(history, ["-y", "2025", "prune", "--dry-run"])

        assert result.exit_code == 0
        assert result.output.splitlines() == ["orphan-topic"]
        prune_mock.assert_called_once_with("2025", True)

    @pytest.mark.parametrize(
        ("failure", "message"),
        [
            (subprocess.CalledProcessError(1, ["git"], stderr="boom"), "git failed: boom"),
            (FileNotFoundError("git"), "git is not available"),
            (OSError("disk quota"), "cannot delete topic directory"),
        ],
    )
    def test_history_prune_git_failure_is_clean_error(self, failure: Exception, message: str) -> None:
        """A domain failure surfaces as a clean error — exit 1, stderr, no traceback."""
        runner = CliRunner()
        with mock.patch.object(_history_module, "prune_topics", side_effect=failure):
            result = runner.invoke(history, ["prune"])

        assert result.exit_code == 1
        assert result.stdout == ""
        assert message in result.stderr
        assert "Traceback" not in result.stderr

    def test_history_prune_empty_slug_dir_is_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A manual empty-slug directory aborts the cleanup before any deletion."""
        year_dir = tmp_path / ".goga" / "history" / "2026"
        (year_dir / "orphan-a").mkdir(parents=True)
        (year_dir / "orphan-a" / "prd.md").write_text("prd\n", encoding="utf-8")
        (year_dir / "ББ").mkdir()
        (year_dir / "ББ" / "prd.md").write_text("prd\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        # The empty slug sorts first, so remove_topic_dir("") raises the
        # domain ValueError before the list is returned — the echo loop never
        # runs and nothing is deleted.
        with mock.patch("goga.history.prune.list_branch_refs", return_value=[]):
            result = CliRunner().invoke(history, ["-y", "2026", "prune"])

        assert result.exit_code == 1
        assert result.stdout == ""
        assert "normalizes to an empty topic slug" in result.stderr
        assert "Traceback" not in result.stderr
        assert (year_dir / "orphan-a").exists()


# --- Edge cases ---


class TestHistoryEmptyResults:
    def test_history_status_empty_result_prints_nothing_exit_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A year without topics prints nothing and exits 0 — not an error."""
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["-y", "1999", "status"])

        assert result.exit_code == 0
        assert result.output == ""

    def test_history_status_filter_matching_nothing_exit_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A filter matching nothing prints nothing and exits 0 — not an error."""
        year_dir = tmp_path / ".goga" / "history" / "2026"
        (year_dir / "history-commands").mkdir(parents=True)
        (year_dir / "history-commands" / "plan.md").write_text("plan\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["-y", "2026", "status", "-t", "nomatch"])

        assert result.exit_code == 0
        assert result.output == ""

    def test_history_list_absent_history_empty_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty workspace has an empty history — list prints nothing, exit 0."""
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["list"])

        assert result.exit_code == 0
        assert result.output == ""

    def test_history_empty_year_value_counts_as_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """-y '' is an empty CLI value — the domain reads it as no selection: full tree."""
        root = tmp_path / ".goga" / "history"
        (root / "2025" / "feat-a").mkdir(parents=True)
        (root / "2026" / "feat-b").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["-y", "", "list"])

        assert result.exit_code == 0
        assert "2025/" in result.output
        assert "2026/" in result.output

    def test_history_list_scoped_missing_year_prints_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A scoped year absent from the tree is empty — list prints nothing, exit 0."""
        (tmp_path / ".goga" / "history" / "2026" / "feat-x").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["-y", "2099", "list"])

        assert result.exit_code == 0
        assert result.output == ""
