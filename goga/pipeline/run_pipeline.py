from __future__ import annotations

import sys
from pathlib import Path

from ..afm import run_flow
from .list_pipelines import list_pipelines
from .pipeline_entry import PipelineSource


def run_pipeline(name: str, project_dir: Path, user_dir: Path, port: int) -> int:
    """Run a goga pipeline by name via the external ``afm`` binary.

    Resolves the pipeline name to a file via :func:`list_pipelines`, builds the
    pipeline file path from the matching entry's source directory, and launches
    ``afm`` via :func:`goga.afm.run_flow` with the absolute path and the
    caller-allocated ``port``. The ``afm`` binary's exit code is propagated; a
    missing pipeline returns a non-zero code without invoking the binary.

    Args:
        name: pipeline name without extension (e.g. ``"deploy"``).
        project_dir: project-level pipelines directory (typically
            ``<cwd>/.goga/pipelines/``).
        user_dir: user-level pipelines directory (typically
            ``~/.goga/pipelines/``).
        port: TCP port forwarded to ``afm run --port``. Allocated by the caller
            (typically :func:`goga.commands.pipeline.run_pipeline_container`).

    Returns:
        ``0`` on success; ``1`` when the named pipeline is missing; ``127``
        when the ``afm`` binary is missing from ``PATH``; ``126`` when the
        binary cannot be invoked; otherwise the ``afm`` exit code.
    """
    entries = list_pipelines(project_dir, user_dir)
    match = next((entry for entry in entries if entry.name == name), None)

    if match is None:
        print(f"Error: pipeline '{name}' is missing", file=sys.stderr)
        return 1

    source_dir = project_dir if match.source == PipelineSource.PROJECT else user_dir
    pipeline_path = (source_dir / f"{match.name}.yml").resolve()

    return run_flow(pipeline_path, port)
