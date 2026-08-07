"""In-container CLI implementation for ``python -m goga.pipeline``.

Parses argv via :mod:`argparse` and dispatches to :func:`list_pipelines`
(discovery) or :func:`run_pipeline` (run). The CLI is invoked by the
host-side docker launcher in :mod:`goga.commands.pipeline` through
``docker run ... python -m goga.pipeline {list|run} ...``; the runpy
entrypoint living in :mod:`goga.pipeline.__main__` is a thin wrapper that
delegates to :func:`pipeline_cli` here.

Keeping the implementation out of ``__main__.py`` ensures that importing
the :mod:`goga.pipeline` package does not pull ``__main__`` into
``sys.modules`` and trigger a ``runpy`` ``RuntimeWarning`` for
``python -m goga.pipeline``. See the ``cli_entrypoint`` practice in the
cell's ``CODEMANIFEST``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .compiler import StructuralError
from .list_pipelines import list_pipelines
from .pipeline_entry import PipelineSource
from .run_pipeline import run_pipeline


def pipeline_cli(argv: list[str]) -> int:
    """In-container CLI entrypoint for ``python -m goga.pipeline``.

    Parses ``argv`` via :mod:`argparse` and dispatches to discovery
    (:func:`list_pipelines`) or run (:func:`run_pipeline`).

    Args:
        argv: argument list, typically the process argv minus the program name
            (e.g. ``["list"]`` or ``["run", "deploy", "--port", "50321"]``,
            optionally followed by ``--parallel N`` for the run command).

    Returns:
        ``0`` on success; ``2`` on an argparse error (missing subcommand,
        missing ``NAME``, missing/invalid ``--port``); ``1`` when
        :func:`run_pipeline` raises :class:`StructuralError` (a malformed
        pipeline DSL), :class:`RuntimeError` (e.g. ``AFM_DIR`` unset),
        :class:`yaml.YAMLError` (invalid YAML in the pipeline file), or
        :class:`OSError` (the pipeline file is unreadable or the flow-file's
        parent directory is missing) — these are caught here and reported as a
        clean stderr message rather than propagated as a traceback; otherwise
        the ``exit_code`` propagated from :func:`run_pipeline`.
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
    run_parser.add_argument(
        "--parallel",
        type=int,
        default=None,
        help="cap concurrently executing stages (threads to afm --max-parallel); omitted ⇒ afm runs unbounded.",
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

    try:
        return run_pipeline(args.name, project_dir, user_dir, args.port, parallel=args.parallel)
    except StructuralError as exc:
        print(f"Error: pipeline '{args.name}' is malformed: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except yaml.YAMLError as exc:
        print(f"Error: pipeline '{args.name}' has invalid YAML: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: pipeline '{args.name}' could not be read or written: {exc}", file=sys.stderr)
        return 1
