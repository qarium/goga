"""Compose the single pipeline card: header values plus post-workflow stages in execution order."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from ..history import resolve_current_branch_name, resolve_topic_dir
from .apply_skip_stages import apply_skip_stages
from .compiler import compile_flow, parse_dsl
from .hooks import PipelineHooks, PipelineIdentity, WorkflowDecision, WorkflowOverlay, WorkIdentity
from .list_pipelines import list_pipelines
from .order_stages import order_stages
from .pipeline_card import CardStage, PipelineCard
from .pipeline_entry import PipelineSource
from .resolve_workflow import resolve_workflow

logger = logging.getLogger(__name__)


def describe_pipeline(  # noqa: PLR0913, PLR0917 — the 6-parameter signature is the CODEMANIFEST contract
    name: str,
    project_dir: Path,
    user_dir: Path,
    workflow: str | None,
    no_workflow: bool,
    skip: list[str] | None = None,
) -> PipelineCard:
    """Compose the card of one pipeline: header values plus ordered stage rows; nothing is executed.

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
            name; the ``skip`` names still compose).
        skip: stage names to exclude from the composition — the repeatable
            ``-s/--skip`` flag values passed to the card, merged exactly as
            a run with the same flags merges them. ``None`` and ``[]`` both
            mean no skip; otherwise the names merge onto the resolved
            workflow in memory via :func:`apply_skip_stages` (name
            validation is the compiler's structural error, not performed
            here).

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
    resolved = resolve_workflow(name, workflow, no_workflow)

    # Step 3 — merge the skip names (the repeatable ``-s/--skip`` flag values
    # the card caller forwards) onto the resolved workflow without mutating it
    # — the same in-memory merge a run applies before its delivery.
    # ``None``/empty is a no-op; otherwise the merged document carries
    # ``WorkflowStage(skip=True)`` entries that ``compile_flow`` turns into
    # stage removal + ``depends_on`` reconnection. Name validation is the
    # compiler's structural error, not performed here.
    workflow_doc = apply_skip_stages(resolved, skip or [])

    # Step 4 — resolve the amendment facts and deliver the amendment. One
    # early ``parse_dsl`` read serves the identity facts; the card fields of
    # step 7 come from the documents tuple, never a re-parse.
    header, _, _ = parse_dsl(pipeline_path.read_text())
    identity = PipelineIdentity(
        name=match.name,
        display_name=header.name,
        description=header.description,
        source=match.source.value,
    )

    # The kind-derivation matrix — the outcome of the PRE-merge resolution
    # the rule set performed but does not report: disabled wins, a resolved
    # document under an explicit name is "explicit", under no name
    # "auto-match", and no document (explicit-missing / auto-miss /
    # containment escape) is a silent miss. The matrix never reads the
    # merged document — a skip-only document synthesized over a missing
    # workflow is not a resolution.
    if no_workflow:
        decision = WorkflowDecision(kind="disabled", workflow_name=None)
    elif resolved is None:
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
        # Disabled delivers nothing — the passthrough overlay of the MERGED
        # workflow (the skip names still compose; ``None`` under a disabled
        # decision without skip names); no registry is built.
        overlay = WorkflowOverlay(workflow=workflow_doc, provenance=[])

    # Step 5 — compile through the real machine into a throwaway temp dir,
    # with the effective workflow the amendment layer returned.
    # ``root_dir``/``project_name`` are not passed: they only shape top-level
    # output keys, never the stages the card reports.
    with tempfile.TemporaryDirectory(prefix="goga-pipeline-card-") as tmp:
        flow_path = Path(tmp) / "flow.yml"
        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=overlay.workflow)

    # Step 6 — order the compiled stages into execution order (loop copies are
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

    # Steps 7-8 — the card: author-facing header values from the documents
    # tuple, one row per ordered stage, the contributing tools of the overlay.
    # The temp flow-file dies with its directory above.
    return PipelineCard(
        name=pipeline_doc.header.name,
        description=pipeline_doc.header.description,
        stages=[CardStage(id=stage.id, title=stage.name) for stage in ordered],
        provenance=overlay.provenance,
    )
