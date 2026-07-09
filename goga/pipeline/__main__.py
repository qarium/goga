"""Runpy entrypoint for ``python -m goga.pipeline``.

This module is a thin wrapper that delegates to :func:`pipeline_cli` from
:mod:`goga.pipeline.cli`. The CLI implementation MUST live in ``cli.py`` so
that importing the :mod:`goga.pipeline` package does not load ``__main__``
into ``sys.modules`` and trigger a ``runpy`` ``RuntimeWarning`` for
``python -m goga.pipeline``. See the ``cli_entrypoint`` practice in the
cell's ``CODEMANIFEST``.

The ``cli_entrypoint`` practice authorizes exactly one piece of logic in this
module's ``__main__`` block: the :func:`ensure_in_docker` guard, called as
the first statement before :func:`pipeline_cli` runs. The guard refuses to
proceed when the process is not inside the goga Docker image, so host-side
invocations of this in-container entrypoint fail loudly instead of silently
producing broken behavior.
"""

from __future__ import annotations

import sys

from ..docker import ensure_in_docker
from .cli import pipeline_cli

if __name__ == "__main__":
    ensure_in_docker()
    sys.exit(pipeline_cli(sys.argv[1:]))
