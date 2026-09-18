"""The ``describe_pipeline`` Routine — the single pipeline card via the compile machine.

Composes the informational card of ONE pipeline: the author-facing
name/description from the DSL header plus the post-workflow stage composition
in execution order. The card deliberately shares the run path's machinery —
the same :func:`~goga.pipeline.resolve_workflow.resolve_workflow` rule set,
the same amendment layer of the pipeline hooks zone, and the same
:func:`~goga.pipeline.compiler.compile_flow` compiler — so the composition
the card reports is structurally the composition the run executes: the
workflow the amendment layer returns is the workflow compiled here, and the
tools the card's ``provenance`` lists are exactly the tools a run with the
same workflow flags would compose through. Workflow ``skip`` directives
therefore apply (they are compiler directives), loop copies appear as
separate ``NAME-1..N`` rows, while the run-only ``GOGA_SKIP_STAGES``
environment variable is NOT read — the card answers "what is this
pipeline?", not "what would this particular run skip?". No run events fire
in card form: the amendment is delivered (unless the workflow decision is
disabled) but neither notification is emitted.

The compiled flow-file is written to a throwaway temp directory (never the
project tree or a runtime directory) and removed once the card is composed.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from ..history import resolve_current_branch_name, resolve_topic_dir
from .compiler import compile_flow, parse_dsl
from .hooks import PipelineHooks, PipelineIdentity, WorkflowDecision, WorkflowOverlay, WorkIdentity
from .list_pipelines import list_pipelines
from .order_stages import order_stages
from .pipeline_card import CardStage, PipelineCard
from .pipeline_entry import PipelineSource
from .resolve_workflow import resolve_workflow

logger = logging.getLogger(__name__)


def describe_pipeline(
    name: str,
    project_dir: Path,
    user_dir: Path,
    workflow: str | None,
    no_workflow: bool,
) -> PipelineCard:
    """Compose the card of a single pipeline: header values plus ordered stage rows.

    The pipeline is located by name through :func:`list_pipelines` (project
    source wins on conflicts); an unknown name raises ``RuntimeError``. The
    optional workflow is resolved through the shared rule set
    (:func:`resolve_workflow` — ``no_workflow`` > explicit ``workflow`` >
    basename auto-match, silent miss). The amendment facts are then resolved —
    the :class:`~goga.pipeline.hooks.PipelineIdentity` from one early
    ``parse_dsl`` header read, the
    :class:`~goga.pipeline.hooks.WorkflowDecision` from the flags and the
    resolution outcome, and the :class:`~goga.pipeline.hooks.WorkIdentity`
    from the current git branch and its hosting topic directory — and the
    amendment is delivered through :class:`~goga.pipeline.hooks.PipelineHooks`
    unless the decision is disabled (a disabled decision delivers nothing and
    composes over the passthrough overlay). The pipeline is compiled through
    the real :func:`compile_flow` machine into a temp flow-file (no
    ``root_dir`` / ``project_name`` — they only affect discarded top-level
    keys, never the stages) with the overlay workflow, and the compiled
    stages are ordered by :func:`~goga.pipeline.order_stages.order_stages`
    into execution order. ``name``/``description`` are the author-facing
    header values (they may differ from the discovered file stem) and come
    from the documents tuple — never a re-parse of the pipeline-file.

    Nothing is executed: no afm invocation, no stage run, no prompt
    materialization, no run events. The temp flow-file is the only write and
    is removed on routine exit.

    Args:
        name: pipeline name without extension (e.g. ``"deploy"``) — the
            discovered stem.
        project_dir: project-level pipelines directory (typically
            ``<cwd>/.goga/pipelines/``).
        user_dir: user-level pipelines directory (typically
            ``~/.goga/pipelines/``).
        workflow: explicit workflow name, or ``None`` for the basename
            auto-match.
        no_workflow: ``True`` disables the workflow entirely (wins over any
            name).

    Returns:
        The composed :class:`~goga.pipeline.pipeline_card.PipelineCard` — its
        ``provenance`` carries the tools whose contributions committed into
        the composition, in enumeration order.

    Raises:
        RuntimeError: If no discovered pipeline carries ``name`` (message
            ``"pipeline '<name>' is missing"``).
        WorkflowSyntaxError: On a structural defect in a resolved
            workflow-file, propagated unchanged from ``parse_workflow`` via
            ``resolve_workflow``.
        StructuralError: On a structural defect in the pipeline DSL,
            propagated unchanged from ``parse_dsl`` / ``compile_flow``.
        yaml.YAMLError: If the pipeline-file is not valid YAML, propagated
            unchanged from ``parse_dsl`` / ``compile_flow``.
        OSError: If the pipeline-file cannot be read or the temp flow-file
            cannot be written, propagated unchanged.
        ValueError: If a hook of the hard ``pipeline.amend_workflow`` action
            failed during the delivery — the message names the hook, the
            tool, and the action; propagated unchanged from the checkpoint
            surface.
        ImportError: If a tool package exists but its facade fails to import
            — the fatal registry-build error, propagated unchanged.
    """
    # Step 1 — locate the pipeline by name (project source wins on conflicts).
    entries = list_pipelines(project_dir, user_dir)
    match = next((entry for entry in entries if entry.name == name), None)

    if match is None:
        raise RuntimeError(f"pipeline '{name}' is missing")

    source_dir = project_dir if match.source == PipelineSource.PROJECT else user_dir
    pipeline_path = (source_dir / f"{match.name}.yml").resolve()

    # Step 2 — resolve the optional workflow through the shared rule set (the
    # same resolver the run path uses, so card composition == run composition).
    workflow_doc = resolve_workflow(name, workflow, no_workflow)

    # Step 3 — resolve the amendment facts and deliver the amendment. One
    # early ``parse_dsl`` read serves the identity facts; the card fields of
    # step 6 come from the documents tuple, never a re-parse.
    header, _, _ = parse_dsl(pipeline_path.read_text())
    identity = PipelineIdentity(
        name=match.name,
        display_name=header.name,
        description=header.description,
        source=match.source.value,
    )

    # The kind-derivation matrix — the outcome of the resolution the rule set
    # performed but does not report: disabled wins, a resolved document under
    # an explicit name is "explicit", under no name "auto-match", and no
    # document (explicit-missing / auto-miss / containment escape) is a
    # silent miss.
    if no_workflow:
        decision = WorkflowDecision(kind="disabled", workflow_name=None)
    elif workflow_doc is None:
        decision = WorkflowDecision(kind="silent-miss", workflow_name=None)
    elif workflow not in (None, ""):
        decision = WorkflowDecision(kind="explicit", workflow_name=workflow)
    else:
        decision = WorkflowDecision(kind="auto-match", workflow_name=name)

    branch = resolve_current_branch_name() or "unknown"
    try:
        topic_dir = resolve_topic_dir(branch)
    except ValueError:
        topic_dir = None  # a fully unsluggable branch hosts no topic

    if topic_dir is not None and topic_dir.is_dir():
        work = WorkIdentity(branch=branch, slug=topic_dir.name, year=topic_dir.parent.name)
    else:
        work = WorkIdentity(branch=branch)

    hooks = PipelineHooks()
    if decision.kind != "disabled":
        overlay = hooks.amend_workflow(pipeline=identity, decision=decision, workflow=workflow_doc, work=work)
    else:
        # Disabled delivers nothing — the passthrough overlay of the resolved
        # workflow (None under a disabled decision); no registry is built.
        overlay = WorkflowOverlay(workflow=workflow_doc, provenance=[])

    # Step 4 — compile through the real machine into a throwaway temp dir,
    # with the effective workflow the amendment layer returned.
    # ``root_dir``/``project_name`` are not passed: they only shape top-level
    # output keys, never the stages the card reports.
    with tempfile.TemporaryDirectory(prefix="goga-pipeline-card-") as tmp:
        flow_path = Path(tmp) / "flow.yml"
        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=overlay.workflow)

    # Step 5 — order the compiled stages into execution order (loop copies are
    # separate rows already; skip removal happened in the compiler).
    ordered = order_stages(flow_doc.stages)

    logger.debug(
        "pipeline card composed",
        extra={
            "pipeline": name,
            "stages": len(ordered),
            "workflow_applied": overlay.workflow is not None,
            "provenance": overlay.provenance,
        },
    )

    # Steps 6-7 — the card: author-facing header values from the documents
    # tuple, one row per ordered stage, the contributing tools of the overlay.
    # The temp flow-file dies with its directory above.
    return PipelineCard(
        name=pipeline_doc.header.name,
        description=pipeline_doc.header.description,
        stages=[CardStage(id=stage.id, title=stage.name) for stage in ordered],
        provenance=overlay.provenance,
    )
