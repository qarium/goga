"""Git-environment introspection for the history domain — the branch reader.

The single routine declared in the cell CODEMANIFEST with ``location:
branch.py``: the raw current-branch reader. Every git invocation follows the
``git`` practice — ``subprocess.run`` with ``check=True``, captured output, and
``GIT_TERMINAL_PROMPT=0`` in the environment. The reader is read-only; no
branch is switched and nothing is written.
"""

from __future__ import annotations

import os
import subprocess


def resolve_current_branch_name() -> str | None:
    """Read the current git branch name exactly as git reports it.

    Asks git via ``git branch --show-current`` (per the ``git`` practice) and
    returns the stripped answer unmodified — no slugification, no fallback
    value; both belong to the caller. ``None`` covers only the three documented
    failure modes: detached HEAD (an empty git answer), a missing git binary
    (``FileNotFoundError``), and a non-repository (a non-zero git exit).
    Read-only; the result is not cached — each call asks git anew.

    Returns:
        The raw current branch name (stripped, unmodified), or ``None`` when it
        cannot be determined.

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
