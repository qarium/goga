"""In-container environment markers: the terminal guard and the non-terminal query."""

from __future__ import annotations

import os
import sys


def is_in_docker() -> bool:
    """Report whether the process runs inside the goga Docker image.

    The non-terminal, branching counterpart of ``ensure_in_docker``: instead
    of refusing to run, it answers the marker question so dual-surface
    launchers can choose their execution substrate (``docker run`` on the
    host, direct child execution inside the image).

    Returns:
        ``True`` only when ``GOGA_DOCKER`` equals exactly ``"1"`` — the same
        marker rule ``ensure_in_docker`` enforces; ``False`` for every other
        value including unset.
    """
    return os.environ.get("GOGA_DOCKER") == "1"


def ensure_in_docker() -> None:
    """Refuse to run when not inside the goga Docker image.

    Returns:
        ``None`` when running inside the goga Docker image — no side effects.

    Raises:
        SystemExit: with code ``1`` when ``GOGA_DOCKER`` is unset or not
            exactly ``"1"``, after a refusal message on ``sys.stderr``.
    """
    marker = os.environ.get("GOGA_DOCKER")

    if marker != "1":
        print(
            "This entrypoint must run inside the goga Docker image (GOGA_DOCKER=1). "
            "On the host, use 'goga build' or 'goga pipeline' instead.",
            file=sys.stderr,
        )

        sys.exit(1)
