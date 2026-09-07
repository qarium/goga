"""Contract and logic tests for the entities declared in
``goga/history/git/CODEMANIFEST`` with ``location: refs.py``:

- ``BranchRef(name, remote)`` — one branch ref of the repository inventory
- ``list_branch_refs()`` — the read-only enumerator merging local branches
  and remote-tracking refs into one sorted inventory

The module mirrors ``goga/topics/git/refs.py`` (the cells are unlinked by
design — no imports between them); the mirror equivalence is pinned by
``test_history_git_inventory_matches_topics_git``. The subprocess call is
mocked at the import point per the ``convention`` practice — no git binary
and no repository are touched.
"""

from __future__ import annotations

import dataclasses
import inspect
import os
import subprocess
import typing
from collections.abc import Callable
from unittest import mock

import pytest
from goga.history.git import BranchRef, list_branch_refs


def _git_answer(stdout: str) -> subprocess.CompletedProcess[str]:
    """A successful ``for-each-ref`` invocation answering ``stdout``."""
    return subprocess.CompletedProcess(args=["git"], returncode=0, stdout=stdout, stderr="")


def _answering_run(heads: str = "", remotes: str = "") -> Callable[..., subprocess.CompletedProcess[str]]:
    """A ``subprocess.run`` mock answering by the requested ref prefix."""

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        outputs = {"refs/heads": heads, "refs/remotes": remotes}
        return _git_answer(outputs[command[-1]])

    return run


# --- Contract tests ---


class TestRefsContract:
    def test_entities_are_importable_from_the_cell_facade(self) -> None:
        """``BranchRef`` and ``list_branch_refs`` live on the cell facade."""
        import goga.history.git as cell

        assert cell.BranchRef is BranchRef
        assert cell.list_branch_refs is list_branch_refs
        assert "BranchRef" in cell.__all__
        assert "list_branch_refs" in cell.__all__

    def test_facade_all_lists_the_three_declared_names(self) -> None:
        """The facade exports the branch reader and the branch inventory."""
        import goga.history.git

        assert goga.history.git.__all__ == [
            "BranchRef",
            "list_branch_refs",
            "resolve_current_branch_name",
        ]

    def test_branch_ref_is_a_frozen_kw_only_dataclass(self) -> None:
        """``BranchRef(name=..., remote=...)`` — frozen, keyword-only."""
        ref = BranchRef(name="feat/a", remote=False)

        assert ref.name == "feat/a"
        assert ref.remote is False

        with pytest.raises(TypeError):
            BranchRef("feat/a", False)  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            ref.name = "renamed"  # type: ignore[misc]

    def test_branch_ref_declares_name_and_remote_only(self) -> None:
        """The record carries exactly the two declared fields."""
        fields = {field.name for field in dataclasses.fields(BranchRef)}
        assert fields == {"name", "remote"}

    def test_list_branch_refs_signature(self) -> None:
        """``list_branch_refs() -> list[BranchRef]`` — no parameters."""
        signature = inspect.signature(list_branch_refs)
        assert list(signature.parameters) == []
        hints = typing.get_type_hints(list_branch_refs)
        assert hints == {"return": list[BranchRef]}

    def test_git_invocations_follow_the_git_practice(self) -> None:
        """Two ``for-each-ref`` calls — check/capture/text and a muted prompt."""
        run = mock.Mock(side_effect=_answering_run())

        with mock.patch("goga.history.git.refs.subprocess.run", run):
            list_branch_refs()

        assert run.call_count == 2
        for call in run.call_args_list:
            command = call.args[0]
            assert command[:2] == ["git", "for-each-ref"]
            assert "--format=%(refname:short)" in command
            assert call.kwargs["check"] is True
            assert call.kwargs["capture_output"] is True
            assert call.kwargs["text"] is True
            assert call.kwargs["env"] == {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        prefixes = [call.args[0][-1] for call in run.call_args_list]
        assert prefixes == ["refs/heads", "refs/remotes"]


# --- Logic tests ---


class TestListBranchRefs:
    def test_list_branch_refs_merges_and_sorts(self) -> None:
        """Local and remote refs merge sorted by display; ``*/HEAD`` dropped."""
        run = mock.Mock(
            side_effect=_answering_run(
                heads="main\nfeat/a\n",
                remotes="origin/HEAD\norigin/feat/a\n",
            )
        )

        with mock.patch("goga.history.git.refs.subprocess.run", run):
            refs = list_branch_refs()

        assert [ref.name for ref in refs] == ["feat/a", "main", "origin/feat/a"]
        assert [ref.remote for ref in refs] == [False, False, True]
        assert run.call_count == 2
        for call in run.call_args_list:
            assert call.kwargs["check"] is True
            assert call.kwargs["capture_output"] is True
            assert call.kwargs["text"] is True
            assert call.kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"

    def test_history_git_inventory_matches_topics_git(self) -> None:
        """The mirror implementations answer identically for one inventory."""
        from goga.history.git import refs as history_refs
        from goga.topics.git import refs as topics_refs

        run = mock.Mock(
            side_effect=_answering_run(
                heads="main\nfeat/a\n",
                remotes="origin/HEAD\norigin/feat/a\n",
            )
        )

        with (
            mock.patch("goga.history.git.refs.subprocess.run", run),
            mock.patch("goga.topics.git.refs.subprocess.run", run),
        ):
            history_result = history_refs.list_branch_refs()
            topics_result = topics_refs.list_branch_refs()

        assert [ref.name for ref in history_result] == [ref.name for ref in topics_result]
        assert [(ref.name, ref.remote) for ref in history_result] == [(ref.name, ref.remote) for ref in topics_result]

    def test_list_branch_refs_empty_repository(self) -> None:
        """An empty inventory is the norm, answered by exactly two calls."""
        run = mock.Mock(side_effect=_answering_run(heads="", remotes=""))

        with mock.patch("goga.history.git.refs.subprocess.run", run):
            refs = list_branch_refs()

        assert refs == []
        assert run.call_count == 2

    def test_list_branch_refs_propagates_git_failure(self) -> None:
        """A git infrastructure failure of the listing propagates unwrapped."""
        failure = subprocess.CalledProcessError(returncode=128, cmd=["git", "for-each-ref"])
        run = mock.Mock(side_effect=failure)

        with (
            mock.patch("goga.history.git.refs.subprocess.run", run),
            pytest.raises(subprocess.CalledProcessError),
        ):
            list_branch_refs()

    def test_list_branch_refs_propagates_missing_binary(self) -> None:
        """A missing git binary surfaces as the OS-level error of the call."""
        run = mock.Mock(side_effect=FileNotFoundError("git"))

        with (
            mock.patch("goga.history.git.refs.subprocess.run", run),
            pytest.raises(FileNotFoundError, match="git"),
        ):
            list_branch_refs()
