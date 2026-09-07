"""The ``WorkflowStage`` dataclass — one per-stage override instruction.

A workflow-file's ``stages`` map carries one entry per pipeline stage the
workflow wants to override. ``WorkflowStage`` is the parsed representation of a
single such entry: which agent to run, which per-stage prompt to merge, how
many loop iterations to expand the stage into, which skills to merge into
the stage. It is constructed by ``parse_workflow`` and carried verbatim inside
``WorkflowDocument``.

The model is intentionally declarative — it holds instructions, never their
resolution. ``agent`` is the raw agent name (the compiler composes the wrapper
path); ``prompt`` is verbatim text (the compiler places it in the description
slot); ``loop`` is a count (the compiler expands it); ``skills`` is a list of
skill names (the compiler merges them with the stage's pipeline-file skills);
``skip`` is a bool flag (the compiler deletes the corresponding stage and
transparently reconnects its dependents' ``depends_on``); ``approve`` is an
optional auto-approval directive — one of ``"auto"``/``"plan"``/``"dialog"``
(the compiler suppresses the stage's ``interactive`` flag and/or emits
``auto_approve: true``, each value driving a subset of these two effects);
``manual`` is an optional manual-launch instruction — strictly a bool, with
``None`` (the default, key absent), ``True`` (force), and ``False``
(explicit cancel) as three DIFFERENT states: an absent key and an explicit
``manual: false`` are distinct instructions (the compiler resolves them);
``notes`` is an optional map of note name → prompt text (a declarative
note-buttons instruction — the compiler emits the stage's ``buttons`` field
from it); ``reflect`` is an optional memory-reflection instruction (a
:class:`WorkflowReflect` naming the reflection file and its access mode);
``memory`` is an optional memory-participation instruction (a bool). The two
memory instructions are declarative — extracted here, consumed by the
compiler to emit the stage's ``reflect`` field / ``memory_use`` participation
when the workflow's memory block is emitted. No validation lives here
either: ``parse_workflow`` enforces every invariant (key set, field types,
``loop >= 1``, ``skip`` is a bool, ``approve`` is one of
``"auto"``/``"plan"``/``"dialog"``, ``manual`` is a bool, ``notes`` is a
str→str map, ``reflect`` is a ``{file, mode}`` mapping, ``memory`` is a bool)
and raises a structural error before this dataclass is built.

Field order is fixed — ``agent``, ``prompt``, ``loop``, ``skills``, ``skip``,
``approve``, ``manual``, ``notes``, ``reflect``, ``memory`` — to match the
canonical order of the per-stage keys in the workflow-file.
"""

from __future__ import annotations

from dataclasses import dataclass

from .workflow_reflect import WorkflowReflect


@dataclass(kw_only=True)
class WorkflowStage:
    """A single per-stage override instruction from a workflow-file.

    The nine fields ``agent``, ``prompt``, ``loop``, ``skills``,
    ``approve``, ``manual``, ``notes``, ``reflect``, and ``memory`` default to
    ``None`` — a workflow-file may omit any of them, and ``parse_workflow``
    produces ``None`` for missing fields; ``skip`` defaults to ``False``.
    Field order is fixed (``agent``, ``prompt``, ``loop``, ``skills``,
    ``skip``, ``approve``, ``manual``, ``notes``, ``reflect``, ``memory``) to
    match the canonical order of the per-stage keys in the workflow-file.

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

              * ``"auto"``   → both effects.
              * ``"plan"``   → interactive suppression only (communication
                effect): the stage's ``interactive`` flag is suppressed (omitted)
                when the body has ``communication: true``. The roles effect
                (``auto_approve``) does NOT fire.
              * ``"dialog"`` → roles effect only: ``auto_approve: true`` is
                emitted when the body's ``roles`` contain ``planner``. The
                communication effect does NOT fire.

            This cell does not act on ``approve`` — it is declarative.
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
