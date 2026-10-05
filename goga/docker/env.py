"""In-container environment assertion: guard routine for in-container entrypoints."""

from __future__ import annotations

import os
import sys


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
