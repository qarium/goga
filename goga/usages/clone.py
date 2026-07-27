"""Clone a git repository into a fresh temp directory (caller owns cleanup)."""

import os
import subprocess
import tempfile
from pathlib import Path


def clone_repository(git: str, ref: str | None) -> Path:
    """Clone a git repository into a fresh temp dir and return its path.

    Used by ``sync`` to obtain a local working copy of a declared git dependency
    before deploying its cell-level usages. The caller owns cleanup: this routine
    creates the temp directory but never removes it — remove it in a ``finally``
    block at the call site. Interactive git prompts are suppressed via the ``git``
    practice (``GIT_TERMINAL_PROMPT=0``).

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

    return repo_path
