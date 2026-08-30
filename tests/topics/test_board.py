"""Contract and logic tests for the entities declared in
``goga/topics/CODEMANIFEST`` with ``location: board.py``:

- ``BoardRecord(topic, branch, statuses, current, remote, title)`` — one row
  of the topic board, a topic hosted by one branch with its title
- ``collect_topic_board(year, remote)`` — the read-only cross-branch topic
  inventory of one year

The git boundary is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched; the working-copy
scenarios use ``tmp_path`` + ``monkeypatch.chdir`` with the real history
path routines, and the scale is the ``builtin_scale`` fixture.
"""

from __future__ import annotations

import dataclasses
import inspect
import subprocess
import typing
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.history.statuses import StatusScale
from goga.topics import BoardRecord, board, collect_topic_board
from goga.topics.git import BranchRef

# --- Shared scenario helpers ---


def _trees_reader(trees: dict[str, list[str]]) -> Callable[..., list[str]]:
    """A ``read_ref_tree_paths`` stand-in answering by ref display name."""

    def read(ref: str, prefix: str) -> list[str]:
        assert prefix == ".goga/history/", "the board reads under the history root only"
        return [path for path in trees.get(ref, []) if path.startswith(prefix)]

    return read


def _files_reader(files: dict[tuple[str, str], str]) -> Callable[..., str | None]:
    """A ``read_ref_file`` stand-in answering by ``(ref, path)``.

    A key missing from the dict answers ``None`` — the mirror of the
    ``read_ref_file`` absence contract.
    """

    def read(ref: str, path: str) -> str | None:
        return files.get((ref, path))

    return read


def _wire_board(  # noqa: PLR0913, PLR0917 — the five board patch points plus the scenario files

    monkeypatch: pytest.MonkeyPatch,
    scale: StatusScale,
    inventory: list[BranchRef],
    trees: dict[str, list[str]],
    current: str | None,
    files: dict[tuple[str, str], str] | None = None,
) -> None:
    """Patch the board's import points: scale, git, trees, branch, files.

    Without ``files`` every ref title reads as ``None`` — no title file at
    any ref.
    """
    monkeypatch.setattr(board, "assemble_status_scale", lambda: scale)
    monkeypatch.setattr(board, "list_branch_refs", lambda: inventory)
    monkeypatch.setattr(board, "resolve_current_branch_name", lambda: current)
    monkeypatch.setattr(board, "read_ref_tree_paths", _trees_reader(trees))
    monkeypatch.setattr(board, "read_ref_file", _files_reader(files or {}))


def _working_copy_topic(cwd: Path, year: str, slug: str, artifacts: list[str]) -> None:
    """Create the working-copy topic directory with its artifact files."""
    for artifact in artifacts:
        path = cwd / ".goga" / "history" / year / slug / artifact
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact", encoding="utf-8")


def _working_title(cwd: Path, year: str, slug: str, content: str) -> None:
    """Write the working-copy title file of a topic with the given content."""
    path = cwd / ".goga" / "history" / year / slug / "title.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _base_inventory() -> list[BranchRef]:
    """The design-scenario inventory: two locals, two remote-tracking refs."""
    return [
        BranchRef(name="feat/a", remote=False),
        BranchRef(name="origin/feat/a", remote=True),
        BranchRef(name="origin/feat/b", remote=True),
        BranchRef(name="main", remote=False),
    ]


def _base_trees() -> dict[str, list[str]]:
    """The design-scenario ref trees: one planned topic, one defined topic."""
    return {
        "feat/a": [".goga/history/2026/feat-a/plan.md"],
        "origin/feat/a": [".goga/history/2026/feat-a/plan.md"],
        "origin/feat/b": [".goga/history/2026/feat-b/prd.md"],
        "main": ["README.md"],
    }


def _rows(records: list[BoardRecord]) -> list[tuple[str, str, list[str], bool, bool, str | None]]:
    """The records as plain tuples — topic, branch, statuses, current, remote, title."""
    return [
        (
            record.topic,
            record.branch,
            record.statuses,
            record.current,
            record.remote,
            record.title,
        )
        for record in records
    ]


# --- Contract tests ---


class TestBoardContract:
    def test_entities_are_importable_from_the_cell_facade(self) -> None:
        """``BoardRecord`` and ``collect_topic_board`` live on the cell facade."""
        import goga.topics as cell

        assert cell.BoardRecord is BoardRecord
        assert cell.collect_topic_board is collect_topic_board
        assert "BoardRecord" in cell.__all__
        assert "collect_topic_board" in cell.__all__

    def test_board_record_is_a_frozen_kw_only_dataclass(self) -> None:
        """``@dataclass(frozen=True, kw_only=True)`` with the six declared fields."""
        assert dataclasses.is_dataclass(BoardRecord)
        assert BoardRecord.__dataclass_params__.frozen is True
        assert BoardRecord.__dataclass_params__.kw_only is True
        assert typing.get_type_hints(BoardRecord) == {
            "topic": str,
            "branch": str,
            "statuses": list[str],
            "current": bool,
            "remote": bool,
            "title": str | None,
        }
        record = BoardRecord(
            topic="feat-a", branch="feat/a", statuses=["planned"], current=True, remote=False
        )
        assert record.topic == "feat-a"
        assert record.branch == "feat/a"
        assert record.statuses == ["planned"]
        assert record.current is True
        assert record.remote is False
        assert record.title is None
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.topic = "other"  # type: ignore[misc]
        with pytest.raises(TypeError):
            BoardRecord("feat-a", "feat/a", ["planned"], True, False)  # type: ignore[misc]

    def test_board_record_declares_title_field(self) -> None:
        """The title field: ``str | None``, sixth, defaulting to ``None``."""
        hints = typing.get_type_hints(BoardRecord)
        assert hints["title"] == str | None
        assert [field.name for field in dataclasses.fields(BoardRecord)] == [
            "topic",
            "branch",
            "statuses",
            "current",
            "remote",
            "title",
        ]
        # The default keeps every pre-title constructor valid.
        record = BoardRecord(topic="a", branch="b", statuses=[], current=False, remote=False)
        assert record.title is None
        titled = BoardRecord(
            topic="a", branch="b", statuses=[], current=False, remote=False, title="Payment retry"
        )
        assert titled.title == "Payment retry"

    def test_collect_topic_board_signature(self) -> None:
        """``collect_topic_board(year=None, remote=False) -> list[BoardRecord]``."""
        signature = inspect.signature(collect_topic_board)
        assert list(signature.parameters) == ["year", "remote"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for parameter in signature.parameters.values()
        )
        assert signature.parameters["year"].default is None
        assert signature.parameters["remote"].default is False
        hints = typing.get_type_hints(collect_topic_board)
        assert hints == {"year": str | None, "remote": bool, "return": list[BoardRecord]}


# --- Logic tests ---


class TestCollectTopicBoard:
    def test_collect_topic_board_local_collapses_twin_and_marks_current(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Local mode: full inventory, the twin collapses, the host is marked."""
        monkeypatch.chdir(tmp_path)
        _working_copy_topic(tmp_path, "2026", "feat-a", ["plan.md"])
        _wire_board(monkeypatch, builtin_scale, _base_inventory(), _base_trees(), "feat/a")

        records = collect_topic_board("2026", remote=False)

        assert _rows(records) == [
            ("feat-b", "origin/feat/b", ["defined"], False, True, None),
            ("feat-a", "feat/a", ["planned"], True, False, None),
        ]
        # The remote twin collapsed into the local row — the local branch wins.
        assert "origin/feat/a" not in [record.branch for record in records]
        # A ref without a topic of the year hosts no row.
        assert "main" not in [record.branch for record in records]
        # Sorting: feat-b (defined, scale position 1) precedes feat-a (planned, position 6).
        assert [record.topic for record in records] == ["feat-b", "feat-a"]

    def test_collect_topic_board_remote_mode_twin_current(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Remote mode: remote-tracking rows only; the twin carries the marker."""
        monkeypatch.chdir(tmp_path)
        _wire_board(monkeypatch, builtin_scale, _base_inventory(), _base_trees(), "feat/a")
        statuses = mock.Mock()
        monkeypatch.setattr(board, "resolve_topic_status", statuses)

        records = collect_topic_board("2026", remote=True)

        assert _rows(records) == [
            ("feat-b", "origin/feat/b", ["defined"], False, True, None),
            ("feat-a", "origin/feat/a", ["planned"], True, True, None),
        ]
        assert [record.branch for record in records] == ["origin/feat/b", "origin/feat/a"]
        # Remote mode never reads the working copy — the current branch shows
        # through its remote twin.
        assert statuses.call_count == 0

    def test_collect_topic_board_year_without_topics_empty(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A year without hosted topics yields an empty list — not an error."""
        monkeypatch.chdir(tmp_path)
        _working_copy_topic(tmp_path, "2026", "feat-a", ["plan.md"])
        _wire_board(monkeypatch, builtin_scale, _base_inventory(), _base_trees(), "feat/a")

        assert collect_topic_board("2030") == []

    def test_collect_topic_board_reads_titles_local_and_ref(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Titles: the working copy for the current branch, ref trees for the rest."""
        monkeypatch.chdir(tmp_path)
        _working_copy_topic(tmp_path, "2026", "feat-a", ["plan.md"])
        _working_title(tmp_path, "2026", "feat-a", "Local title\nsecond\n")
        trees = {
            **_base_trees(),
            # Without a year topic on main there is no main row — and the
            # absent-title case stays unmeasured.
            "main": [".goga/history/2026/main-only/prd.md", "README.md"],
        }
        files = {("origin/feat/b", ".goga/history/2026/feat-b/title.txt"): "Remote title\n"}
        _wire_board(monkeypatch, builtin_scale, _base_inventory(), trees, "feat/a", files)

        records = collect_topic_board("2026")

        assert _rows(records) == [
            ("feat-b", "origin/feat/b", ["defined"], False, True, "Remote title"),
            ("main-only", "main", ["defined"], False, False, None),
            ("feat-a", "feat/a", ["planned"], True, False, "Local title"),
        ]

    def test_collect_topic_board_title_first_line_and_empty(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A multi-line title yields its first line; empty stays empty; absent is None."""
        monkeypatch.chdir(tmp_path)
        _working_copy_topic(tmp_path, "2026", "feat-a", ["plan.md"])
        _working_title(tmp_path, "2026", "feat-a", "A\nB\n")
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="feat/b", remote=False),
            BranchRef(name="feat/c", remote=False),
        ]
        trees = {
            "feat/a": [".goga/history/2026/feat-a/plan.md"],
            "feat/b": [".goga/history/2026/feat-b/plan.md"],
            "feat/c": [".goga/history/2026/feat-c/plan.md"],
        }
        files = {("feat/b", ".goga/history/2026/feat-b/title.txt"): ""}
        _wire_board(monkeypatch, builtin_scale, inventory, trees, "feat/a", files)

        records = collect_topic_board("2026")

        # All planned — the order is the slug alphabet, never the titles.
        assert _rows(records) == [
            ("feat-a", "feat/a", ["planned"], True, False, "A"),
            ("feat-b", "feat/b", ["planned"], False, False, ""),
            ("feat-c", "feat/c", ["planned"], False, False, None),
        ]

    def test_current_branch_empty_slug_hosts_no_topic(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A fully non-ASCII current branch hosts nothing — and breaks nothing."""
        monkeypatch.chdir(tmp_path)
        inventory = [BranchRef(name="🚀", remote=False), BranchRef(name="feat/a", remote=False)]
        trees = {"feat/a": [".goga/history/2026/feat-a/plan.md"]}
        exists = mock.Mock(return_value=False)
        monkeypatch.setattr(board, "topic_exists", exists)
        _wire_board(monkeypatch, builtin_scale, inventory, trees, "🚀")

        records = collect_topic_board("2026")

        assert _rows(records) == [("feat-a", "feat/a", ["planned"], False, False, None)]
        # The empty-slug guard runs before the existence oracle — the board is
        # never crashed by the branch that cannot host a topic.
        assert exists.call_count == 0

    def test_collect_topic_board_no_current_branch(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No current branch — no marker, every status from the ref trees."""
        monkeypatch.chdir(tmp_path)
        _wire_board(monkeypatch, builtin_scale, _base_inventory(), _base_trees(), None)
        statuses = mock.Mock()
        monkeypatch.setattr(board, "resolve_topic_status", statuses)

        records = collect_topic_board("2026")

        assert _rows(records) == [
            ("feat-b", "origin/feat/b", ["defined"], False, True, None),
            ("feat-a", "feat/a", ["planned"], False, False, None),
        ]
        assert all(not record.current for record in records)
        # Without a current branch the working copy is not read at all.
        assert statuses.call_count == 0

    def test_board_sees_only_committed_artifacts_on_other_refs(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The current row sees uncommitted progress; the trees see commits only."""
        monkeypatch.chdir(tmp_path)
        _working_copy_topic(tmp_path, "2026", "feat-a", ["plan.md"])
        inventory = [
            BranchRef(name="feat/a", remote=False),
            BranchRef(name="origin/feat/a", remote=True),
        ]
        trees = {
            "feat/a": [".goga/history/2026/feat-a/notes.txt"],
            "origin/feat/a": [".goga/history/2026/feat-a/notes.txt"],
        }
        _wire_board(monkeypatch, builtin_scale, inventory, trees, "feat/a")

        local_rows = _rows(collect_topic_board("2026", remote=False))
        remote_rows = _rows(collect_topic_board("2026", remote=True))

        # The current branch reads the working copy — the uncommitted plan.md
        # is visible.
        assert local_rows == [("feat-a", "feat/a", ["planned"], True, False, None)]
        # The same work through its remote twin reads the ref tree — the
        # uncommitted artifact is invisible there.
        assert remote_rows == [("feat-a", "origin/feat/a", ["empty"], True, True, None)]


class TestBoardInfrastructureBoundary:
    def test_git_failure_surfaces_as_clean_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A git infrastructure failure with stderr becomes a ``ClickException``."""
        monkeypatch.chdir(tmp_path)
        failure = subprocess.CalledProcessError(
            returncode=128, cmd=["git", "for-each-ref"], stderr="fatal: not a git repository"
        )
        monkeypatch.setattr(board, "assemble_status_scale", lambda: builtin_scale)
        monkeypatch.setattr(board, "list_branch_refs", mock.Mock(side_effect=failure))

        with pytest.raises(click.ClickException) as raised:
            collect_topic_board("2026")

        assert "fatal: not a git repository" in raised.value.message

    def test_missing_git_binary_surfaces_as_clean_error(
        self,
        builtin_scale: StatusScale,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A missing git binary becomes a ``ClickException``."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(board, "assemble_status_scale", lambda: builtin_scale)
        monkeypatch.setattr(board, "list_branch_refs", mock.Mock(side_effect=FileNotFoundError("git")))

        with pytest.raises(click.ClickException):
            collect_topic_board("2026")

    def test_broken_tool_package_import_surfaces_as_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fatal scale-assembly ``ImportError`` keeps its package name."""
        monkeypatch.chdir(tmp_path)
        broken = ImportError("package goga_tool_bad failed to import: boom")
        monkeypatch.setattr(board, "assemble_status_scale", mock.Mock(side_effect=broken))

        with pytest.raises(click.ClickException) as raised:
            collect_topic_board("2026")

        assert raised.value.message == "package goga_tool_bad failed to import: boom"
