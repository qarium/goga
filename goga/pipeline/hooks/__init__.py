"""Hooks zone of the pipeline domain — the checkpoint surface of pipeline runs.

The zone owns the fact vocabulary of the run events (identity, contexts), the
authored-wins workflow overlay, the read-and-contribute amendment view, and the
``PipelineHooks`` checkpoint surface delivering the platform's first hard
action ``pipeline/amend_workflow`` and the two soft notifications
``pipeline/run_created`` / ``pipeline/run_completed``.

Built incrementally: each entity task adds its module's import and ``__all__``
entry. With the identity models, the run-event contexts, the authored-wins
overlay, and the amendment view landed, the three identity names, the three
context names, the three overlay names, and the amendment view are
re-exported here — ten of the eleven contract names.
"""

from .amendments import WorkflowAmendment
from .contexts import CompositionStage, RunCompleted, RunCreated
from .identity import PipelineIdentity, WorkflowDecision, WorkIdentity
from .overlay import ToolContribution, WorkflowOverlay, merge_workflow_overlay

__all__: list[str] = [
    "CompositionStage",
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
