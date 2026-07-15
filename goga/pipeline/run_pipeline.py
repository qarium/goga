from __future__ import annotations

import os
import sys
from pathlib import Path

from ..afm import run_flow
from .compiler import compile_flow
from .list_pipelines import list_pipelines
from .pipeline_entry import PipelineSource


def run_pipeline(name: str, project_dir: Path, user_dir: Path, port: int) -> int:
    """Resolve, compile, and run a goga pipeline by name via the external ``afm`` binary.

    Resolves the pipeline name to a file via :func:`list_pipelines`, builds the
    pipeline file path from the matching entry's source directory, compiles the
    goga DSL pipeline-file into an afm flow-file via :func:`compile_flow` at the
    path ``<AFM_DIR>/flow.yml``, then launches ``afm`` via
    :func:`goga.afm.run_flow` with the compiled flow-file path (not the DSL
    path) and the caller-allocated ``port``. The ``afm`` binary's exit code is
    propagated; a missing pipeline returns a non-zero code without invoking the
    compiler or the binary.

    Args:
        name: pipeline name without extension (e.g. ``"deploy"``).
        project_dir: project-level pipelines directory (absolute; typically
            ``<cwd>/.goga/pipelines/``).
        user_dir: user-level pipelines directory (absolute; typically
            ``~/.goga/pipelines/``).
        port: TCP port forwarded to ``afm run --port``. Allocated by the caller
            (typically :func:`goga.commands.pipeline.run_pipeline_container`).

    Returns:
        ``0`` on success; ``1`` when the named pipeline is missing; ``127``
        when the ``afm`` binary is missing from ``PATH``; ``126`` when the
        binary cannot be invoked; otherwise the ``afm`` exit code.

    Raises:
        RuntimeError: When the ``AFM_DIR`` environment variable is unset or empty
            (message ``"AFM_DIR not set"``).
        StructuralError: On a structural defect in the pipeline DSL, propagated
            unchanged from :func:`compile_flow`.
    """
    entries = list_pipelines(project_dir, user_dir)
    match = next((entry for entry in entries if entry.name == name), None)

    if match is None:
        print(f"Error: pipeline '{name}' is missing", file=sys.stderr)
        return 1

    source_dir = project_dir if match.source == PipelineSource.PROJECT else user_dir
    pipeline_path = (source_dir / f"{match.name}.yml").resolve()

    afm_env = os.environ.get("AFM_DIR")
    if not afm_env:
        raise RuntimeError("AFM_DIR not set")
    afm_dir = Path(afm_env).resolve()
    flow_path = afm_dir / "flow.yml"

    compile_flow(pipeline_path, flow_path)
    return run_flow(flow_path, port)
