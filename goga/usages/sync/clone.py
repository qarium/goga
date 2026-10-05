"""Clone a git repository into a fresh temp directory (caller owns cleanup)."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def clone_repository(git: str, ref: str | None) -> Path:
    """Clone a git repository into a fresh temp dir and return its path.

    Args:
        git: Git repository URL (non-empty).
        ref: Optional git ref — branch, tag, or commit. ``None`` checks out the
            default branch (clone only).

    Returns:
        Path to the cloned repository temp directory — the caller owns its cleanup; on failure the
        routine removes the temp dir it created before re-raising.

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
