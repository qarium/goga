"""The ``WorkflowStage`` dataclass — one per-stage override instruction."""

from __future__ import annotations

from dataclasses import dataclass

from .workflow_reflect import WorkflowReflect


@dataclass(kw_only=True)
class WorkflowStage:
    """A single per-stage override instruction from a workflow-file.

    Args:
        agent: Agent name consumed by the compiler to compose the per-stage
            command wrapper path, or ``None`` when not specified.
        prompt: Per-stage prompt text consumed by the compiler as the stage
            description field, or ``None`` when not specified.
        loop: Positive iteration count (>= 1) instructing the compiler to
            expand the stage into N copies, or ``None`` when not specified.
        skills: List of skill names the compiler merges with the stage's
            pipeline-file skills (pipeline first, then these, deduplicated by
            value), or ``None`` when not specified (no merge).
        skip: Bool flag instructing the compiler to DELETE the corresponding
            stage entirely and transparently reconnect its dependents'
            ``depends_on``. ``False`` (the default, the key absent, or
            ``skip: false``) means the stage is NOT skipped; ``True``
            (``skip: true``) means the compiler removes it. Defaults to
            ``False`` — for ``skip`` absence is equivalent to ``False``.
        approve: Optional auto-approval directive consumed by the compiler
            when the stage runs. Accepted values are ``"auto"``, ``"plan"``,
            and ``"dialog"`` (any other value is rejected by ``parse_workflow``
            before this dataclass is built); ``None`` (the default) means no
            directive. The compiler applies two INDEPENDENT effects, each on
            its own trigger, and each value drives a subset of them:
            ``"auto"`` → both effects; ``"plan"`` → interactive suppression
            only (the ``interactive`` flag is suppressed when the body has
            ``communication: true``); ``"dialog"`` → the roles effect only
            (``auto_approve: true`` when the body's ``roles`` contain
            ``planner``). This cell does not act on ``approve`` — it is
            declarative.
        manual: Optional manual-launch instruction consumed by the compiler.
            ``None`` (the default) means the instruction is not given — the
            stage's own body decides the launch mode; ``True`` forces the
            manual launch mode; ``False`` explicitly cancels the resulting
            manual state of the stage regardless of which side authored it.
            The value is strictly a bool (any other value is rejected by
            ``parse_workflow`` before this dataclass is built). Defaults to
            ``None`` (NOT ``False``) — an absent key and an explicit
            ``manual: false`` are DIFFERENT instructions and must stay
            distinguishable to the compiler. This cell does not act on
            ``manual`` — it is declarative; the compiler applies the
            force / cancel logic.
        notes: Optional note-buttons instruction (a map of note name →
            prompt text), or ``None`` when not specified. Declarative —
            extracted here, consumed by the compiler to emit the stage's
            ``buttons`` field. An empty map equals absence (``parse_workflow``
            normalizes it to ``None``), so this field carries either ``None``
            or a non-empty map. This cell does not act on ``notes`` — it is
            declarative.
        reflect: Optional memory-reflection instruction (a
            :class:`WorkflowReflect` carrying the reflection file and the
            access mode), or ``None`` when not specified. Declarative —
            extracted here, consumed by the compiler to emit the stage's
            ``reflect`` field. This cell does not act on ``reflect`` — it is
            declarative; the compiler performs the emission when applying the
            workflow.
        memory: Optional memory-participation instruction, or ``None`` when
            not specified. Declarative — extracted here, consumed by the
            compiler to emit the stage's memory participation. An explicit
            ``memory: false`` equals absence (normalized to ``None`` by
            ``parse_workflow``), so this field carries either ``None`` or
            ``True``. This cell does not act on ``memory`` — it is
            declarative; the compiler performs the emission when applying the
            workflow.
    """

    agent: str | None = None
    prompt: str | None = None
    loop: int | None = None
    skills: list[str] | None = None
    skip: bool = False
    approve: str | None = None
    manual: bool | None = None
    notes: dict[str, str] | None = None
    reflect: WorkflowReflect | None = None
    memory: bool | None = None
