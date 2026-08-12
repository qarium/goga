from __future__ import annotations

import os
import subprocess
from pathlib import Path


def resolve_project_name() -> str | None:
    """Derive the project name from the git origin remote URL.

    The project name is used by consumers as a description prefix / default
    identifier (pipeline flow-file description prefix; onboarding image-name
    default). It is derived from ``git config --get remote.origin.url`` — the
    same git remote the project bind-mount originates from — and is OUTPUT-only
    context, never read from ``.goga/config.yml`` (that is
    ``goga/config/project``'s responsibility).

    The basename of the URL is the project name, with a trailing ``.git``
    suffix stripped. The git subprocess is invoked per the ``git`` practice:
    ``check=True``, ``capture_output=True`` and ``GIT_TERMINAL_PROMPT=0`` in the
    env (suppress interactive prompts). Any failure resolves to ``None`` rather
    than raising: a missing ``git`` binary, not a git repo, no ``origin``
    remote configured (non-zero exit → :class:`subprocess.CalledProcessError`),
    an empty result, or a trailing-slash URL whose basename is empty.

    Returns:
        The derived project name, or ``None`` when it cannot be derived.
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
