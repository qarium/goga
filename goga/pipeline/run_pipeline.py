from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from ..afm import run_flow
from .apply_skip_stages import apply_skip_stages
from .compiler import compile_flow, translate_role
from .list_pipelines import list_pipelines
from .pipeline_entry import PipelineSource
from .workflow import WorkflowDocument, parse_workflow

# The three overridable pipeline roles. Each role resolves to its afm prompt-file
# stem via the single source of truth ``translate_role`` (planner→planning,
# executor→implementation, reviewer→review). ``summary`` is NOT a role — it is a
# separate, always-default channel materialized from the literal ``summary.md``.
_ROLES = ("planner", "executor", "reviewer")


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


def resolve_project_name() -> str | None:
    """Derive the project name from the git origin remote URL.

    The in-container project name is reflected into the compiled flow-file
    description as a ``[<project-name>]`` prefix (Part 2). It is derived from
    ``git config --get remote.origin.url`` — the same git remote the project
    bind-mount originates from — and is OUTPUT-only context, mirroring the
    ``root_dir`` pattern (derived in-container from ``Path.cwd()``, never read
    from config, and never raising so it cannot abort a pipeline run).

    The basename of the URL is the project name, with a trailing ``.git``
    suffix stripped. Any failure resolves to ``None`` rather than raising: a
    missing ``git`` binary, not a git repo, no ``origin`` remote configured, a
    non-zero exit, an empty result, or a trailing-slash URL whose basename is
    empty. A ``None`` name simply yields no prefix on the flow description.

    Returns:
        The derived project name, or ``None`` when it cannot be derived.
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    url = result.stdout.strip()
    if not url:
        return None

    # ``os.path.basename`` is intentional over ``Path(url).name``: the former
    # returns ``""`` for a trailing-slash URL (e.g. ``".../acme/"``) while the
    # latter returns ``"acme"`` — the trailing-slash case must resolve to
    # ``None`` (no prefix), so the basename-empty guard below fires. noqa: PTH119
    name = os.path.basename(url)  # noqa: PTH119
    if name.endswith(".git"):
        name = name[:-4]

    return name or None


def run_pipeline(
    name: str, project_dir: Path, user_dir: Path, port: int, parallel: int | None = None
) -> int:
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
    path), the caller-allocated ``port``, and an optional concurrency cap. The
    ``afm`` binary's exit code is propagated; a missing pipeline returns a
    non-zero code without invoking the compiler or the binary.

    ``parallel`` is forwarded as ``run_flow(..., max_parallel=parallel)`` so a
    non-``None`` cap materializes as ``afm run --max-parallel <N>`` (the
    host-side ``-p/--parallel`` option threads through to it). It is
    compilation-orthogonal: steps 1-8 do not consume it, and ``None`` (the
    default) reaches ``run_flow`` as ``max_parallel=None`` so the flag is
    omitted (backward compatible).

    Step 8 materializes the four afm prompt files
    (``planning``, ``implementation``, ``review``, ``summary``) into
    ``<AFM_DIR>/prompts/``. The first three correspond to the overridable roles
    (``planner``/``executor``/``reviewer``), each resolved to its afm stem via
    :func:`translate_role`; for each role, an inline override from the
    pipeline-file ``roles`` header replaces the file wholesale at its stem,
    otherwise the package default is copied. ``summary`` is a separate,
    always-default channel — it is never overridden and is always copied from the
    package default. The step is validate-first: every role is checked (override
    present or package default exists at its stem) AND the summary default is
    checked BEFORE the prompts directory is wiped, so a missing default with no
    override raises before any file is written and the directory is left
    untouched (atomicity). The wipe + recreate makes re-runs idempotent
    regardless of prior directory state.

    Args:
        name: pipeline name without extension (e.g. ``"deploy"``).
        project_dir: project-level pipelines directory (absolute; typically
            ``<cwd>/.goga/pipelines/``).
        user_dir: user-level pipelines directory (absolute; typically
            ``~/.goga/pipelines/``).
        port: TCP port forwarded to ``afm run --port``. Allocated by the caller
            (typically :func:`goga.commands.pipeline.run_pipeline_container`).
        parallel: optional cap on concurrently executing stages, forwarded to
            :func:`goga.afm.run_flow` as ``max_parallel=parallel`` (so afm
            receives ``--max-parallel <parallel>``). ``None`` (the default) is
            forwarded unchanged and the flag is omitted — compilation never
            depends on it.

    Returns:
        ``0`` on success; ``1`` when the named pipeline is missing; ``127``
        when the ``afm`` binary is missing from ``PATH``; ``126`` when the
        binary cannot be invoked; otherwise the ``afm`` exit code.

    Raises:
        RuntimeError: When the ``AFM_DIR`` environment variable is unset or empty
            (message ``"AFM_DIR not set"``), or when step 8 finds a missing
            package default for an overridable role's stem with no inline override
            (message ``"<stem>: default prompt missing from package and no inline
            override supplied"``), or when the ``summary`` package default is
            missing (message ``"summary: default prompt missing from package"``),
            raised before the prompts directory is wiped.
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

    # Step 6e: merge CLI skip directives (the comma-split ``GOGA_SKIP_STAGES``
    # container env var) onto the resolved workflow without mutating it. An empty
    # or unset var is a no-op (``apply_skip_stages`` returns the input unchanged);
    # otherwise the merged document carries ``WorkflowStage(skip=True)`` entries
    # that ``compile_flow`` (step 4skip) turns into stage removal + ``depends_on``
    # reconnection. Name validation is deferred to ``compile_flow`` step 4pre, so
    # an unknown name surfaces as a ``StructuralError`` there, not here.
    raw = os.environ.get("GOGA_SKIP_STAGES", "")
    skip_stages = [s for s in raw.split(",") if s]
    workflow = apply_skip_stages(workflow, skip_stages)

    # The in-container project root is the single source of truth for the afm
    # ``root_dir`` directive emitted into the compiled flow-file. ``Path.cwd()``
    # resolves to ``/workspace`` inside the goga container (the host-side
    # launcher sets ``workdir=/workspace`` and bind-mounts the project there),
    # so this mirrors the mount decision rather than re-declaring the literal.
    # Forwarded as an explicit parameter so the compiler stays a pure
    # transformer with no environment-variable reads.
    root_dir = str(Path.cwd().resolve())

    # Step 7: derive the in-container project name from the git origin remote URL
    # for the ``[<project-name>]`` description prefix (Part 2). OUTPUT-only context,
    # mirroring ``root_dir`` — derived here from the environment, never read from
    # config, and ``resolve_project_name`` never raises so it cannot abort the run.
    project_name = resolve_project_name()

    pipeline_doc, _flow_doc = compile_flow(
        pipeline_path, flow_path, workflow=workflow, root_dir=root_dir, project_name=project_name
    )

    # Step 8: materialize the four agent prompt files into <AFM_DIR>/prompts/.
    defaults_dir = _resolve_defaults_dir()
    roles = pipeline_doc.header.roles

    # 8b — validate-all before wipe (atomicity): each overridable role needs an
    # inline override (from ``header.roles``) or an existing package default at
    # its ``translate_role`` stem; ``summary`` always needs its package default
    # (it is a separate, non-overridable channel). A missing default with no
    # override raises BEFORE any file is written, so a failed run leaves prompts/
    # as-is.
    for role in _ROLES:
        stem = translate_role(role)
        override = getattr(roles, role) if roles is not None else None
        if override is None and not (defaults_dir / f"{stem}.md").exists():
            raise RuntimeError(f"{stem}: default prompt missing from package and no inline override supplied")
    if not (defaults_dir / "summary.md").exists():
        raise RuntimeError("summary: default prompt missing from package")

    # 8c — wipe + recreate so re-runs are idempotent regardless of prior state.
    prompts_dir = afm_dir / "prompts"
    if prompts_dir.exists():
        shutil.rmtree(prompts_dir)
    prompts_dir.mkdir(parents=True, exist_ok=False)

    # 8d — write per role: an override replaces the file at its stem; otherwise
    # copy the package default. ``summary`` is always copied from the default —
    # it has no inline override channel.
    for role in _ROLES:
        stem = translate_role(role)
        override = getattr(roles, role) if roles is not None else None
        target = prompts_dir / f"{stem}.md"
        if override is not None:
            target.write_text(override)
        else:
            shutil.copy(defaults_dir / f"{stem}.md", target)
    shutil.copy(defaults_dir / "summary.md", prompts_dir / "summary.md")

    # 8e — exactly four prompt files materialized (planning/implementation/review
    # from ``_ROLES`` via ``translate_role`` plus the literal summary). A real
    # guard, not an ``assert``: the count must hold in optimized runs
    # (``python -O``) too, and a divergence here (concurrent writer, FS oddity)
    # is a RuntimeError rather than a bare AssertionError surfacing at the CLI.
    expected_stems = [translate_role(role) for role in _ROLES] + ["summary"]
    materialized = sorted(prompts_dir.iterdir())
    expected = sorted(prompts_dir / f"{stem}.md" for stem in expected_stems)
    if materialized != expected:
        raise RuntimeError(f"prompt materialization incomplete: expected {expected}, got {materialized}")

    return run_flow(flow_path, port, max_parallel=parallel)
