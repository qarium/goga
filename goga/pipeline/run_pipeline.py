from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from ..afm import run_flow
from ..config import load_project_config, resolve_project_name
from ..config.hooks import ConfigHooks
from ..docker import decode_extra_env
from ..history import (
    assemble_status_scale,
    resolve_current_branch_name,
    resolve_topic_dir,
    resolve_topic_status,
)
from .afm_config import write_afm_config
from .apply_skip_stages import apply_skip_stages
from .compiler import PipelineRoles, compile_flow, parse_dsl, translate_role
from .hooks import (
    CompositionStage,
    PipelineHooks,
    PipelineIdentity,
    WorkflowDecision,
    WorkflowOverlay,
    WorkIdentity,
)
from .list_pipelines import list_pipelines
from .order_stages import order_stages
from .pipeline_entry import PipelineEntry, PipelineSource
from .resolve_workflow import resolve_workflow

if TYPE_CHECKING:  # the workflow document is a fact the amendment facts carry
    from .workflow import WorkflowDocument

logger = logging.getLogger(__name__)

# The three overridable pipeline roles. Each role resolves to its afm prompt-file
# stem via the single source of truth ``translate_role`` (planner→planning,
# executor→implementation, reviewer→review). ``summary`` is NOT a role — it is a
# separate, always-default channel materialized from the literal ``summary.md``.
_ROLES = ("planner", "executor", "reviewer")

# The engine-variable keys that never enter a composed launch layer: launch
# mechanics belong to the launcher, so a task-env or CLI entry colliding with
# one of them is dropped silently — the inherited launch value stands, with no
# warning.
_ENGINE_ENV_KEYS = frozenset({"AFM_DIR", "AFM_DOCKER_FILE_ROOTS", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"})


def _resolve_defaults_dir() -> Path:
    """Resolve the in-package directory holding the four default agent prompts.

    The prompts ship as package data under ``goga/assets/afm/prompts/`` (one
    ``<key>.md`` file per agent key). Resolved relative to this module so it
    resolves correctly in an installed image regardless of ``CWD``/``AFM_DIR``.
    """
    return Path(__file__).resolve().parent.parent / "assets" / "afm" / "prompts"


def _resolve_amendment_facts(
    match: PipelineEntry,
    pipeline_path: Path,
    no_workflow: bool,
    workflow_name: str | None,
    workflow: WorkflowDocument | None,
) -> tuple[PipelineIdentity, WorkflowDecision, WorkIdentity, Path | None]:
    """Resolve the amendment facts of step 10 from the operation's own data.

    The checkpoints read no repository — every fact resolves here: the
    :class:`~goga.pipeline.hooks.PipelineIdentity` from one early
    ``parse_dsl`` header read, the
    :class:`~goga.pipeline.hooks.WorkflowDecision` from the kind-derivation
    matrix (disabled wins; a resolved document under an explicit name is
    ``explicit``, under no name ``auto-match``; no document is a silent
    miss), and the :class:`~goga.pipeline.hooks.WorkIdentity` from the
    current branch and its hosting topic directory.

    Args:
        match: The discovered pipeline entry — the name and the source.
        pipeline_path: The absolute pipeline-file path (parsed once here).
        no_workflow: The disabled flag of the run's workflow decision.
        workflow_name: The explicit workflow name of the run's decision, or
            ``None``.
        workflow: The workflow the resolution returned — before the
            runner-skip merge. The decision mirrors the resolution, not the
            skip merge: a skip-only document synthesized over a missing
            workflow is not a resolution.

    Returns:
        The identity, the decision, the work identity, and the hosting
        topic directory (``None`` in the branch-only form).
    """
    header, _, _ = parse_dsl(pipeline_path.read_text())
    identity = PipelineIdentity(
        name=match.name,
        display_name=header.name,
        description=header.description,
        source=match.source.value,
    )

    if no_workflow:
        decision = WorkflowDecision(kind="disabled", workflow_name=None)
    elif workflow is None:
        decision = WorkflowDecision(kind="silent-miss", workflow_name=None)
    elif workflow_name not in (None, ""):
        decision = WorkflowDecision(kind="explicit", workflow_name=workflow_name)
    else:
        decision = WorkflowDecision(kind="auto-match", workflow_name=match.name)

    # The branch (the literal "unknown" when git resolves none) with the
    # hosting topic's slug and year when the branch hosts a topic. A fully
    # unsluggable branch raises ``ValueError`` out of the topic composer —
    # guarded to the branch-only form.
    branch = resolve_current_branch_name() or "unknown"
    try:
        topic_dir = resolve_topic_dir(branch)
    except ValueError:
        topic_dir = None  # a fully unsluggable branch hosts no topic

    if topic_dir is not None and topic_dir.is_dir():
        work = WorkIdentity(branch=branch, slug=topic_dir.name, year=topic_dir.parent.name)
    else:
        work = WorkIdentity(branch=branch)
        topic_dir = None

    return identity, decision, work, topic_dir


def _materialize_prompts(afm_dir: Path, roles: PipelineRoles | None) -> None:
    """Materialize the four agent prompt files of step 13 into ``<AFM_DIR>/prompts/``.

    Validate-first: every overridable role (``planner``/``executor``/
    ``reviewer``) is checked — an inline override from the documents tuple
    header or an existing package default at its ``translate_role`` stem —
    and the ``summary`` package default is checked BEFORE the prompts
    directory is wiped, so a missing default with no override raises before
    any file is written and the directory is left untouched (atomicity).
    The wipe + recreate then makes re-runs idempotent regardless of prior
    directory state; ``summary`` is a separate, always-default channel —
    never overridden, always copied from the default.

    Args:
        afm_dir: The resolved runtime directory — the prompts land at
            ``<AFM_DIR>/prompts/``.
        roles: The inline role overrides from the documents tuple header, or
            ``None`` when the header carries no ``roles`` block.

    Raises:
        RuntimeError: When a role's package default is missing with no inline
            override (message ``"<stem>: default prompt missing from package
            and no inline override supplied"``), or when the ``summary``
            package default is missing (message ``"summary: default prompt
            missing from package"``) — both raised before the wipe.
    """
    defaults_dir = _resolve_defaults_dir()

    # 13b — validate-all before wipe (atomicity).
    for role in _ROLES:
        stem = translate_role(role)
        override = getattr(roles, role) if roles is not None else None
        if override is None and not (defaults_dir / f"{stem}.md").exists():
            raise RuntimeError(f"{stem}: default prompt missing from package and no inline override supplied")

    if not (defaults_dir / "summary.md").exists():
        raise RuntimeError("summary: default prompt missing from package")

    # 13c — wipe + recreate so re-runs are idempotent regardless of prior state.
    prompts_dir = afm_dir / "prompts"
    if prompts_dir.exists():
        shutil.rmtree(prompts_dir)
    prompts_dir.mkdir(parents=True, exist_ok=False)

    # 13d — write per role: an override replaces the file at its stem; otherwise
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

    # 13e — exactly four prompt files materialized (planning/implementation/review
    # from ``_ROLES`` via ``translate_role`` plus the literal summary). A real
    # guard, not an ``assert``: the count must hold in optimized runs
    # (``python -O``) too, and a divergence here (concurrent writer, FS oddity)
    # is a RuntimeError rather than a bare AssertionError surfacing at the CLI.
    expected_stems = [translate_role(role) for role in _ROLES] + ["summary"]
    materialized = sorted(prompts_dir.iterdir())
    expected = sorted(prompts_dir / f"{stem}.md" for stem in expected_stems)
    if materialized != expected:
        raise RuntimeError(f"prompt materialization incomplete: expected {expected}, got {materialized}")


def run_pipeline(  # noqa: PLR0913, PLR0915, PLR0917 — the 8-parameter signature and the 21-step contract algorithm
    name: str,
    project_dir: Path,
    user_dir: Path,
    port: int,
    workflow: str | None = None,
    no_workflow: bool = False,
    skip: list[str] | None = None,
    parallel: int | None = None,
) -> int:
    """Resolve, compile, and run a goga pipeline by name via the external ``afm`` binary.

    Opens with the in-container configuration load-and-amend: loads the
    authored project configuration via
    :func:`~goga.config.project.loader.load_project_config`, delivers the
    config amendment through
    :class:`~goga.config.hooks.events.ConfigHooks` (printing the overlay's
    summary lines to stderr; nothing when empty), and consumes the effective
    configuration of the overlay for the run parameters this domain owns.
    Then resolves the pipeline name to a file via :func:`list_pipelines`,
    builds the pipeline file path from the matching entry's source directory,
    resolves an optional workflow via
    :func:`~goga.pipeline.resolve_workflow.resolve_workflow` from the explicit
    parameters (``no_workflow`` > ``workflow`` > basename fallback), merges
    the ``skip`` stage names, resolves the amendment facts (the pipeline
    identity from one early ``parse_dsl`` header read, the workflow decision,
    and the work identity from the current branch and its hosting topic),
    delivers the workflow amendment through the pipeline hooks zone (unless
    the decision is disabled), compiles the goga DSL pipeline-file into an
    afm flow-file via :func:`compile_flow` at the path ``<AFM_DIR>/flow.yml``
    (forwarding the overlay workflow the amendment layer returned),
    materializes the four agent prompt files into ``<AFM_DIR>/prompts/``,
    writes the afm configuration file via :func:`write_afm_config` with the
    effective pipeline agent, composes the afm launch environment layer (the
    decoded CLI entries applied above the effective ``pipeline.env`` task env
    layer, the engine-variable keys dropped), emits the run-creation facts,
    then launches ``afm`` via :func:`goga.afm.run_flow` with the compiled
    flow-file path (not the DSL path), the caller-allocated ``port``, an
    optional concurrency cap, and the composed layer as the ``env``
    parameter. On every return of ``run_flow`` the work statuses are
    recomputed at the completion moment, the run-completion facts are emitted
    with the actual exit code, and the exit code is returned.

    The workflow decision and the skip names arrive as explicit parameters —
    never from the environment. The environment reads are exactly two:
    ``AFM_DIR`` (the runtime directory) and ``GOGA_EXTRA_ENV`` (the encoded
    CLI entries payload of the docker carriage); stale user-supplied
    workflow/skip values in the environment are never read and stay inert.

    ``parallel`` is forwarded as ``run_flow(..., max_parallel=parallel)`` so a
    non-``None`` cap materializes as ``afm run --max-parallel <N>`` (the
    host-side ``-p/--parallel`` option threads through to it). It is
    compilation-orthogonal: no step before the launch consumes it, and ``None``
    (the default) reaches ``run_flow`` as ``max_parallel=None`` so the flag is
    omitted (backward compatible).

    Step 13 (via :func:`_materialize_prompts`) materializes the four afm
    prompt files (``planning``, ``implementation``, ``review``, ``summary``)
    into ``<AFM_DIR>/prompts/`` — validate-first (atomicity), wipe +
    recreate (idempotent), overrides replacing the file wholesale at their
    stem, ``summary`` always from the package default.

    Args:
        name: pipeline name without extension (e.g. ``"deploy"``).
        project_dir: project-level pipelines directory (absolute; typically
            ``<cwd>/.goga/pipelines/``).
        user_dir: user-level pipelines directory (absolute; typically
            ``~/.goga/pipelines/``).
        port: TCP port forwarded to ``afm run --port``. Allocated by the caller
            (typically :func:`goga.commands.pipeline.run_pipeline_container`).
        workflow: optional explicit workflow name — the CLI ``-w/--workflow``
            value the run coordination forwards. Resolved via the shared rule
            set: ``no_workflow`` wins, then this name, then the basename
            auto-match (the pipeline name). ``None`` (the default) means no
            explicit name.
        no_workflow: ``True`` disables workflow application entirely (the CLI
            ``--no-workflow`` flag) — wins over any name. ``False`` (the
            default) applies the workflow rule set.
        skip: stage names to exclude from the composition — the repeatable
            ``-s/--skip`` flag values passed by run coordination. ``None`` and
            ``[]`` both mean no skip; otherwise the names merge onto the
            resolved workflow in memory via :func:`apply_skip_stages` (name
            validation is the compiler's structural error, not performed
            here).
        parallel: optional cap on concurrently executing stages, forwarded to
            :func:`goga.afm.run_flow` as ``max_parallel=parallel`` (so afm
            receives ``--max-parallel <parallel>``). ``None`` (the default) is
            forwarded unchanged and the flag is omitted — compilation never
            depends on it.

    Returns:
        ``0`` on success; ``1`` when the project configuration fails to load
        or the config amendment delivery fails (both before any discovery,
        compile, write, or launch — no events fire), when the named pipeline
        is missing, or when the CLI entries payload is damaged (one clean
        error before the run-creation facts — no events fire, afm never
        launches); ``127`` when the ``afm`` binary is missing from ``PATH``;
        ``126`` when the binary cannot be invoked; otherwise the ``afm`` exit
        code.

    Raises:
        RuntimeError: When the ``AFM_DIR`` environment variable is unset or empty
            (message ``"AFM_DIR not set"``), or when step 13 finds a missing
            package default for an overridable role's stem with no inline override
            (message ``"<stem>: default prompt missing from package and no inline
            override supplied"``), or when the ``summary`` package default is
            missing (message ``"summary: default prompt missing from package"``),
            raised before the prompts directory is wiped.
        OSError: Propagated unchanged from :func:`write_afm_config` when the
            in-container home directory is unwritable (step 14, before the
            run-creation facts — no events have fired).
        WorkflowSyntaxError: On a structural defect in a resolved workflow-file,
            propagated unchanged from :func:`parse_workflow` (step 8) when
            ``no_workflow`` is ``False`` and the resolved workflow-file exists
            but is malformed.
        StructuralError: On a structural defect in the pipeline DSL, propagated
            unchanged from :func:`parse_dsl` (step 10, the fact-resolution
            header read) or :func:`compile_flow`.
        ValueError: When a hook of the hard ``pipeline.amend_workflow`` action
            failed during the amendment delivery (step 11, before any compile,
            write, or launch) — the message names the hook, the tool, and the
            action; the tool's whole contribution is discarded.
        ImportError: When a tool package exists but its facade fails to import
            — the fatal registry-build error of the hooks platform.
        FileNotFoundError / PermissionError: Propagated unchanged from
            :func:`compile_flow` when ``pipeline_path`` is unreadable or the
            ``flow_path`` parent directory does not exist.
        yaml.YAMLError: Propagated unchanged from :func:`parse_dsl` when the
            pipeline-file is not valid YAML.
    """
    # Steps 1-2 — the in-container configuration load-and-amend. The authored
    # load and the config-amendment delivery each own a clean-error boundary:
    # both return 1 before any discovery, compile, write, or launch, so no
    # events fire and nothing is partially applied. Every downstream step
    # consumes the effective configuration of the overlay — the run parameters
    # this domain owns (pipeline.agent, pipeline.env) are read from it alone;
    # the docker-level fields (image, proxy, hosts) stay applied-but-unconsumed,
    # silently.
    try:
        authored = load_project_config()
    except (FileNotFoundError, OSError, KeyError, ValueError, yaml.YAMLError) as exc:
        logger.error("project configuration load failed", extra={"reason": str(exc)})
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        overlay = ConfigHooks().amend_config(config=authored)
    except (ValueError, ImportError) as exc:
        logger.error("config amendment delivery failed", extra={"reason": str(exc)})
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for line in overlay.summary_lines:
        print(line, file=sys.stderr)

    config = overlay.config

    # Steps 3-5 — discover the entry and build the absolute pipeline path.
    entries = list_pipelines(project_dir, user_dir)
    match = next((entry for entry in entries if entry.name == name), None)

    if match is None:
        # Step 4 — the missing-pipeline report; the return happens before any
        # checkpoint, so no events fire.
        logger.error("pipeline missing", extra={"pipeline": name})
        print(f"Error: pipeline '{name}' is missing", file=sys.stderr)
        return 1

    source_dir = project_dir if match.source == PipelineSource.PROJECT else user_dir
    pipeline_path = (source_dir / f"{match.name}.yml").resolve()

    # Steps 6-7 — the runtime directory and the output flow path inside it.
    afm_env = os.environ.get("AFM_DIR")
    if not afm_env:
        raise RuntimeError("AFM_DIR not set")
    afm_dir = Path(afm_env).resolve()
    flow_path = afm_dir / "flow.yml"
    runtime_dir = afm_dir.as_posix()

    # Step 8: resolve an optional workflow via ``resolve_workflow`` from the
    # explicit parameters (no_workflow > workflow > basename fallback). The CLI
    # decision arrives as arguments — never from the environment — and the
    # shared rule set applies it: the same entry point the info-card path
    # (describe_pipeline) uses, so what the card shows is what the run executes.
    # The disabled priority is enforced twice: in the input (the name is nulled
    # when disabled) and as step 1 of the rule set. Structural workflow errors
    # propagate from parse_workflow unchanged — before the delivery, so no
    # events fire.
    workflow_name = None if no_workflow else workflow
    resolved = resolve_workflow(name, workflow_name, no_workflow)

    # Step 9: merge the skip names (the repeatable ``-s/--skip`` flag values
    # passed by run coordination) onto the resolved workflow without mutating
    # it. ``None``/empty is a no-op (``apply_skip_stages`` returns the input
    # unchanged); otherwise the merged document carries ``WorkflowStage(
    # skip=True)`` entries that ``compile_flow`` (step 4skip) turns into stage
    # removal + ``depends_on`` reconnection. Name validation is deferred to
    # ``compile_flow`` step 4pre, so an unknown name surfaces as a
    # ``StructuralError`` there, not here.
    workflow_doc = apply_skip_stages(resolved, skip or [])

    # Step 10: the amendment facts (identity, decision, work) and the hosting
    # topic directory — resolved in the operation, read by no checkpoint.
    # The decision derives from the pre-merge resolution outcome: a skip-only
    # document synthesized over a missing workflow is not a resolution, so
    # the miss still reports as a miss.
    identity, decision, work, topic_dir = _resolve_amendment_facts(
        match, pipeline_path, no_workflow, workflow_name, resolved
    )

    # Step 11: deliver the amendment with the authored workflow after the skip
    # merge — receiving the overlay result. A disabled decision delivers
    # nothing (the layer is off) and the overlay is the passthrough of the
    # merged workflow. The delivery is hard: the first failing tool stops the
    # run here with a clean ``ValueError``, before any compile, write, or
    # launch — and no events fire.
    hooks = PipelineHooks()

    if decision.kind != "disabled":
        overlay = hooks.amend_workflow(pipeline=identity, decision=decision, workflow=workflow_doc, work=work)
    else:
        overlay = WorkflowOverlay(workflow=workflow_doc, provenance=[])

    # The in-container project root is the single source of truth for the afm
    # ``root_dir`` directive emitted into the compiled flow-file. ``Path.cwd()``
    # resolves to ``/workspace`` inside the goga container (the host-side
    # launcher sets ``workdir=/workspace`` and bind-mounts the project there),
    # so this mirrors the mount decision rather than re-declaring the literal.
    # Forwarded as an explicit parameter so the compiler stays a pure
    # transformer with no environment-variable reads.
    root_dir = str(Path.cwd().resolve())

    # Step 12: derive the in-container project name from the git origin remote URL
    # for the ``[<project-name>]`` description prefix (Part 2). OUTPUT-only context,
    # mirroring ``root_dir`` — derived here from the environment, never read from
    # config, and ``resolve_project_name`` never raises so it cannot abort the run.
    # Compilation runs with the overlay workflow — with no tool packages the
    # overlay is the passthrough, so the compiled workflow is exactly what was
    # resolved. Structural errors propagate unchanged (no events).
    project_name = resolve_project_name()

    pipeline_doc, flow_doc = compile_flow(
        pipeline_path, flow_path, workflow=overlay.workflow, root_dir=root_dir, project_name=project_name
    )

    # Step 13: materialize the four agent prompt files into <AFM_DIR>/prompts/.
    _materialize_prompts(afm_dir, pipeline_doc.header.roles)

    # Step 14: write the afm configuration file with the effective pipeline
    # agent — the whole file at the fixed in-container home path, before the
    # launch. The section is guaranteed present (the host structural guard and
    # the set/force-only amendments materialize it), so no in-container section
    # guard exists. An ``OSError`` (an unwritable home) propagates — declared
    # error semantics; this precedes the run-creation facts, so no events have
    # fired.
    write_afm_config(config.pipeline.agent)

    # Step 15: the composition — one row per ordered compiled stage, as the card
    # shows them, built from the same compilation the run executes.
    composition = [CompositionStage(id=stage.id, title=stage.name) for stage in order_stages(flow_doc.stages)]

    # Step 16: the work statuses of the hosting topic — the scale assembles once
    # per run and both status reads share it. The branch-only form stays empty
    # and never assembles the scale.
    scale = None
    statuses: list[str] = []
    if topic_dir is not None:
        scale = assemble_status_scale()
        statuses = resolve_topic_status(topic_dir, scale)

    logger.debug(
        "pipeline run composed",
        extra={
            "pipeline": name,
            "stages": [stage.id for stage in composition],
            "workflow_applied": overlay.workflow is not None,
            "provenance": overlay.provenance,
            "statuses": statuses,
        },
    )

    # Step 17: compose the afm launch environment layer — the decoded CLI
    # entries applied ABOVE the effective task env layer (explicit CLI input
    # beats configuration and tool amendments on key conflict), with the
    # engine-variable keys dropped silently so launch mechanics can never be
    # overridden. The layer travels only through ``run_flow``'s env parameter;
    # the container's process environment is never mutated. A damaged payload
    # is one clean error BEFORE the run-creation facts — no events fire, afm
    # never launches, nothing is partially applied.
    try:
        payload = decode_extra_env(os.environ.get("GOGA_EXTRA_ENV", ""))
    except ValueError as exc:
        logger.error("cli environment payload damaged", extra={"reason": str(exc)})
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    launch_layer = {
        key: value
        for key, value in {**config.pipeline.env, **payload}.items()
        if key not in _ENGINE_ENV_KEYS
    }

    # Step 18: the run-creation facts immediately before the launch — now after
    # the afm configuration write (step 14) and the layer composition (step
    # 17) — soft, so a failing hook warns and the launch proceeds.
    hooks.emit_run_created(
        pipeline=identity,
        decision=decision,
        overlay=overlay,
        composition=composition,
        work=work,
        statuses=statuses,
        runtime_dir=runtime_dir,
    )

    # Step 19: launch. The composed layer applies to the afm subprocess only —
    # an empty layer passes as-is (run_flow treats it as pure inheritance).
    # Spawn failures are return codes (126/127), not raises.
    exit_code = run_flow(flow_path, port, max_parallel=parallel, env=launch_layer)

    # Steps 20-21: on every return of run_flow — zero, non-zero, and spawn
    # failures alike — recompute the statuses at the completion moment (one
    # scale, two reads) and emit the completion facts with the actual exit
    # code; a failing hook warns and never affects the code.
    if topic_dir is not None:
        statuses = resolve_topic_status(topic_dir, scale)

    hooks.emit_run_completed(
        pipeline=identity,
        decision=decision,
        overlay=overlay,
        composition=composition,
        work=work,
        statuses=statuses,
        runtime_dir=runtime_dir,
        exit_code=exit_code,
    )
    return exit_code
