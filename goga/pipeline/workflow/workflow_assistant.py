"""The ``WorkflowAssistant`` dataclass — one assistant authoring entry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowAssistant:
    """One assistant authoring entry — a named helper declaration and its attachment parameters.

    One model serves the map-form entry kinds: a catalog declaration, a full
    inline stage declaration, a stage reference (with attachment parameters),
    and a skip veto over a pipeline-declared name. Constructed by
    :func:`parse_workflow`; carried inside :class:`WorkflowDocument` (the
    catalog) and :class:`WorkflowStage` (the attachments).

    Args:
        name: The assistant name — the map key of the entry on every
            authoring surface; matches ``[A-Za-z0-9._-]``; ``"assistant"``
            is rejected (:func:`parse_workflow` owns the grammar and the
            reserved name; uniqueness across the effective namespace — the
            catalog, every inline declaration, and the pipeline
            declarations of the compiled pipeline-file — is a compilation
            check owned by ``compile_flow``).
        prompt: The assistant's instruction text, or ``None`` when not
            authored.
        skills: List of the assistant's own skill names, or ``None`` when
            not authored — an authored empty list is an explicit override
            that clears, never normalized to absence.
        agent: Agent name the delivery resolves into the assistant's launch
            command, or ``None`` — ``None`` resolves to the effective global
            pipeline agent.
        delegate: Whether the assistant may create child tasks — ``None``
            when not authored (the value is inheritable: the overlay merge
            lets a delivered base supply it), ``False`` when explicitly
            authored off, ``True`` when authored on; downstream materializes
            ``False`` when the effective value stays ``None``.
        env: The assistant's environment instruction (string map, literal
            and/or rendered); ``None`` when not authored — an authored empty
            map is an explicit override that clears, never normalized to
            absence.
        gate: Whether the assistant's verdict must pass before the stage may
            finish — ``None`` when not authored (absence vs an authored
            ``False`` is the extension-inheritance distinction: an extension
            entry's absent gate inherits the declaration's gate, an authored
            ``False`` downgrades it). Authored only on a stage attachment;
            the catalog rejects the key.
        when: When the assistant engages — one of ``"start"``,
            ``"checkpoints"``, ``"finish"``, ``"message"``. ``"message"`` is
            the resting engagement: the engine sends no initial request, the
            helper waits for messages and stays attached after each answer.
            ``None`` when not authored; legal only where the origin check
            allows — the compile-time check owns that decision. Unknown in
            the catalog (the catalog rejects the key).
        skip: The veto carriage — ``None`` on every non-skip entry, ``True``
            on a ``{skip: true}`` entry addressing a pipeline-declared name
            of that stage (the compilation then drops the declaration's
            attachment, team member, and profile; the stage still runs).

    The model is pure data: no validation, no profile-id derivation, no env
    action — the consumers own resolution and delivery.
    """

    name: str
    prompt: str | None = None
    skills: list[str] | None = None
    agent: str | None = None
    delegate: bool | None = None
    env: dict[str, str] | None = None
    gate: bool | None = None
    when: str | None = None
    skip: bool | None = None
