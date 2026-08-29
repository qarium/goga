"""Contract and logic tests for the entities declared in
``goga/topics/git/CODEMANIFEST`` with ``location: switch.py``:

- ``checkout_local_branch(branch)`` — switch the working copy to an
  existing local branch
- ``create_branch_from_remote_tracking(ref)`` — create a local branch
  from a remote-tracking ref and switch to it
- ``create_and_switch_branch(branch_name)`` — create a branch with the
  name exactly as entered and switch to it
- ``is_working_tree_clean()`` — the read-only cleanliness probe

The subprocess call is mocked at the import point per the ``convention``
practice — no git binary and no repository are touched.
"""

from __future__ import annotations

import inspect
import os
import subprocess
from unittest import mock

from goga.topics.git import (
    BranchRef,
    checkout_local_branch,
    create_and_switch_branch,
    create_branch_from_remote_tracking,
    is_working_tree_clean,
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

    def test_declared_signatures(self) -> None:
        """The routines take exactly the declared parameters."""
        assert list(inspect.signature(checkout_local_branch).parameters) == ["branch"]
        assert list(inspect.signature(create_branch_from_remote_tracking).parameters) == ["ref"]
        assert list(inspect.signature(create_and_switch_branch).parameters) == ["branch_name"]
        assert list(inspect.signature(is_working_tree_clean).parameters) == []

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
    def test_is_working_tree_clean_boolean(self) -> None:
        """An empty porcelain report is clean; any entry is dirty."""
        with mock.patch("goga.topics.git.switch.subprocess.run", return_value=_git_answer("")):
            assert is_working_tree_clean() is True
        with mock.patch("goga.topics.git.switch.subprocess.run", return_value=_git_answer(" M x.py\n")):
            assert is_working_tree_clean() is False

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
