"""Clone a git repository into a fresh temp directory (caller owns cleanup)."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def clone_repository(git: str, ref: str | None) -> Path:
    """Clone a git repository into a fresh temp dir and return its path.

    Used by ``sync`` to obtain a local working copy of a declared git dependency
    before deploying its cell-level usages. Interactive git prompts are
    suppressed via the ``git`` practice (``GIT_TERMINAL_PROMPT=0``).

    Cleanup ownership: on success the caller owns cleanup and must remove the
    returned path (``sync`` does this in a ``finally`` block). On failure — if the
    clone or checkout subprocess raises — this routine removes the temp dir it
    created before re-raising, so a failed clone never leaks. The caller only
    receives a path it is responsible for when the call succeeds.

    Args:
        git: Git repository URL (non-empty).
        ref: Optional git ref — branch, tag, or commit. ``None`` checks out the
            default branch (clone only).

    Returns:
        Path to the cloned repository temp directory.

    Raises:
        subprocess.CalledProcessError: If git exits non-zero (propagated).
        FileNotFoundError: If the git binary is not installed (propagated).
    """
    repo_path = Path(tempfile.mkdtemp())

    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    try:
        subprocess.run(
            ["git", "clone", git, str(repo_path)],
            check=True,
            capture_output=True,
            env=env,
        )

        if ref is not None:
            subprocess.run(
                ["git", "-C", str(repo_path), "checkout", ref],
                check=True,
                capture_output=True,
                env=env,
            )
    except BaseException:
        # The caller only owns cleanup on the success path; if we never return a
        # path, remove the temp dir we created so a failed clone does not leak.
        shutil.rmtree(repo_path, ignore_errors=True)
        raise

    return repo_path
