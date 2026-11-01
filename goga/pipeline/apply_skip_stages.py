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
          (``prompt=None``, ``extend={}``, ``memory=None``, ``profile=None``,
          ``build=None``).
        - The memory configuration, the profile field, and the build block of
          the input workflow survive the rebuild verbatim — a rebuild that
          dropped them would silently disable memory participation, change
          activation, or lose build instructions for skip-driven runs.
        - The assistants catalog and the delegation block of the input
          workflow survive the rebuild verbatim (the same objects, opaque) —
          the same carry precedent: a rebuild that dropped them would strip
          the collaboration plumbing of its declarations and task budget for
          skip-driven runs. A skipped stage's replacement entry carries the
          PRE-SKIP entry's ``assistants`` list (the same carry an authored
          skip: true stage keeps): the compiler removes the skipped stage
          before the attachment walk, so the stage's own attachments are
          never checked or emitted, but its inline DECLARATIONS stay in the
          document-wide assistant namespace — a surviving stage's reference
          to a name declared on the skipped stage keeps resolving.
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
    # The replacement carries the pre-skip entry's assistants — the compiler
    # removes the skipped stage before the attachment walk (its own
    # attachments are unreachable), but the namespace pass reads every stage
    # entry, so the stage's inline declarations stay resolvable for other
    # stages' references (the authored-``skip: true`` parity).
    for name in skip_stages:
        existing = new_stages.get(name)
        new_stages[name] = WorkflowStage(
            skip=True,
            assistants=(existing.assistants if existing is not None else None),
        )

    # Step 4 — return a NEW document; the input is NOT mutated. The memory
    # configuration, the profile field, the build block, the assistants
    # catalog, and the delegation block ride along verbatim (same objects,
    # opaque — never rebuilt); a None workflow with non-empty skip
    # synthesizes the default empty catalog and no delegation block.
    return WorkflowDocument(
        prompt=workflow.prompt if workflow is not None else None,
        stages=new_stages,
        extend=dict(workflow.extend) if workflow is not None else {},
        memory=workflow.memory if workflow is not None else None,
        profile=workflow.profile if workflow is not None else None,
        build=workflow.build if workflow is not None else None,
        assistants=workflow.assistants if workflow is not None else {},
        delegation=workflow.delegation if workflow is not None else None,
    )
