"""The ``WorkflowRepeat`` dataclass — the workflow repeat-block run-cycle bounds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowRepeat:
    """The workflow repeat block — the authored bounds of a repeating run.

    Constructed by :func:`parse_workflow` from the optional top-level block;
    carried inside :class:`WorkflowDocument`. A directive carrying no
    authored key IS the scalar form — the model materializes no defaults and
    the engine owns the cycle semantics.

    Args:
        max_cycles: The maximum number of complete run cycles, or ``None``
            when not authored. An authored ``0`` is a VALUE, never an
            absence.
        keep_runs: The number of recent cycle run-directories to retain, or
            ``None`` when not authored. An authored ``0`` is a VALUE, never
            an absence.

    The model is pure data: no validation, no interpretation —
    :func:`parse_workflow` enforces the types and bounds during parsing, and
    the consumer and the engine interpret the bounds.
    """

    max_cycles: int | None = None
    keep_runs: int | None = None
