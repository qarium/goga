"""The ``describe_pipeline`` Routine — the single pipeline card via the compile machine.

Composes the informational card of ONE pipeline: the author-facing
name/description from the DSL header plus the post-workflow stage composition
in execution order. The card deliberately shares the run path's machinery —
the same :func:`~goga.pipeline.resolve_workflow.resolve_workflow` rule set and
the same :func:`~goga.pipeline.compiler.compile_flow` compiler — so the
composition the card reports is structurally the composition the run executes.
Workflow ``skip`` directives therefore apply (they are compiler directives),
loop copies appear as separate ``NAME-1..N`` rows, while the run-only
``GOGA_SKIP_STAGES`` environment variable is NOT read — the card answers
"what is this pipeline?", not "what would this particular run skip?".

The compiled flow-file is written to a throwaway temp directory (never the
project tree or a runtime directory) and removed once the card is composed.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from .compiler import compile_flow
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
    basename auto-match, silent miss), the pipeline is compiled through the
    real :func:`compile_flow` machine into a temp flow-file (no ``root_dir`` /
    ``project_name`` — they only affect discarded top-level keys, never the
    stages), and the compiled stages are ordered by
    :func:`~goga.pipeline.order_stages.order_stages` into execution order.
    ``name``/``description`` are the author-facing header values (they may
    differ from the discovered file stem).

    Nothing is executed: no afm invocation, no stage run, no prompt
    materialization. The temp flow-file is the only write and is removed on
    routine exit.

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
        The composed :class:`~goga.pipeline.pipeline_card.PipelineCard`.

    Raises:
        RuntimeError: If no discovered pipeline carries ``name`` (message
            ``"pipeline '<name>' is missing"``).
        WorkflowSyntaxError: On a structural defect in a resolved
            workflow-file, propagated unchanged from ``parse_workflow`` via
            ``resolve_workflow``.
        StructuralError: On a structural defect in the pipeline DSL,
            propagated unchanged from ``compile_flow``.
        yaml.YAMLError: If the pipeline-file is not valid YAML, propagated
            unchanged from ``compile_flow``.
        OSError: If the pipeline-file cannot be read or the temp flow-file
            cannot be written, propagated unchanged.
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

    # Step 3 — compile through the real machine into a throwaway temp dir.
    # ``root_dir``/``project_name`` are not passed: they only shape top-level
    # output keys, never the stages the card reports.
    with tempfile.TemporaryDirectory(prefix="goga-pipeline-card-") as tmp:
        flow_path = Path(tmp) / "flow.yml"
        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow_doc)

    # Step 4 — order the compiled stages into execution order (loop copies are
    # separate rows already; skip removal happened in the compiler).
    ordered = order_stages(flow_doc.stages)

    logger.debug(
        "pipeline card composed",
        extra={"pipeline": name, "stages": len(ordered), "workflow_applied": workflow_doc is not None},
    )

    # Step 5 — the card: author-facing header values + stage rows. The header
    # comes from the documents tuple, never a re-parse of the pipeline-file.
    return PipelineCard(
        name=pipeline_doc.header.name,
        description=pipeline_doc.header.description,
        stages=[CardStage(id=stage.id, title=stage.name) for stage in ordered],
    )
