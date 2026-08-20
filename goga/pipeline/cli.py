"""In-container CLI implementation for ``python -m goga.pipeline``.

Parses argv via :mod:`argparse` and dispatches to one of four operations:
the flat listing (:func:`list_pipelines`), the overview
(:func:`describe_pipelines`), the single-pipeline card
(:func:`describe_pipeline`), or the run (:func:`run_pipeline`). The CLI is
invoked by the host-side docker launcher in
:mod:`goga.commands.pipeline` through
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
from .describe_pipeline import describe_pipeline
from .describe_pipelines import describe_pipelines
from .list_pipelines import list_pipelines
from .pipeline_entry import PipelineSource
from .run_pipeline import run_pipeline
from .workflow import WorkflowSyntaxError


def _build_parser() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    """Build the ``list``/``run`` subcommand parser.

    Returns:
        The top-level parser and the ``run`` subparser (needed for the
        conditional ``--port`` post-check's usage rendering).
    """
    parser = argparse.ArgumentParser(
        prog="goga.pipeline",
        description="Run goga pipelines inside the goga Docker image.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list available pipelines")
    list_parser.add_argument(
        "--info",
        "-i",
        action="store_true",
        default=False,
        help="print the overview: one bullet per pipeline with name and description fields.",
    )

    run_parser = subparsers.add_parser("run", help="run a pipeline by name")
    run_parser.add_argument("name", help="pipeline name without extension")
    run_parser.add_argument(
        "--info",
        "-i",
        action="store_true",
        default=False,
        help="print the pipeline card instead of running it.",
    )
    run_parser.add_argument(
        "--workflow",
        "-w",
        default=None,
        help="apply this workflow to the card composition (--info mode only; "
        "a run picks its workflow up from the GOGA_WORKFLOW_* env vars).",
    )
    run_parser.add_argument(
        "--no-workflow",
        action="store_true",
        default=False,
        help="disable any workflow: report the raw DSL composition (--info mode only).",
    )
    run_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="TCP port forwarded to `afm run --port` (allocated by the host launcher); "
        "required without --info, ignored with it.",
    )
    run_parser.add_argument(
        "--parallel",
        type=int,
        default=None,
        help="cap concurrently executing stages (threads to afm --max-parallel); omitted ⇒ afm runs unbounded.",
    )

    return parser, run_parser


def _run_flat_list(project_dir: Path, user_dir: Path) -> int:
    """Operation (a): the flat listing — one `* {name}[ (project)]` bullet per pipeline."""
    entries = list_pipelines(project_dir, user_dir)
    for entry in entries:
        suffix = " (project)" if entry.source == PipelineSource.PROJECT else ""
        print(f"* {entry.name}{suffix}")
    return 0


def _run_overview(project_dir: Path, user_dir: Path) -> int:
    """Operation (b): the overview — one `* {name}[ (project)]` bullet with name/description fields per pipeline."""
    try:
        summaries = describe_pipelines(project_dir, user_dir)
    except (StructuralError, WorkflowSyntaxError, RuntimeError, yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for summary in summaries:
        suffix = " (project)" if summary.source == PipelineSource.PROJECT else ""
        print(f"* {summary.name}{suffix}")
        print(f"    name: {summary.display_name}")
        print(f"    description: {summary.description}")

    return 0


def _run_card(args: argparse.Namespace, project_dir: Path, user_dir: Path) -> int:
    """Operation (c): the card — name/description fields, a `---` separator, stage bullets."""
    try:
        card = describe_pipeline(args.name, project_dir, user_dir, workflow=args.workflow, no_workflow=args.no_workflow)
    except (StructuralError, WorkflowSyntaxError, RuntimeError, yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"name: {card.name}")
    print(f"description: {card.description}")
    print()
    print("---")
    print()

    for stage in card.stages:
        print(f"* {stage.id}:")
        print(f"    title: {stage.title}")

    return 0


def _run_execution(args: argparse.Namespace, project_dir: Path, user_dir: Path) -> int:  # noqa: PLR0911
    """Operation (d): the run — compile and launch via ``afm``, exit code propagated."""
    try:
        return run_pipeline(args.name, project_dir, user_dir, args.port, parallel=args.parallel)
    except WorkflowSyntaxError as exc:
        print(f"Error: pipeline '{args.name}' has a malformed workflow: {exc}", file=sys.stderr)
        return 1
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
    except UnicodeDecodeError as exc:
        print(f"Error: pipeline '{args.name}' is not valid UTF-8: {exc}", file=sys.stderr)
        return 1


def pipeline_cli(argv: list[str]) -> int:
    """In-container CLI entrypoint for ``python -m goga.pipeline``.

    Parses ``argv`` via :mod:`argparse` and dispatches to one of the four
    operations: the flat listing, the overview, the card, or the run.

    Args:
        argv: argument list, typically the process argv minus the program name
            (e.g. ``["list"]``, ``["list", "--info"]``,
            ``["run", "deploy", "--port", "50321"]``, or
            ``["run", "deploy", "--info", "-w", "hardening"]``).

    Returns:
        ``0`` on success; ``2`` on an argparse error (missing subcommand,
        missing ``NAME``, a non-integer ``--port``, or a missing ``--port``
        on a run without ``--info``); ``1`` when an info operation raises
        :class:`StructuralError`, :class:`WorkflowSyntaxError`,
        :class:`RuntimeError`, :class:`yaml.YAMLError`,
        :class:`OSError`, or :class:`UnicodeDecodeError` — these are
        caught here and reported as a clean stderr message rather than
        propagated as a traceback; ``1`` likewise
        when :func:`run_pipeline` raises one of its handled failures;
        otherwise the ``exit_code`` propagated from :func:`run_pipeline`.
    """
    parser, run_parser = _build_parser()

    args = parser.parse_args(argv)

    # ``--port`` is conditionally required: only a run without ``--info``
    # needs it. Declaring it optional above and enforcing it here keeps the
    # info forms (``run NAME --info``) port-free while a plain run still
    # exits 2 with the standard argparse usage+error rendering.
    if args.command == "run" and not args.info and args.port is None:
        run_parser.error("the following arguments are required: --port")

    project_dir = Path.cwd() / ".goga" / "pipelines"
    user_dir = Path.home() / ".goga" / "pipelines"

    if args.command == "list":
        return _run_overview(project_dir, user_dir) if args.info else _run_flat_list(project_dir, user_dir)

    if args.info:
        return _run_card(args, project_dir, user_dir)

    return _run_execution(args, project_dir, user_dir)
