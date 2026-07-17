"""The ``WorkflowDocument`` dataclass — the aggregated workflow-file document.

A workflow-file combines an optional top-level ``prompt`` and a map of
per-stage override instructions (``stages``, keyed by stage name).
``WorkflowDocument`` is the single parsed value representing the whole file.
It is built by ``parse_workflow`` and consumed by the compiler via its
workflow parameter.

The model is intentionally declarative — it carries instructions, never
their resolution. ``prompt`` is verbatim text (the compiler emits it as the
first top-level key of the flow-file); ``stages`` is a verbatim map of
``WorkflowStage`` instructions (the compiler applies each to the matching
pipeline stage). No validation lives here: ``parse_workflow`` enforces every
structural invariant (key set, field types, the at-least-one requirement)
and raises a structural error before this dataclass is built.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .workflow_stage import WorkflowStage


@dataclass(kw_only=True)
class WorkflowDocument:
    """Aggregated workflow-file document — top-level prompt plus per-stage overrides.

    ``prompt`` defaults to ``None`` and ``stages`` defaults to an empty dict
    via ``field(default_factory=dict)`` (the DSL signature lists ``None``;
    the factory is applied at construction so two documents never share a
    stages map). A workflow-file with neither a top-level ``prompt`` nor any
    stage entries is rejected by ``parse_workflow`` with a structural error
    before this dataclass is built — at least one must be present.

    Args:
        prompt: Top-level prompt text emitted by the compiler as the first
            top-level key of the compiled flow-file, or ``None`` when the
            workflow-file has no top-level prompt directive.
        stages: Map of per-stage override instructions keyed by stage name.
            Empty map when the workflow-file has no stages section.
    """

    prompt: str | None = None
    stages: dict[str, WorkflowStage] = field(default_factory=dict)
