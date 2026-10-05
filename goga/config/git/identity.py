from __future__ import annotations

import os
import subprocess
from pathlib import Path


def resolve_project_name() -> str | None:
    """Derive the project name from the git origin remote URL — the basename with a trailing ``.git`` stripped.

    Returns:
        The derived project name, or ``None`` when it cannot be derived (missing git binary, missing
        ``origin`` remote, empty output, or a trailing-slash URL).
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            check=True,
            cwd=str(Path.cwd()),
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    url = result.stdout.strip()
    if not url:
        return None

    # ``os.path.basename`` is intentional over ``Path(url).name``: the former
    # returns ``""`` for a trailing-slash URL (e.g. ``".../acme/"``) while the
    # latter returns ``"acme"`` — the trailing-slash case must resolve to
    # ``None`` (no prefix), so the basename-empty guard below fires. noqa: PTH119
    name = os.path.basename(url)  # noqa: PTH119
    if name.endswith(".git"):
        name = name[:-4]

    return name or None
