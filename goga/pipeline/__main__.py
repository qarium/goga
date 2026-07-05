"""Runpy entrypoint for ``python -m goga.pipeline``.

This module is a thin wrapper that delegates to :func:`pipeline_cli` from
:mod:`goga.pipeline.cli`. The CLI implementation MUST live in ``cli.py`` so
that importing the :mod:`goga.pipeline` package does not load ``__main__``
into ``sys.modules`` and trigger a ``runpy`` ``RuntimeWarning`` for
``python -m goga.pipeline``. See the ``cli_entrypoint`` practice in the
cell's ``CODEMANIFEST``.
"""

from __future__ import annotations

import sys

from .cli import pipeline_cli

if __name__ == "__main__":
    sys.exit(pipeline_cli(sys.argv[1:]))
