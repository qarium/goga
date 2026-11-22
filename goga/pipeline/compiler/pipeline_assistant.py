"""The ``PipelineAssistant`` dataclass — one pipeline-file stage-declared helper."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class PipelineAssistant:
    """One pipeline-file stage-declared helper assistant.

    Declared inside the stage body's ``assistants`` map (both body formats);
    attaches to its own stage on every run — with a workflow-file or without
    one. Constructed by :func:`parse_dsl`; carried in the ``assistants``
    field of :class:`PhaseStep` and :class:`StageStep`. No delivery fields —
    ``agent``, ``env`` and ``delegate`` are workflow-file territory.

    Args:
        name: The assistant name — the map key of the declaration inside the
            stage body; :func:`parse_dsl` owns the vocabulary checks.
        prompt: The assistant's instruction text, or ``None`` when not
            authored.
        skills: List of the assistant's own skill names (delivered via the
            team member), or ``None`` when not authored — an authored empty
            list is a value, a declaration resolving content.
        when: When the assistant engages — one of ``"start"``,
            ``"checkpoints"``, ``"finish"``, ``"message"``. Required: no
            compiler-side engagement default exists.
        gate: Whether the assistant's verdict must pass before the stage may
            finish — materializes the advisory ``False`` when not authored.

    The model is pure data: no validation, no profile-id derivation —
    :func:`parse_dsl` enforces the vocabulary and :func:`compile_flow` owns
    the attachment and governance resolution.
    """

    name: str
    prompt: str | None = None
    skills: list[str] | None = None
    when: str
    gate: bool = False
