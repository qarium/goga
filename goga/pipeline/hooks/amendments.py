"""The read-and-contribute amendment view delivered at the hard amend_workflow checkpoint."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..workflow import ResolvedProfile, WorkflowDocument
from .identity import PipelineIdentity, WorkflowDecision, WorkIdentity


@dataclass(kw_only=True)
class WorkflowAmendment:
    """The read-and-contribute view of one tool at the amendment checkpoint.

    Args:
        pipeline: the identity of the pipeline being composed.
        decision: the workflow decision of the operation.
        workflow: the original authored workflow — post decision, post
            runner-skip merge, pre-layer; read-only and identical for
            every tool; ``None`` when no workflow resolved.
        work: the current work identity.
        profile: the operation's already-resolved active contributor
            profile — the profile that rendered the authored
            workflow-file: its name, its whole content, and its source —
            or ``None`` when no profile is active.
    """

    pipeline: PipelineIdentity
    decision: WorkflowDecision
    workflow: WorkflowDocument | None
    work: WorkIdentity
    profile: ResolvedProfile | None = None

    _contribution: WorkflowDocument | None = field(init=False, default=None, repr=False)

    def contribute(self, document: WorkflowDocument) -> None:
        """Buffer one declarative contribution; a later call replaces the earlier buffer.

        Args:
            document: the complete contribution — a
                :class:`~goga.pipeline.workflow.WorkflowDocument`-shaped
                set of instructions (prompt, stages, extend, memory,
                assistants, delegation, repeat, gates) using the same
                vocabulary an authored workflow-file uses.
        """

        self._contribution = document
