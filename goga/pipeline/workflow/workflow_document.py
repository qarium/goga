"""The ``WorkflowDocument`` dataclass — the aggregated declarative workflow-file document."""

from __future__ import annotations

from dataclasses import dataclass, field

from .workflow_assistant import WorkflowAssistant
from .workflow_build import WorkflowBuild
from .workflow_delegation import WorkflowDelegation
from .workflow_extend_stage import WorkflowExtendStage
from .workflow_memory import WorkflowMemory
from .workflow_stage import WorkflowStage


@dataclass(kw_only=True)
class WorkflowDocument:
    """Aggregated workflow-file document — top-level prompt plus per-stage overrides.

    Args:
        prompt: Top-level prompt text emitted by the compiler as the first
            top-level key of the compiled flow-file, or ``None`` when the
            workflow-file has no top-level prompt directive.
        stages: Map of per-stage override instructions keyed by stage name;
            each constructed document carries its own map. Empty map when the
            workflow-file has no stages section.
        extend: Map of new-stage declarations keyed by stage name (each a
            :class:`WorkflowExtendStage` carrying ``before``/``after``
            positioning and a verbatim body); each constructed document
            carries its own map. Empty map when the workflow-file has no
            extend section.
        memory: Workflow-memory configuration extracted from the optional
            top-level ``memory`` block (a :class:`WorkflowMemory` with
            materialized defaults), or ``None`` when the workflow-file
            carries no block. A workflow consisting of the block alone is
            valid.
        profile: The parsed counterpart of the peeked workflow default —
            activation reads the raw text via the peek, not this field;
            ``None`` when the workflow-file carries no top-level profile key.
        build: The six-field build block model (a :class:`WorkflowBuild`)
            consumed by the build path, or ``None`` when the workflow-file
            carries no block. A workflow consisting of the block alone is
            valid.
        assistants: The assistant catalog — an insertion-ordered map of
            :class:`WorkflowAssistant` keyed by name (the authored order is
            the delivery order of the run agents); an empty map (default)
            means no catalog.
        delegation: The delegation block (a :class:`WorkflowDelegation` with
            materialized defaults), or ``None`` when the workflow-file
            carries no block. A workflow consisting of the block alone is
            valid.
    """

    prompt: str | None = None
    stages: dict[str, WorkflowStage] = field(default_factory=dict)
    extend: dict[str, WorkflowExtendStage] = field(default_factory=dict)
    memory: WorkflowMemory | None = None
    profile: str | None = None
    build: WorkflowBuild | None = None
    assistants: dict[str, WorkflowAssistant] = field(default_factory=dict)
    delegation: WorkflowDelegation | None = None
