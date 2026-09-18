"""Hooks zone of the pipeline domain — the checkpoint surface of pipeline runs.

The zone owns the fact vocabulary of the run events (identity, contexts), the
authored-wins workflow overlay, the read-and-contribute amendment view, and the
``PipelineHooks`` checkpoint surface delivering the platform's first hard
action ``pipeline/amend_workflow`` and the two soft notifications
``pipeline/run_created`` / ``pipeline/run_completed``.

Built incrementally: each entity task adds its module's import and ``__all__``
entry. With the identity models landed, the three identity names are
re-exported here — three of the eleven contract names.
"""

from .identity import PipelineIdentity, WorkflowDecision, WorkIdentity

__all__: list[str] = [
    "PipelineIdentity",
    "WorkIdentity",
    "WorkflowDecision",
]
