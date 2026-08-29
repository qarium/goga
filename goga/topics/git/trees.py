"""The ref-tree reading of the topics-domain git cell.

The entity declared in the cell CODEMANIFEST with ``location: trees.py``:
the file paths of one ref tree under a path prefix. ``ls-tree`` walks the
object database of the repository — no checkout, no worktree, no
temporary directory — and every git invocation follows the ``git``
practice.
"""

from __future__ import annotations

import os
import subprocess


def read_ref_tree_paths(ref: str, prefix: str) -> list[str]:
    """Read the file paths of one ref tree under a path prefix.

    Args:
        ref: The ref to read — a display branch name as carried by
            :class:`~goga.topics.git.refs.BranchRef`.
        prefix: The path prefix to read under, relative to the repository
            root.

    Returns:
        Every file path under the prefix, relative to the repository root,
        in the order git reports.

    Algorithm:
        1. Ask git for the recursive file listing of the ``ref`` tree
        2. Keep the paths that sit under ``prefix``
        3. Return them in the order git reports

    Requirements:
        One git invocation per ref.

        Read-only — the working copy, the index, and ``.git`` stay
        untouched.

        A ref or prefix without matches yields an empty list — not an
        error.

    Constraints:
        Do not materialize the tree — no checkout, no worktree, no temp
        directory.

        Do not inspect file contents — paths only.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            tree listing itself (propagated — the caller wraps it).
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "--", prefix],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    return [path for path in result.stdout.splitlines() if path and path.startswith(prefix)]
