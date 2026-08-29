"""Contract and logic tests for the entity declared in
``goga/topics/git/CODEMANIFEST`` with ``location: trees.py``:

- ``read_ref_tree_paths(ref, prefix)`` — the read-only file listing of one
  ref tree under a path prefix, without checkout, worktree, or temp
  directories

The subprocess call is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched.
"""

from __future__ import annotations

import os
import subprocess
from unittest import mock

from goga.topics.git import read_ref_tree_paths


def _git_answer(stdout: str) -> subprocess.CompletedProcess[str]:
    """A successful ``ls-tree`` invocation answering ``stdout``."""
    return subprocess.CompletedProcess(args=["git"], returncode=0, stdout=stdout, stderr="")


# --- Contract tests ---


class TestTreesContract:
    def test_entity_is_importable_from_the_cell_facade(self) -> None:
        """``read_ref_tree_paths`` lives on the cell facade."""
        import goga.topics.git as cell

        assert cell.read_ref_tree_paths is read_ref_tree_paths
        assert "read_ref_tree_paths" in cell.__all__

    def test_signature_takes_ref_and_prefix_and_returns_paths(self) -> None:
        """``read_ref_tree_paths(ref, prefix) -> list[str]``."""
        with (
            mock.patch(
                "goga.topics.git.trees.subprocess.run",
                return_value=_git_answer(".goga/history/2026/feat-a/plan.md\n"),
            ) as run,
        ):
            paths = read_ref_tree_paths("feat-a", ".goga/history/")

        assert isinstance(paths, list)
        assert all(isinstance(path, str) for path in paths)
        assert run.call_count == 1

    def test_git_invocation_follows_the_git_practice(self) -> None:
        """One ``ls-tree -r --name-only`` call — check/capture/text, muted prompt."""
        run = mock.Mock(return_value=_git_answer(""))
        with mock.patch("goga.topics.git.trees.subprocess.run", run):
            read_ref_tree_paths("feat-a", ".goga/history/")

        assert run.call_count == 1
        command = run.call_args.args[0]
        assert command == ["git", "ls-tree", "-r", "--name-only", "feat-a", "--", ".goga/history/"]
        kwargs = run.call_args.kwargs
        assert kwargs["check"] is True
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["env"] == {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


# --- Logic tests ---


class TestReadRefTreePaths:
    def test_read_ref_tree_paths_filters_prefix(self) -> None:
        """Only paths under the prefix survive — one invocation per ref."""
        run = mock.Mock(return_value=_git_answer(".goga/history/2026/feat-a/plan.md\nREADME.md\n"))
        with mock.patch("goga.topics.git.trees.subprocess.run", run):
            result = read_ref_tree_paths("feat-a", ".goga/history/")

        assert result == [".goga/history/2026/feat-a/plan.md"]
        assert run.call_count == 1

    def test_read_ref_tree_paths_no_matches_empty(self) -> None:
        """A ref or prefix without matches yields an empty list — not an error."""
        with mock.patch("goga.topics.git.trees.subprocess.run", return_value=_git_answer("")):
            assert read_ref_tree_paths("feat-a", ".goga/history/") == []

    def test_read_ref_tree_paths_keeps_git_order(self) -> None:
        """Paths return in the order git reports them."""
        stdout = ".goga/history/2026/feat-a/plan.md\n.goga/history/2026/feat-a/prd.md\n"
        with mock.patch("goga.topics.git.trees.subprocess.run", return_value=_git_answer(stdout)):
            result = read_ref_tree_paths("feat-a", ".goga/history/")

        assert result == [".goga/history/2026/feat-a/plan.md", ".goga/history/2026/feat-a/prd.md"]
