"""The ref-tree reading of the topics-domain git cell.

The entities declared in the cell CODEMANIFEST with ``location: trees.py``:
the file paths of one ref tree under a path prefix, and the file contents
of one file of a ref tree. ``ls-tree`` and ``show`` walk the object
database of the repository — no checkout, no worktree, no temporary
directory — and every git invocation follows the ``git`` practice.
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


def read_ref_file(ref: str, path: str) -> str | None:
    """Read the content of one file of a ref tree.

    Args:
        ref: The ref to read — a display branch name as carried by
            :class:`~goga.topics.git.refs.BranchRef`.
        path: The file path to read, relative to the repository root.

    Returns:
        The file content as text, or None when the file is absent at
        the ref.

    Algorithm:
        1. Ask git for the content of ``path`` at the ``ref``
        2. An absent file at the ref yields None — not an error
        3. Return the content as text

    Requirements:
        One git invocation per file.

        Read-only — the working copy, the index, and ``.git`` stay
        untouched.

        The content is returned as-is — no interpretation, no
        transformation. The content is UTF-8 by the creation contract, so
        the invocation decodes UTF-8 explicitly — locale decoding breaks
        on non-ASCII content under the C/POSIX locale.

    Constraints:
        Do not materialize the tree — no checkout, no worktree, no temp
        directory.

        Do not list paths — path enumeration belongs to
        :func:`read_ref_tree_paths`.

    Raises:
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            missing git binary).
    """
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.CalledProcessError:
        return None

    return result.stdout
