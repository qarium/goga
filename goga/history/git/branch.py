"""Git-environment introspection for the history domain — the branch reader."""

from __future__ import annotations

import os
import subprocess


def resolve_current_branch_name() -> str | None:
    """Read the current git branch name exactly as git reports it.

    Returns:
        The raw current branch name (stripped, unmodified), or ``None`` for
        exactly the three failure modes: detached HEAD, a missing git binary,
        a non-repository.

    Raises:
        OSError: unexpected OS-level failures of the git invocation (e.g. a
            ``PermissionError``); the ``None`` result covers only the
            documented failure modes.
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    if value == "":
        return None

    return value
