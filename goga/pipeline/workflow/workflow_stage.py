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
optional auto-approval directive (the compiler suppresses the stage's
``interactive`` flag and/or emits ``auto_approve: true`` when ``"auto"``).
No validation lives here either: ``parse_workflow`` enforces every invariant
(key set, field types, ``loop >= 1``, ``skip`` is a bool, ``approve`` is
``"auto"``) and raises a structural error before this dataclass is built.

Field order is fixed — ``agent``, ``prompt``, ``loop``, ``skills``, ``skip``,
``approve`` — to match the canonical order of the per-stage keys in the
workflow-file.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowStage:
    """A single per-stage override instruction from a workflow-file.

    The five fields ``agent``, ``prompt``, ``loop``, ``skills``, and ``approve``
    default to ``None`` — a workflow-file may omit any of them, and
    ``parse_workflow`` produces ``None`` for missing fields; ``skip`` defaults
    to ``False``. Field order is fixed (``agent``, ``prompt``, ``loop``,
    ``skills``, ``skip``, ``approve``) to match the canonical order of the
    per-stage keys in the workflow-file.

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
    """

    agent: str | None = None
    prompt: str | None = None
    loop: int | None = None
    skills: list[str] | None = None
    skip: bool = False
    approve: str | None = None
