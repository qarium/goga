"""In-container CLI entrypoint for ``python -m goga.pipeline``.

Parses argv via :mod:`argparse` and dispatches to :func:`list_pipelines`
(discovery) or :func:`run_pipeline` (run). This entrypoint is invoked by the
host-side docker launcher in :mod:`goga.commands.pipeline` — it is never
imported by Python from the host side (docker runtime boundary, no
``Imports``). The host launches it via
``docker run ... python -m goga.pipeline {list|run} ...``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .list_pipelines import list_pipelines
from .pipeline_entry import PipelineSource
from .run_pipeline import run_pipeline


def pipeline_cli(argv: list[str]) -> int:
    """In-container CLI entrypoint for ``python -m goga.pipeline``.

    Parses ``argv`` via :mod:`argparse` and dispatches to discovery
    (:func:`list_pipelines`) or run (:func:`run_pipeline`).

    Args:
        argv: argument list, typically the process argv minus the program name
            (e.g. ``["list"]`` or ``["run", "deploy", "--port", "50321"]``).

    Returns:
        ``0`` on success; ``2`` on an argparse error (missing subcommand,
        missing ``NAME``, missing/invalid ``--port``); otherwise the
        ``exit_code`` propagated from :func:`run_pipeline`.
    """
    parser = argparse.ArgumentParser(
        prog="goga.pipeline",
        description="Run goga pipelines inside the goga Docker image.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="list available pipelines")

    run_parser = subparsers.add_parser("run", help="run a pipeline by name")
    run_parser.add_argument("name", help="pipeline name without extension")
    run_parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="TCP port forwarded to `afm run --port` (allocated by the host launcher).",
    )

    args = parser.parse_args(argv)

    project_dir = Path.cwd() / ".goga" / "pipelines"
    user_dir = Path.home() / ".goga" / "pipelines"

    if args.command == "list":
        entries = list_pipelines(project_dir, user_dir)
        print("Available pipelines:")
        for entry in entries:
            suffix = " (project)" if entry.source == PipelineSource.PROJECT else ""
            print(f"  {entry.name}{suffix}")
        return 0

    return run_pipeline(args.name, project_dir, user_dir, args.port)


if __name__ == "__main__":
    sys.exit(pipeline_cli(sys.argv[1:]))
