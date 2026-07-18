from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from ..afm import run_flow
from .compiler import compile_flow
from .list_pipelines import list_pipelines
from .pipeline_entry import PipelineSource
from .workflow import WorkflowDocument, parse_workflow

# The four fixed agent-prompt keys. Each file stem equals its key, so the inline
# ``agents`` header overrides and the package defaults share the same names.
_AGENT_KEYS = ("planning", "implementation", "review", "summary")


def _resolve_defaults_dir() -> Path:
    """Resolve the in-package directory holding the four default agent prompts.

    The prompts ship as package data under ``goga/assets/afm/prompts/`` (one
    ``<key>.md`` file per agent key). Resolved relative to this module so it
    resolves correctly in an installed image regardless of ``CWD``/``AFM_DIR``.
    """
    return Path(__file__).resolve().parent.parent / "assets" / "afm" / "prompts"


def _resolve_workflow(name: str) -> WorkflowDocument | None:
    """Resolve an optional workflow per the workflow environment contract.

    Precedence: ``GOGA_WORKFLOW_DISABLED`` (value ``"1"`` wins — workflow
    disabled) > ``GOGA_WORKFLOW_NAME`` (explicit workflow name) > basename
    fallback (the same name as the pipeline). The workflow-file path is
    project-only and CWD-based — ``Path.cwd() / ".goga" / "workflows" /
    "<name>.yml"`` — NOT derived from ``project_dir.parent``: ``project_dir``
    is ``/workspace/.goga/pipelines``, so ``project_dir.parent`` is
    ``/workspace/.goga`` and a parent-based composition would produce a double
    ``.goga`` segment. ``Path.cwd()`` is ``/workspace`` in-container, i.e. the
    project root. The host-side launcher performs explicit ``--workflow``
    existence validation before launch; inside the container a missing file is
    a defensive silent miss, not an error.

    A structurally malformed workflow-file surfaces its
    :class:`~goga.pipeline.workflow.WorkflowSyntaxError` from
    :func:`parse_workflow` unchanged.

    Args:
        name: The pipeline name — used only for the basename fallback path.

    Returns:
        The parsed :class:`WorkflowDocument` when a workflow-file resolves and
        exists, or ``None`` when workflow is disabled or no file is found.
    """
    if os.environ.get("GOGA_WORKFLOW_DISABLED") == "1":
        return None

    workflows_root = (Path.cwd() / ".goga" / "workflows").resolve()
    workflow_name = os.environ.get("GOGA_WORKFLOW_NAME")
    workflow_path = workflows_root / f"{workflow_name or name}.yml"

    # Containment guard — workflow paths are project-only by design (CODEMANIFEST
    # step 6b). A name carrying a ``..`` segment or an absolute prefix that
    # escapes the workflows dir is a silent miss, never a traversal into the
    # wider filesystem (``GOGA_WORKFLOW_NAME`` may originate from a less-trusted
    # source than the host CLI).
    try:
        workflow_path.resolve().relative_to(workflows_root)
    except ValueError:
        return None

    if not workflow_path.exists():
        return None

    return parse_workflow(workflow_path)


def run_pipeline(name: str, project_dir: Path, user_dir: Path, port: int) -> int:
    """Resolve, compile, and run a goga pipeline by name via the external ``afm`` binary.

    Resolves the pipeline name to a file via :func:`list_pipelines`, builds the
    pipeline file path from the matching entry's source directory, resolves an
    optional workflow per the environment contract
    (``GOGA_WORKFLOW_DISABLED`` > ``GOGA_WORKFLOW_NAME`` > basename fallback),
    compiles the goga DSL pipeline-file into an afm flow-file via
    :func:`compile_flow` at the path ``<AFM_DIR>/flow.yml`` (forwarding the
    parsed workflow when one resolved), materializes the four agent prompt files
    into ``<AFM_DIR>/prompts/`` (step 8), then launches ``afm`` via
    :func:`goga.afm.run_flow` with the compiled flow-file path (not the DSL
    path) and the caller-allocated ``port``. The ``afm`` binary's exit code is
    propagated; a missing pipeline returns a non-zero code without invoking the
    compiler or the binary.

    Step 8 materializes one prompt file per agent key
    (``planning``, ``implementation``, ``review``, ``summary``) into
    ``<AFM_DIR>/prompts/``. For each key, an inline override from the
    pipeline-file ``agents`` header replaces the file wholesale; otherwise the
    package default is copied. The step is validate-first: every key is checked
    (override present or package default exists) BEFORE the prompts directory is
    wiped, so a missing default with no override raises before any file is
    written and the directory is left untouched (atomicity). The wipe + recreate
    makes re-runs idempotent regardless of prior directory state.

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
            (message ``"AFM_DIR not set"``), or when step 8 finds a missing
            package default for an agent key with no inline override (message
            ``"<key>: default prompt missing from package and no inline override
            supplied"``), raised before the prompts directory is wiped.
        WorkflowSyntaxError: On a structural defect in a resolved workflow-file,
            propagated unchanged from :func:`parse_workflow` (step 6) when
            ``GOGA_WORKFLOW_DISABLED`` is not ``"1"`` and the resolved
            workflow-file exists but is malformed.
        StructuralError: On a structural defect in the pipeline DSL, propagated
            unchanged from :func:`compile_flow`.
        FileNotFoundError / PermissionError: Propagated unchanged from
            :func:`compile_flow` when ``pipeline_path`` is unreadable or the
            ``flow_path`` parent directory does not exist.
        yaml.YAMLError: Propagated unchanged from :func:`parse_dsl` when the
            pipeline-file is not valid YAML.
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

    # Step 6: resolve an optional workflow per the workflow environment contract
    # (GOGA_WORKFLOW_DISABLED > GOGA_WORKFLOW_NAME > basename fallback). When a
    # workflow-file resolves and exists, the parsed WorkflowDocument is forwarded
    # to compile_flow; structural workflow errors propagate from parse_workflow.
    workflow = _resolve_workflow(name)

    pipeline_doc, _flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

    # Step 8: materialize the four agent prompt files into <AFM_DIR>/prompts/.
    defaults_dir = _resolve_defaults_dir()
    agents = pipeline_doc.header.agents

    # 8b — validate-all before wipe (atomicity): every key needs an inline
    # override or an existing package default. A missing default with no override
    # raises BEFORE any file is written, so a failed run leaves prompts/ as-is.
    for key in _AGENT_KEYS:
        override = getattr(agents, key) if agents is not None else None
        if override is None and not (defaults_dir / f"{key}.md").exists():
            raise RuntimeError(
                f"{key}: default prompt missing from package and no inline override supplied"
            )

    # 8c — wipe + recreate so re-runs are idempotent regardless of prior state.
    prompts_dir = afm_dir / "prompts"
    if prompts_dir.exists():
        shutil.rmtree(prompts_dir)
    prompts_dir.mkdir(parents=True, exist_ok=False)

    # 8d — write per key: an override replaces the file; otherwise copy default.
    for key in _AGENT_KEYS:
        override = getattr(agents, key) if agents is not None else None
        target = prompts_dir / f"{key}.md"
        if override is not None:
            target.write_text(override)
        else:
            shutil.copy(defaults_dir / f"{key}.md", target)

    # 8e — exactly four prompt files materialized. A real guard, not an
    # ``assert``: the count must hold in optimized runs (``python -O``) too, and
    # a divergence here (concurrent writer, FS oddity) is a RuntimeError rather
    # than a bare AssertionError surfacing at the CLI.
    materialized = sorted(prompts_dir.iterdir())
    expected = sorted(prompts_dir / f"{key}.md" for key in _AGENT_KEYS)
    if materialized != expected:
        raise RuntimeError(f"prompt materialization incomplete: expected {expected}, got {materialized}")

    return run_flow(flow_path, port)
