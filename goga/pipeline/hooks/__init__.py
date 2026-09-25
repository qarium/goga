"""Hooks zone of the pipeline domain — the checkpoint surface of pipeline runs.

The zone owns the fact vocabulary of the run events (identity, contexts), the
authored-wins workflow overlay, the read-and-contribute amendment view, and the
``PipelineHooks`` checkpoint surface delivering the platform's first hard
action ``pipeline/amend_workflow`` and the two soft notifications
``pipeline/run_created`` / ``pipeline/run_completed``.

Built incrementally: each entity task added its module's import and
``__all__`` entry. With the identity models, the run-event contexts, the
authored-wins overlay, the amendment view, and the checkpoint surface landed,
the eleven contract names of the zone are re-exported here.
"""

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
