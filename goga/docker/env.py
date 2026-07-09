"""In-container environment assertion: guard routine for in-container entrypoints."""

from __future__ import annotations

import os
import sys


def ensure_in_docker() -> None:
    """Refuse to run when not inside the goga Docker image.

    Reads the ``GOGA_DOCKER`` environment marker (set only inside the goga
    Docker image at build time) and aborts the process when the marker is
    absent or not exactly ``"1"``. Host-side invocations of in-container
    entrypoints thus fail loudly instead of silently producing broken
    behavior (missing in-container binaries, wrong paths, missing runtime
    directories).

    On the success path (``GOGA_DOCKER == "1"``) the routine returns
    ``None`` with no side effects. On the refusal path it writes a message
    to ``sys.stderr`` and raises :class:`SystemExit` with code ``1`` before
    any filesystem or process work runs.

    Returns:
        ``None`` when running inside the goga Docker image.

    Raises:
        SystemExit: with code ``1`` when ``GOGA_DOCKER`` is unset or not
            exactly ``"1"``.
    """
    marker = os.environ.get("GOGA_DOCKER")

    if marker != "1":
        print(
            "This entrypoint must run inside the goga Docker image (GOGA_DOCKER=1). "
            "On the host, use 'goga build' or 'goga pipeline' instead.",
            file=sys.stderr,
        )

        sys.exit(1)
