"""Contract and logic tests for the entity declared in
``goga/topics/git/CODEMANIFEST`` with ``location: trees.py``:

- ``read_ref_tree_paths(ref, prefix)`` — the read-only file listing of one
  ref tree under a path prefix, without checkout, worktree, or temp
  directories
- ``read_ref_file(ref, path)`` — the read-only content of one file of a
  ref tree, without checkout, worktree, or temp directories

The subprocess call is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched.
"""

from __future__ import annotations

import inspect
import os
import subprocess
import typing
from unittest import mock

from goga.topics.git import read_ref_file, read_ref_tree_paths


def _git_answer(stdout: str) -> subprocess.CompletedProcess[str]:
    """A successful git invocation answering ``stdout``."""
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
        assert command == [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            "--full-name",
            "--",
            "feat-a",
            ":/.goga/history/",
        ]
        kwargs = run.call_args.kwargs
        assert kwargs["check"] is True
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["env"] == {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    def test_git_invocation_separates_a_dash_leading_ref(self) -> None:
        """The ``--`` separator precedes the ref, never only the pathspec.

        A display name that starts with a dash (git accepts
        ``refs/heads/--mirror``, and the publish path plants names verbatim)
        would otherwise be parsed as an ls-tree option and fail every
        inventory read of the repository with ``unknown option``.
        """
        run = mock.Mock(return_value=_git_answer(""))
        with mock.patch("goga.topics.git.trees.subprocess.run", run):
            read_ref_tree_paths("--mirror", ".goga/history/")

        assert run.call_args.args[0] == [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            "--full-name",
            "--",
            "--mirror",
            ":/.goga/history/",
        ]

    def test_git_invocation_anchors_the_read_at_the_repository_root(self) -> None:
        """``--full-name`` and the ``:/`` pathspec magic pin both sides root.

        The contract anchors the prefix and the reported paths at the
        repository root, but git resolves a bare pathspec against the working
        directory and reports paths relative to it — a caller inside a
        subdirectory would read nothing while the publication write
        (``--cacheinfo``) lands at the root regardless, and the occupancy
        oracle would miss the very conflict it exists to catch. The magic
        prefix is handed to git only; the returned paths are matched against
        the caller's prefix unchanged.
        """
        run = mock.Mock(return_value=_git_answer(".goga/history/2026/feat-a/plan.md\n"))
        with mock.patch("goga.topics.git.trees.subprocess.run", run):
            paths = read_ref_tree_paths("feat-a", ".goga/history/2026/feat-a/")

        command = run.call_args.args[0]
        assert "--full-name" in command
        assert command[-1] == ":/.goga/history/2026/feat-a/"
        assert paths == [".goga/history/2026/feat-a/plan.md"]

    def test_file_entity_is_importable_from_the_cell_facade(self) -> None:
        """``read_ref_file`` lives on the fifteen-name cell facade."""
        import goga.topics.git as cell

        assert cell.read_ref_file is read_ref_file
        assert "read_ref_file" in cell.__all__
        assert cell.__all__ == sorted(cell.__all__)
        assert len(cell.__all__) == 15

    def test_file_signature_takes_ref_and_path_and_returns_optional_str(self) -> None:
        """``read_ref_file(ref: str, path: str) -> str | None``."""
        signature = inspect.signature(read_ref_file)

        assert list(signature.parameters) == ["ref", "path"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )

        hints = typing.get_type_hints(read_ref_file)
        assert hints == {"ref": str, "path": str, "return": str | None}


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


class TestReadRefFile:
    def test_read_ref_file_returns_content_as_is(self) -> None:
        """The content returns as-is — one ``git show``, UTF-8, muted prompt."""
        run = mock.Mock(return_value=_git_answer("Payment retry\n"))
        with mock.patch("goga.topics.git.trees.subprocess.run", run):
            content = read_ref_file("feat/a", ".goga/history/2026/feat-a/todo.md")

        assert content == "Payment retry\n"
        assert run.call_count == 1
        command = run.call_args.args[0]
        assert command == ["git", "show", "feat/a:.goga/history/2026/feat-a/todo.md"]
        kwargs = run.call_args.kwargs
        assert kwargs["check"] is True
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["env"] == {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    def test_read_ref_file_absent_file_returns_none(self) -> None:
        """An absent file at the ref yields None — not an error."""
        failure = subprocess.CalledProcessError(1, ["git", "show"], stderr="fatal: path 'x' does not exist")

        with mock.patch("goga.topics.git.trees.subprocess.run", side_effect=failure):
            content = read_ref_file("feat/a", ".goga/history/2026/feat-a/absent.md")

        assert content is None

    def test_read_ref_file_decodes_invalid_bytes_with_replacement(self) -> None:
        """A hand-edited non-UTF-8 file never crashes the read.

        The invocation decodes with the replacement policy — the content is
        display data (the todo column), so an undecodable byte degrades to
        U+FFFD instead of raising through the board's clean-error boundary.
        """
        run = mock.Mock(return_value=_git_answer("Pay�ment\n"))
        with mock.patch("goga.topics.git.trees.subprocess.run", run):
            content = read_ref_file("feat/a", ".goga/history/2026/feat-a/todo.md")

        assert content == "Pay�ment\n"
        assert run.call_args.kwargs["errors"] == "replace"

    def test_read_ref_file_empty_file_returns_empty_string(self) -> None:
        """An empty file is present — ``""`` differs from absence (``None``)."""
        run = mock.Mock(return_value=_git_answer(""))
        with mock.patch("goga.topics.git.trees.subprocess.run", run):
            content = read_ref_file("feat/a", ".goga/history/2026/feat-a/todo.md")

        assert content == ""
        assert run.call_count == 1
