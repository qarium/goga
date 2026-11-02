"""The ``WorkflowAssistant`` dataclass — one assistant authoring entry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowAssistant:
    """One assistant authoring entry — a named helper declaration and its attachment parameters.

    One model serves the map-form entry kinds: a catalog declaration, a full
    inline stage declaration, and a stage reference (with attachment
    parameters). Constructed by :func:`parse_workflow`; carried inside
    :class:`WorkflowDocument` (the catalog) and :class:`WorkflowStage` (the
    attachments).

    Args:
        name: The assistant name — the map key of the entry on both
            authoring surfaces; matches ``[A-Za-z0-9._-]``; ``"assistant"``
            is rejected; unique across the catalog and every inline
            declaration of one workflow-file (:func:`parse_workflow` owns
            the grammar, the reserved name, and the uniqueness checks).
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
            finish; materialized ``False`` (advisory) when not authored.
            Authored only on a stage attachment; the catalog rejects the key.
        when: When the assistant engages — one of ``"start"``,
            ``"checkpoints"``, ``"finish"``. Authored on every stage
            attachment (a missing ``when`` is a structural error); unknown
            in the catalog (the catalog rejects the key). The model default
            serves the construction paths that carry no attachment
            authoring.

    The model is pure data: no validation, no profile-id derivation, no env
    action — the consumers own resolution and delivery.
    """

    name: str
    prompt: str | None = None
    skills: list[str] | None = None
    agent: str | None = None
    delegate: bool | None = None
    env: dict[str, str] | None = None
    gate: bool = False
    when: str = "checkpoints"
