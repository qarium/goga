"""The ``WorkflowStage`` dataclass — one per-stage override instruction.

A workflow-file's ``stages`` map carries one entry per pipeline stage the
workflow wants to override. ``WorkflowStage`` is the parsed representation of a
single such entry: which agent to run, which per-stage prompt to merge, and
how many loop iterations to expand the stage into. It is constructed by
``parse_workflow`` and carried verbatim inside ``WorkflowDocument``.

The model is intentionally declarative — it holds instructions, never their
resolution. ``agent`` is the raw agent name (the compiler composes the wrapper
path); ``prompt`` is verbatim text (the compiler places it in the description
slot); ``loop`` is a count (the compiler expands it). No validation lives here
either: ``parse_workflow`` enforces every invariant (key set, field types,
``loop >= 1``) and raises a structural error before this dataclass is built.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowStage:
    """A single per-stage override instruction from a workflow-file.

    All three fields default to ``None`` — a workflow-file may omit any of
    them, and ``parse_workflow`` produces ``None`` for missing fields. Field
    order is fixed (``agent``, ``prompt``, ``loop``) to match the canonical
    order of the per-stage keys in the workflow-file.

    Args:
        agent: Agent name consumed by the compiler to compose the per-stage
            command wrapper path, or ``None`` when not specified.
        prompt: Per-stage prompt text consumed by the compiler as the stage
            description field, or ``None`` when not specified.
        loop: Positive iteration count (>= 1) instructing the compiler to
            expand the stage into N copies, or ``None`` when not specified.
    """

    agent: str | None = None
    prompt: str | None = None
    loop: int | None = None
