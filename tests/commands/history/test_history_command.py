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

import sys
from datetime import datetime
from pathlib import Path
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


class TestHistoryStatus:
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

        result = CliRunner().invoke(history, ["status", "2026", "-t", "Release/1.3.0", "-s", "done"])

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

        result = CliRunner().invoke(history, ["status", "2026", "-s", "planned", "-s", "done"])

        assert result.exit_code == 0
        assert result.output.splitlines() == ["done-topic [done]", "planned-topic [planned]"]
        assert "defined-topic" not in result.output


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

    def test_history_path_explicit_topic_and_year(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """path takes an explicit branch-name topic; -y overrides the year."""
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["path", "release/1.3.0", "-f", "plan.md", "-y", "2025"])

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


# --- Edge cases ---


class TestHistoryEmptyResults:
    def test_history_status_empty_result_exit_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A filter matching nothing prints nothing and exits 0 — not an error."""
        year_dir = tmp_path / ".goga" / "history" / "2026"
        (year_dir / "history-commands").mkdir(parents=True)
        (year_dir / "history-commands" / "plan.md").write_text("plan\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(history, ["status", "2026", "-t", "nomatch"])

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
