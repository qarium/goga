"""Hooks zone of the pipeline domain: identity, contexts, overlay, amendment view, checkpoints."""

from .amendments import WorkflowAmendment
from .contexts import CompositionStage, RunCompleted, RunCreated
from .events import PipelineHooks
from .identity import PipelineIdentity, WorkflowDecision, WorkIdentity
from .overlay import ToolContribution, WorkflowOverlay, merge_workflow_overlay

__all__: list[str] = [
    "CompositionStage",
    "PipelineHooks",
    "PipelineIdentity",
    "RunCompleted",
    "RunCreated",
    "ToolContribution",
    "WorkIdentity",
    "WorkflowAmendment",
    "WorkflowDecision",
    "WorkflowOverlay",
    "merge_workflow_overlay",
]
