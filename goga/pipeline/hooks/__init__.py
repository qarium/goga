"""Hooks zone of the pipeline domain: identity, contexts, overlay, amendment view, checkpoints."""

from .amendments import WorkflowAmendment
from .contexts import (
    CompositionStage,
    RunCompleted,
    RunCreated,
    RunEvent,
    RunIdentity,
    StageEvent,
    StageTransition,
)
from .events import PipelineHooks
from .identity import PipelineIdentity, WorkflowDecision, WorkIdentity
from .overlay import ToolContribution, WorkflowOverlay, merge_workflow_overlay

__all__: list[str] = [
    "CompositionStage",
    "PipelineHooks",
    "PipelineIdentity",
    "RunCompleted",
    "RunCreated",
    "RunEvent",
    "RunIdentity",
    "StageEvent",
    "StageTransition",
    "ToolContribution",
    "WorkIdentity",
    "WorkflowAmendment",
    "WorkflowDecision",
    "WorkflowOverlay",
    "merge_workflow_overlay",
]
