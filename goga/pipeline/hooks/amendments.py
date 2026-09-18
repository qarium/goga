"""The amendment view of the pipeline domain — the read-and-contribute view.

``WorkflowAmendment`` is the context one tool receives at the hard
``pipeline/amend_workflow`` checkpoint: the delivered facts of the
composition (the pipeline identity, the workflow decision, the original
authored workflow, and the current work identity) plus the buffer of that
one tool's contribution. The view is read-and-contribute — reads deliver
the original facts (no staged-application state exists, a tool never sees
another tool's contribution), and :meth:`contribute` is the only write
channel, buffering one declarative document until the delivery commits it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..workflow import WorkflowDocument
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
    """

    pipeline: PipelineIdentity
    decision: WorkflowDecision
    workflow: WorkflowDocument | None
    work: WorkIdentity

    _contribution: WorkflowDocument | None = field(init=False, default=None, repr=False)

    def contribute(self, document: WorkflowDocument) -> None:
        """Buffer one declarative contribution of this tool.

        The replacement is whole — a later call replaces the earlier
        buffered document. No validation lives here: a bad document
        surfaces at the consumer, and an empty document (no prompt, no
        stages, no extend, no memory) is discarded by the delivery with a
        warning. The call changes nothing until the delivery commits it —
        it does not cancel, redirect, or defer the operation.

        Args:
            document: the complete contribution — a
                :class:`~goga.pipeline.workflow.WorkflowDocument`-shaped
                set of instructions (prompt, stages, extend, memory) using
                the same vocabulary an authored workflow-file uses.
        """

        self._contribution = document
