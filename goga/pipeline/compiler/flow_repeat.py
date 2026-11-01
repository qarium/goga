"""The ``FlowRepeat`` dataclass — the emitted top-level repeat directive of a flow-file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class FlowRepeat:
    """The emitted top-level repeat directive of a flow-file — the compiled run-cycle bounds.

    Built by :func:`compile_flow` for a repeatable pipeline; consumed by
    :func:`serialize_flow`. A directive carrying no authored key IS the scalar
    form — the serialization writes the short form and the engine applies its
    own defaults; this cell materializes no values and the engine owns every
    cycle semantic.

    Args:
        max_cycles: The authored maximum number of complete run cycles, or
            ``None`` when not authored. An authored ``0`` is a VALUE, never
            an omission.
        keep_runs: The authored number of recent cycle run-directories to
            retain, or ``None`` when not authored. An authored ``0`` is a
            VALUE, never an omission.
    """

    max_cycles: int | None = None
    keep_runs: int | None = None
