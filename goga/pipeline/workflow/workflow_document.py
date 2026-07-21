"""The ``WorkflowDocument`` dataclass — the aggregated workflow-file document.

A workflow-file combines an optional top-level ``prompt``, a map of
per-stage override instructions (``stages``, keyed by stage name), and a map
of new-stage declarations (``extend``, keyed by stage name).
``WorkflowDocument`` is the single parsed value representing the whole file.
It is built by ``parse_workflow`` and consumed by the compiler via its
workflow parameter.

The model is intentionally declarative — it carries instructions, never
their resolution. ``prompt`` is verbatim text (the compiler emits it as the
first top-level key of the flow-file); ``stages`` is a verbatim map of
``WorkflowStage`` instructions (the compiler applies each to the matching
pipeline stage); ``extend`` is a verbatim map of ``WorkflowExtendStage``
declarations (the compiler embeds each as a new stage). No validation lives
here: ``parse_workflow`` enforces every structural invariant (key set, field
types, the at-least-one requirement) and raises a structural error before
this dataclass is built.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .workflow_extend_stage import WorkflowExtendStage
from .workflow_stage import WorkflowStage


@dataclass(kw_only=True)
class WorkflowDocument:
    """Aggregated workflow-file document — top-level prompt plus per-stage overrides.

    ``prompt`` defaults to ``None`` and ``stages``/``extend`` default to
    empty dicts via ``field(default_factory=dict)`` (the DSL signature lists
    ``None``; the factory is applied at construction so two documents never
    share a stages or extend map). A workflow-file with neither a top-level
    ``prompt``, any stage entries, nor any extend entries is rejected by
    ``parse_workflow`` with a structural error before this dataclass is
    built — at least one must be present. The new ``extend`` field is
    backward-compatible: its default means existing consumers (which never
    pass ``extend``) keep working.

    Args:
        prompt: Top-level prompt text emitted by the compiler as the first
            top-level key of the compiled flow-file, or ``None`` when the
            workflow-file has no top-level prompt directive.
        stages: Map of per-stage override instructions keyed by stage name.
            Empty map when the workflow-file has no stages section.
        extend: Map of new-stage declarations keyed by stage name (each a
            :class:`WorkflowExtendStage` carrying ``before``/``after``
            positioning and a verbatim body). Empty map when the workflow-file
            has no extend section.
    """

    prompt: str | None = None
    stages: dict[str, WorkflowStage] = field(default_factory=dict)
    extend: dict[str, WorkflowExtendStage] = field(default_factory=dict)
