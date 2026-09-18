"""Hooks zone of the pipeline domain — the checkpoint surface of pipeline runs.

The zone owns the fact vocabulary of the run events (identity, contexts), the
authored-wins workflow overlay, the read-and-contribute amendment view, and the
``PipelineHooks`` checkpoint surface delivering the platform's first hard
action ``pipeline/amend_workflow`` and the two soft notifications
``pipeline/run_created`` / ``pipeline/run_completed``.

Built incrementally: each entity task adds its module's import and ``__all__``
entry. With the identity models and the run-event contexts landed, the three
identity names and the three context names are re-exported here — six of the
eleven contract names.
"""

from .contexts import CompositionStage, RunCompleted, RunCreated
from .identity import PipelineIdentity, WorkflowDecision, WorkIdentity

__all__: list[str] = [
    "CompositionStage",
    "PipelineIdentity",
    "RunCompleted",
    "RunCreated",
    "WorkIdentity",
    "WorkflowDecision",
]
