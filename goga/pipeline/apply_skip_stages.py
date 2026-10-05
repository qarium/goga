"""In-memory merge of CLI skip directives onto a workflow document — no mutation, no validation."""

from __future__ import annotations

from .workflow import WorkflowDocument, WorkflowStage


def apply_skip_stages(workflow: WorkflowDocument | None, skip_stages: list[str]) -> WorkflowDocument | None:
    """Merge CLI skip directives into a workflow document without mutation.

    Requirements:
        - Empty ``skip_stages`` is a no-op — return the input unchanged
          (``None`` stays ``None``; no skip applied).
        - Skip always wins — a name present in both the workflow stages and
          ``skip_stages`` is replaced with a ``WorkflowStage(skip=True)`` (all
          other fields at defaults — ``notes`` stays ``None``, the model-field
          default).
        - Do not mutate the input ``workflow`` or its stages/extend maps.
        - When ``workflow`` is ``None`` and ``skip_stages`` is non-empty,
          construct a document whose stages map carries only the skip entries
          (``prompt=None``, ``extend={}``, ``memory=None``).
        - The memory configuration of the input workflow survives the rebuild
          verbatim — a rebuild that drops it would silently disable memory
          participation for skip-driven runs.
        - Stage-name validation is NOT performed here — the compiler's strict
          check raises a structural error on a name absent from the pipeline
          body; this Routine stays declarative.

    Args:
        workflow: Optional ``WorkflowDocument`` resolved by ``run_pipeline``
            (parsed from a workflow-file, or ``None`` when no workflow resolved).
        skip_stages: Stage names to skip (the repeatable ``-s/--skip`` flag
            names passed by run coordination and the card); an empty list is
            a no-op.

    Returns:
        The resulting ``WorkflowDocument`` carrying the skip directives, or the
        input unchanged when ``skip_stages`` is empty (``None`` stays ``None``).

    Constraints:
        - Do not interpret, validate, or rebuild the memory configuration — it
          is carried as an opaque value (per the ``memory`` practice).
    """
    # Step 1 — empty skip is a no-op (None stays None; input returned as-is).
    if not skip_stages:
        return workflow

    # Step 2 — build a NEW stages map isolated from the input's map.
    new_stages = dict(workflow.stages) if workflow is not None else {}

    # Step 3 — skip wins: each name fully replaces any pre-existing entry.
    for name in skip_stages:
        new_stages[name] = WorkflowStage(skip=True)

    # Step 4 — return a NEW document; the input is NOT mutated. The memory
    # configuration rides along verbatim (same object, opaque — never rebuilt).
    return WorkflowDocument(
        prompt=workflow.prompt if workflow is not None else None,
        stages=new_stages,
        extend=dict(workflow.extend) if workflow is not None else {},
        memory=workflow.memory if workflow is not None else None,
    )
