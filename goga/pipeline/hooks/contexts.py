"""Run-event contexts — read-only fact bundles a hook observes but cannot alter."""

from __future__ import annotations

from dataclasses import dataclass

from ..workflow import WorkflowDocument
from .identity import PipelineIdentity, WorkflowDecision, WorkIdentity


@dataclass(kw_only=True)
class CompositionStage:
    """One row of the final composition — the stage identity and its display title.

    Args:
        id: the stage identifier.
        title: the stage display title.
    """

    id: str
    title: str


@dataclass(kw_only=True)
class RunCreated:
    """The read-only context of the run-creation notification — the facts before the runner launch.

    Args:
        pipeline: the identity of the running pipeline.
        decision: the workflow decision of the operation.
        workflow: the final effective workflow — authored instructions
            plus the committed tool contributions, or ``None`` when no
            effective workflow exists.
        composition: the ordered stages of the final composition — one
            row per compiled stage, as the card shows them.
        provenance: the tools whose contributions committed, in
            enumeration order.
        work: the current work identity.
        statuses: the maximal present statuses of the work's topic at the
            moment — both axes, built-in and tool.
        runtime_dir: the run's runtime directory as a posix string.
    """

    pipeline: PipelineIdentity
    decision: WorkflowDecision
    workflow: WorkflowDocument | None
    composition: list[CompositionStage]
    provenance: list[str]
    work: WorkIdentity
    statuses: list[str]
    runtime_dir: str


@dataclass(kw_only=True)
class RunCompleted:
    """The read-only context of the run-completion notification — recomputed facts plus launch outcome.

    Args:
        pipeline: the identity of the running pipeline.
        decision: the workflow decision of the operation.
        workflow: the final effective workflow the run executed, or
            ``None`` when no effective workflow existed.
        composition: the ordered stages of the executed composition.
        provenance: the tools whose contributions committed, in
            enumeration order.
        work: the current work identity.
        statuses: the maximal present statuses of the work's topic
            recomputed at the completion moment.
        runtime_dir: the run's runtime directory as a posix string.
        exit_code: the actual exit code of the launch attempt — zero,
            non-zero, or a spawn failure (126/127).
    """

    pipeline: PipelineIdentity
    decision: WorkflowDecision
    workflow: WorkflowDocument | None
    composition: list[CompositionStage]
    provenance: list[str]
    work: WorkIdentity
    statuses: list[str]
    runtime_dir: str
    exit_code: int
