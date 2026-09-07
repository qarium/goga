"""The branch mutations of the topics-domain git cell.

The entities declared in the cell CODEMANIFEST with
``location: switch.py``: checking out an existing local branch, creating
a local branch from a remote-tracking ref, create-and-switch to a new
branch, and the working-tree cleanliness probe. They are bounded
host-side git actions — when a switch is allowed stays with the caller.
Every git invocation follows the ``git`` practice.
"""

from __future__ import annotations

import os
import subprocess

from .refs import BranchRef


def checkout_local_branch(branch: str) -> None:
    """Switch the working copy to an existing local branch.

    Args:
        branch: The short name of the local branch.

    Algorithm:
        1. Ask git to check out the branch
        2. A git failure surfaces as a clean error

    Requirements:
        The mutation is local — no network, no push, no fetch.

    Constraints:
        Do not create the branch — it must exist.

        Do not decide when a switch is allowed — the caller owns the
        cleanliness policy.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            checkout itself (propagated — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    _run_git(["git", "switch", branch])


def create_branch_from_remote_tracking(ref: BranchRef) -> None:
    """Create a local branch from a remote-tracking ref and switch to it.

    The local branch takes the short name of the ref — the part after the
    first slash of its display name.

    Args:
        ref: The remote-tracking ref to branch from.

    Algorithm:
        1. Ask git to create a local branch named after the short name of
           ``ref`` at the ref's commit and switch to it
        2. A git failure surfaces as a clean error

    Requirements:
        The mutation is local — the remote-tracking ref as it exists
        locally, no network.

    Constraints:
        Do not update the remote-tracking ref — no fetch.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            branch creation itself (propagated — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    short = ref.name.partition("/")[2]
    _run_git(["git", "switch", "-c", short, ref.name])


def create_and_switch_branch(branch_name: str) -> None:
    """Create a branch with the name exactly as entered and switch to it.

    Args:
        branch_name: The branch name as entered by the user.

    Algorithm:
        1. Ask git to create the branch named exactly ``branch_name`` and
           switch to it
        2. A name git rejects surfaces as a clean error

    Requirements:
        The name is taken verbatim — no normalization, no suffixing.

        The mutation is local.

    Constraints:
        Do not validate the name characters — git owns name validity.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            branch creation itself (propagated — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    _run_git(["git", "switch", "-c", branch_name])


def is_working_tree_clean() -> bool:
    """Probe whether the working copy carries uncommitted changes.

    Returns:
        True when the working tree and the index match the branch head.

    Algorithm:
        1. Ask git for the working tree state
        2. Report the answer as a plain boolean

    Requirements:
        Read-only — nothing is staged, committed, or reset.

    Constraints:
        Do not act on a dirty tree — the caller owns the policy.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            state probe itself (propagated — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    return _run_git(["git", "status", "--porcelain"]).stdout.strip() == ""


def _run_git(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one git invocation following the ``git`` practice.

    Args:
        command: The argv of the invocation, starting with ``git``.

    Returns:
        The completed invocation with captured text output.
    """
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
