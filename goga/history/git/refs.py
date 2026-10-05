"""The branch-ref inventory of the history-domain git cell."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class BranchRef:
    """One branch ref of the repository inventory.

    Attributes:
        name: The display name — the short branch name for a local ref,
            ``<remote>/<branch>`` for a remote-tracking ref.
        remote: ``True`` when the ref is remote-tracking.

    Requirements:
        The display name is the identity used by consumers — no
        reshortening, no normalization.
    """

    name: str
    remote: bool


def list_branch_refs() -> list[BranchRef]:
    """Enumerate the branch refs of the repository.

    Returns:
        Every branch ref, sorted alphabetically by display name.

    Algorithm:
        1. Ask git for the local branch refs
        2. Ask git for the remote-tracking refs
        3. Drop the ``<remote>/HEAD`` symrefs of the answers — they are
           pointers, not branches
        4. Merge both into one inventory sorted alphabetically by display
           name

    Requirements:
        Read-only — no ref is created, moved, or deleted. No network —
        remote-tracking refs as they exist locally.

    Constraints:
        Do not deduplicate — a local branch and its remote twin are two
        distinct refs here; collapsing them belongs to the caller.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            ref listing itself (propagated — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocations (e.g. a
            missing git binary).
    """
    local = _refs_under("refs/heads", remote=False)
    tracked = _refs_under("refs/remotes", remote=True)
    return sorted([*local, *tracked], key=lambda ref: ref.name)


def _refs_under(ref_prefix: str, remote: bool) -> list[BranchRef]:
    """Run one ``for-each-ref`` invocation and parse it into branch refs.

    Args:
        ref_prefix: The ref namespace to list — ``refs/heads`` or
            ``refs/remotes``.
        remote: Whether the listed refs are remote-tracking.

    Returns:
        The parsed refs of the namespace, in git order. Refs whose display
        name ends with ``/HEAD`` (the ``<remote>/HEAD`` symrefs) are not
        branches and are dropped.
    """
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname:short)", ref_prefix],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    return [
        BranchRef(name=line, remote=remote)
        for line in result.stdout.splitlines()
        if line and not line.endswith("/HEAD")
    ]
