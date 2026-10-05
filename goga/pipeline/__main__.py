"""Runpy entrypoint for ``python -m goga.pipeline``: ``ensure_in_docker`` first, then ``pipeline_cli``."""

from __future__ import annotations

import sys

from ..docker import ensure_in_docker
from .cli import pipeline_cli

if __name__ == "__main__":
    ensure_in_docker()
    sys.exit(pipeline_cli(sys.argv[1:]))
