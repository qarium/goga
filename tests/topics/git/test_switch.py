"""Contract and logic tests for the entities declared in
``goga/topics/git/CODEMANIFEST`` with ``location: switch.py``:

- ``checkout_local_branch(branch)`` — switch the working copy to an
  existing local branch
- ``create_branch_from_remote_tracking(ref)`` — create a local branch
  from a remote-tracking ref and switch to it
- ``create_and_switch_branch(branch_name)`` — create a branch with the
  name exactly as entered and switch to it
- ``is_working_tree_clean()`` — the read-only cleanliness probe
- ``merge_into_current(revision, message)`` — merge a revision into the
  current branch as a real merge commit, never fast-forwarding
- ``rebase_current_onto(revision)`` — rebase the current branch onto a
  revision
- ``fast_forward_current_branch(revision)`` — advance the current branch
  to a revision without a merge commit

The subprocess call is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched.
"""

from __future__ import annotations

import inspect
import os
import subprocess
from unittest import mock

import pytest
from goga.topics.git import (
    BranchRef,
    checkout_local_branch,
    create_and_switch_branch,
    create_branch_from_remote_tracking,
    is_working_tree_clean,
)
from goga.topics.git.switch import (
    fast_forward_current_branch,
    merge_into_current,
    rebase_current_onto,
)


def _git_answer(stdout: str = "") -> subprocess.CompletedProcess[str]:
    """A successful git invocation answering ``stdout``."""
    return subprocess.CompletedProcess(args=["git"], returncode=0, stdout=stdout, stderr="")


def _commands_of(run: mock.Mock) -> list[list[str]]:
    """The argv list of every invocation the mock received."""
    return [call.args[0] for call in run.call_args_list]


# --- Contract tests ---


class TestSwitchContract:
    def test_entities_are_importable_from_the_cell_facade(self) -> None:
        """All four switch routines live on the cell facade."""
        import goga.topics.git as cell

        assert cell.checkout_local_branch is checkout_local_branch
        assert cell.create_branch_from_remote_tracking is create_branch_from_remote_tracking
        assert cell.create_and_switch_branch is create_and_switch_branch
        assert cell.is_working_tree_clean is is_working_tree_clean
        for name in (
            "checkout_local_branch",
            "create_branch_from_remote_tracking",
            "create_and_switch_branch",
            "is_working_tree_clean",
        ):
            assert name in cell.__all__

    def test_switch_routines_take_declared_parameters(self) -> None:
        """The routines take exactly the declared parameters."""
        assert list(inspect.signature(checkout_local_branch).parameters) == ["branch"]
        assert list(inspect.signature(create_branch_from_remote_tracking).parameters) == ["ref"]
        assert list(inspect.signature(create_and_switch_branch).parameters) == ["branch_name"]
        assert list(inspect.signature(is_working_tree_clean).parameters) == []

    def test_in_place_moves_are_importable_from_the_module(self) -> None:
        """The three in-place moves live on the switch module."""
        from goga.topics.git import switch

        assert switch.merge_into_current is merge_into_current
        assert switch.rebase_current_onto is rebase_current_onto
        assert switch.fast_forward_current_branch is fast_forward_current_branch

    def test_in_place_move_signatures(self) -> None:
        """The three in-place moves take exactly the declared parameters."""
        assert list(inspect.signature(merge_into_current).parameters) == ["revision", "message"]
        assert list(inspect.signature(rebase_current_onto).parameters) == ["revision"]
        assert list(inspect.signature(fast_forward_current_branch).parameters) == ["revision"]

    def test_in_place_moves_are_single_git_invocations(self) -> None:
        """Each in-place move is one bounded git invocation."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.switch.subprocess.run", run):
            merge_into_current("aa1", "Update topic 'feat-x'")
            rebase_current_onto("aa1")
            fast_forward_current_branch("aa1")

        assert run.call_count == 3

    def test_in_place_moves_follow_the_git_practice(self) -> None:
        """Every in-place move — check/capture/text and a muted prompt."""
        calls = [
            (merge_into_current, ("aa1", "Update topic 'feat-x'")),
            (rebase_current_onto, ("aa1",)),
            (fast_forward_current_branch, ("aa1",)),
        ]
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.switch.subprocess.run", run):
            for routine, args in calls:
                routine(*args)

        for call in run.call_args_list:
            kwargs = call.kwargs
            assert kwargs["check"] is True
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True
            assert kwargs["env"] == {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    def test_mutations_are_git_switch_invocations(self) -> None:
        """The three mutations are bounded host-side ``git switch`` actions."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.switch.subprocess.run", run):
            checkout_local_branch("feat/a")
            create_branch_from_remote_tracking(BranchRef(name="origin/feat/b", remote=True))
            create_and_switch_branch("Feature/Foo_Bar")

        assert _commands_of(run) == [
            ["git", "switch", "feat/a"],
            ["git", "switch", "-c", "feat/b", "origin/feat/b"],
            ["git", "switch", "-c", "Feature/Foo_Bar"],
        ]

    def test_cleanliness_probe_is_a_porcelain_invocation(self) -> None:
        """The probe reads the working tree state — nothing else."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.switch.subprocess.run", run):
            is_working_tree_clean()

        assert _commands_of(run) == [["git", "status", "--porcelain"]]

    def test_git_invocations_follow_the_git_practice(self) -> None:
        """Every call — check/capture/text and a muted prompt."""
        calls = [
            (checkout_local_branch, ("feat/a",)),
            (create_branch_from_remote_tracking, (BranchRef(name="origin/feat/b", remote=True),)),
            (create_and_switch_branch, ("Feature/Foo_Bar",)),
            (is_working_tree_clean, ()),
        ]
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.switch.subprocess.run", run):
            for routine, args in calls:
                routine(*args)

        assert run.call_count == len(calls)
        for call in run.call_args_list:
            kwargs = call.kwargs
            assert kwargs["check"] is True
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True
            assert kwargs["env"] == {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


# --- Logic tests ---


class TestSwitchBehaviour:
    @pytest.mark.parametrize(
        ("porcelain", "expected"),
        [
            pytest.param("", True, id="empty-report-is-clean"),
            pytest.param(" M x.py\n", False, id="any-entry-is-dirty"),
        ],
    )
    def test_is_working_tree_clean_boolean(self, porcelain: str, expected: bool) -> None:
        """An empty porcelain report is clean; any entry is dirty."""
        with mock.patch("goga.topics.git.switch.subprocess.run", return_value=_git_answer(porcelain)):
            assert is_working_tree_clean() is expected

    def test_create_branch_from_remote_tracking_takes_the_short_name(self) -> None:
        """The local branch is named after the part past the first slash."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.switch.subprocess.run", run):
            create_branch_from_remote_tracking(BranchRef(name="origin/feat/b", remote=True))

        assert _commands_of(run) == [["git", "switch", "-c", "feat/b", "origin/feat/b"]]

    def test_create_and_switch_branch_takes_the_name_verbatim(self) -> None:
        """No normalization, no suffixing — the name goes to git as entered."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.switch.subprocess.run", run):
            create_and_switch_branch("Feature/Foo_Bar")

        assert _commands_of(run) == [["git", "switch", "-c", "Feature/Foo_Bar"]]

    def test_checkout_local_branch_switches_without_creating(self) -> None:
        """A plain checkout — no ``-c``, the branch must already exist."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.switch.subprocess.run", run):
            checkout_local_branch("feat/a")

        assert _commands_of(run) == [["git", "switch", "feat/a"]]

    def test_merge_into_current_never_fast_forwards(self) -> None:
        """``--no-ff`` and ``--no-edit`` precede the revision — a merge
        commit lands even when a fast-forward is possible."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.switch.subprocess.run", run):
            merge_into_current("aa1", "Update topic 'feat-x'")

        assert _commands_of(run) == [
            ["git", "merge", "--no-ff", "--no-edit", "-m", "Update topic 'feat-x'", "aa1"],
        ]

    def test_rebase_current_onto_uses_rebase(self) -> None:
        """A plain rebase — no ``--onto`` forms, no autostash."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.switch.subprocess.run", run):
            rebase_current_onto("aa1")

        assert _commands_of(run) == [["git", "rebase", "aa1"]]

    def test_fast_forward_current_branch_uses_ff_only(self) -> None:
        """An ff-only merge — no fallback, no commit authored."""
        run = mock.Mock(return_value=_git_answer())

        with mock.patch("goga.topics.git.switch.subprocess.run", run):
            fast_forward_current_branch("aa1")

        assert _commands_of(run) == [["git", "merge", "--ff-only", "aa1"]]
