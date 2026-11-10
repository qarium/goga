"""The ``WorkflowGates`` dataclass — the workflow quality-gate settings block."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowGates:
    """The workflow gates settings block — the authored retry tuning for stage-completion checks.

    Constructed by :func:`parse_workflow` from the optional top-level block;
    carried inside :class:`WorkflowDocument`. A block carrying no authored
    key IS absence — the parser normalizes an empty block to ``None`` and the
    model materializes no defaults; the consumer translates the field names
    into the engine vocabulary and the engine owns the retry semantics.

    Args:
        patience: The authored tolerance for an unchanged correction
            stalemate, or ``None`` when not authored. An authored ``0`` is a
            VALUE, never an absence.
        max_iterations: The authored bound of failed correction attempts, or
            ``None`` when not authored. An authored ``0`` is a VALUE, never
            an absence.
        fresh_correction: Whether a correction session starts fresh, or
            ``None`` when not authored.

    The model is pure data: no validation, no interpretation —
    :func:`parse_workflow` enforces the types and bounds during parsing, and
    the consumer and the engine interpret the settings.
    """

    patience: int | None = None
    max_iterations: int | None = None
    fresh_correction: bool | None = None
