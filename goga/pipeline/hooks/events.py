"""The checkpoint surface of the pipeline domain — the events cell of the zone.

The entity declared in the cell CODEMANIFEST with ``location: events.py``:
``PipelineHooks`` — the amendment delivery and the two run notifications of
the pipeline flows over the platform facade. Construction is cheap and every
context is built from the values the caller passes; one lazily-built run
registry carries every checkpoint of a command, so the package enumeration
happens once per run whatever the number of checkpoints. The amendment is
the platform's first hard action — the first failing tool stops the command
and its whole contribution is discarded — while the two notifications are
soft fire-and-forget emissions: a failing hook warns inside the platform
and never affects the run.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...hooks import (
    HookRegistry,
    build_hook_arguments,
    declared_actions,
    emit_hook_event,
    wrap_context,
)
from .amendments import WorkflowAmendment
from .contexts import CompositionStage, RunCompleted, RunCreated
from .identity import PipelineIdentity, WorkflowDecision, WorkIdentity
from .overlay import ToolContribution, WorkflowOverlay, merge_workflow_overlay

if TYPE_CHECKING:  # the workflow document is a context fact the zone models carry
    from ..workflow import WorkflowDocument

logger = logging.getLogger(__name__)


class PipelineHooks:
    """The checkpoint surface of the pipeline domain.

    Owns the single run registry shared by the amendment delivery and the
    two run notifications, and drives the delivery per tool with staged
    commit over the public primitives of the hooks platform. Tools are
    mutually blind — every amendment view reads the same original authored
    workflow, never a staged state; a tool's contribution commits only
    after every hook of the tool succeeded.

    Requirements:
        - Cheap construction — no enumeration and no imports happen at
          construction
        - One ``HookRegistry`` per run carries every checkpoint of a
          command — the assembly runs once per run whatever the number of
          checkpoints
        - Every context is built from the values the caller passes — no
          repository reads happen at a checkpoint
    """

    def __init__(self) -> None:
        """Create the checkpoint surface of one command.

        Nothing is enumerated and nothing is imported: the run registry
        builds lazily on the first checkpoint that needs it.
        """
        self._registry: HookRegistry | None = None

    def _ensure_registry(self) -> HookRegistry:
        """Build the run registry once — the shared state of every checkpoint.

        Returns:
            The assembled registry of the run — built on the first call and
            reused by every checkpoint; never rebuilt on the same surface.

        Raises:
            ImportError: A tool package exists but its facade fails to
                import — the single fatal case; the message names the
                package.
        """
        if self._registry is None:
            registry = HookRegistry()
            registry.build_once()
            self._registry = registry

        return self._registry

    def amend_workflow(
        self,
        pipeline: PipelineIdentity,
        decision: WorkflowDecision,
        workflow: WorkflowDocument | None,
        work: WorkIdentity,
    ) -> WorkflowOverlay:
        """Deliver the workflow-amendment checkpoint and return the overlay.

        Algorithm:
            1. Resolve the address ``pipeline.amend_workflow`` against
               ``declared_actions`` — an unknown address is a clean error
               of the emitting side
            2. Walk the subscriptions of the address per tool in
               enumeration order: build the tool's ``WorkflowAmendment``
               view over the delivered facts — every tool reads the same
               original ``workflow`` — wrap it via ``wrap_context``,
               project the call arguments via ``build_hook_arguments``
               with the tool's own context, and call each hook of the tool
            3. A tool whose every hook returned without raising and whose
               buffer carries a non-empty contribution commits as one
               ``ToolContribution``
            4. A tool with a raising hook is a hard failure: a clean error
               naming the hook, the tool, and the action stops the command
               at the first failure; the tool's whole contribution is
               discarded together with its view
            5. A tool whose buffered document is empty — no prompt, no
               stages, no extend, no memory — is a content no-op: a
               warning naming the tool, the contribution discarded, the
               walk continues
            6. Merge the committed contributions onto ``workflow`` via
               ``merge_workflow_overlay`` and return the overlay — an
               address without subscriptions returns the passthrough
               overlay

        Args:
            pipeline: The identity of the pipeline being composed.
            decision: The workflow decision of the operation.
            workflow: The authored workflow after the decision and the
                runner-skip merge; ``None`` when no workflow resolved.
            work: The current work identity.

        Returns:
            The :class:`~goga.pipeline.hooks.WorkflowOverlay` — the
            effective workflow and the contributing tools.

        Raises:
            ValueError: The address is not declared, or a hook of the
                hard action failed — the message names the hook, the
                tool, and the reason.
        """
        registry = self._ensure_registry()

        record = next(
            (entry for entry in declared_actions() if entry.domain == "pipeline" and entry.name == "amend_workflow"),
            None,
        )
        if record is None:
            raise ValueError("unknown hook action: pipeline.amend_workflow")

        groups: dict[str, list] = {}
        for subscription in registry.subscriptions_for("pipeline", "amend_workflow"):
            groups.setdefault(subscription.tool, []).append(subscription)

        contributions: list[ToolContribution] = []

        for tool, subscriptions in groups.items():
            # A fresh view per tool — fresh facts, fresh buffer; the view
            # dies with the tool when a hook fails, taking the buffer with it.
            amendment = WorkflowAmendment(pipeline=pipeline, decision=decision, workflow=workflow, work=work)
            proxy = wrap_context(amendment)

            for subscription in subscriptions:
                try:
                    subscription.hook(**build_hook_arguments(subscription.hook, proxy, registry.self_context(tool)))
                except Exception as reason:
                    # Hard: stop at the first failure. The message copies the
                    # platform's format — hook name, tool, address, reason.
                    raise ValueError(
                        f"hook {subscription.name} of tool {tool} failed on pipeline.amend_workflow: {reason}"
                    ) from reason

            if amendment._contribution is None:
                continue  # never contributed — silent

            document = amendment._contribution
            if document.prompt is None and not document.stages and not document.extend and document.memory is None:
                logger.warning(
                    "tool %s contributed an empty document to pipeline.amend_workflow: discarded",
                    tool,
                )
                continue

            contributions.append(ToolContribution(tool=tool, document=document))

        return merge_workflow_overlay(workflow, contributions)

    # The parameter list is fixed by the cell contract — the CODEMANIFEST
    # declares every fact the context carries.
    def emit_run_created(  # noqa: PLR0913, PLR0917
        self,
        pipeline: PipelineIdentity,
        decision: WorkflowDecision,
        overlay: WorkflowOverlay,
        composition: list[CompositionStage],
        work: WorkIdentity,
        statuses: list[str],
        runtime_dir: str,
    ) -> None:
        """Emit the run-creation notification — the facts before the launch.

        Fire-and-forget: nothing is collected and no value returns. A
        failing hook is skipped with a warning under the soft error class
        of the action — the launch proceeds.

        Args:
            pipeline: The identity of the running pipeline.
            decision: The workflow decision of the operation.
            overlay: The amendment result — the effective workflow and
                the provenance.
            composition: The ordered stages of the final composition.
            work: The current work identity.
            statuses: The maximal present statuses at the moment.
            runtime_dir: The run's runtime directory as a posix string.
        """
        context = RunCreated(
            pipeline=pipeline,
            decision=decision,
            workflow=overlay.workflow,
            composition=composition,
            provenance=overlay.provenance,
            work=work,
            statuses=statuses,
            runtime_dir=runtime_dir,
        )

        emit_hook_event(
            self._ensure_registry(),
            "pipeline",
            "run_created",
            context_for=lambda _tool: context,
        )

    def emit_run_completed(  # noqa: PLR0913, PLR0917
        self,
        pipeline: PipelineIdentity,
        decision: WorkflowDecision,
        overlay: WorkflowOverlay,
        composition: list[CompositionStage],
        work: WorkIdentity,
        statuses: list[str],
        runtime_dir: str,
        exit_code: int,
    ) -> None:
        """Emit the run-completion notification — the finished attempt's facts.

        Fire-and-forget: nothing is collected and no value returns. The
        emission happens on every launch-attempt return path — zero,
        non-zero, and spawn failures alike — and a failing hook warns
        under the soft error class: the exit code of the run is never
        affected.

        Args:
            pipeline: The identity of the running pipeline.
            decision: The workflow decision of the operation.
            overlay: The amendment result of the run.
            composition: The ordered stages of the executed composition.
            work: The current work identity.
            statuses: The maximal present statuses recomputed at the
                completion moment.
            runtime_dir: The run's runtime directory as a posix string.
            exit_code: The actual exit code of the launch attempt.
        """
        context = RunCompleted(
            pipeline=pipeline,
            decision=decision,
            workflow=overlay.workflow,
            composition=composition,
            provenance=overlay.provenance,
            work=work,
            statuses=statuses,
            runtime_dir=runtime_dir,
            exit_code=exit_code,
        )

        emit_hook_event(
            self._ensure_registry(),
            "pipeline",
            "run_completed",
            context_for=lambda _tool: context,
        )
