"""The ``WorkflowGateStep`` dataclass — one authored workflow check step."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowGateStep:
    """One authored check step — a single stage-completion check, shell or AI-review.

    Constructed by :func:`parse_workflow` from an entry of a stage's
    ``gates`` list; carried inside :class:`WorkflowStage`. Exactly one of
    ``script``/``agent`` is not ``None`` on every constructed instance —
    the parser enforces the exclusivity before construction — and ``prompt``
    is ``None`` on every shell instance (the parser-enforced
    prompt-on-script-step binding). The consumer composes ``agent`` into a
    launch command and materializes the shell-step timeout default; the
    engine owns the value grammars.

    Args:
        name: The check's dashboard label — required on every step.
        script: The shell command of a shell check step, or ``None``.
        agent: The agent name of an AI-review step, or ``None`` — the same
            name vocabulary as the per-stage agent override.
        timeout: The authored timeout value, carried verbatim, or ``None``
            when not authored.
        prompt: The review instruction of an AI step, carried verbatim, or
            ``None`` when not authored.

    The model is pure data: no validation, no interpretation —
    :func:`parse_workflow` enforces the step form during parsing, and the
    consumer and the engine interpret the values.
    """

    name: str
    script: str | None = None
    agent: str | None = None
    timeout: str | None = None
    prompt: str | None = None
