"""The ``FlowVerify`` dataclass — the emitted stage completion gate of a flow-file."""

from __future__ import annotations

from dataclasses import dataclass

from .flow_verify_step import FlowVerifyStep


@dataclass(kw_only=True)
class FlowVerify:
    """The emitted stage completion gate — a stage's compiled check steps plus retry settings.

    Built by :func:`compile_flow` from a stage's authored check steps and,
    when the workflow-level settings block authored any key, the authored
    retry settings under the engine vocabulary; carried in the stage fields;
    consumed by :func:`serialize_flow`. An instance carrying no authored
    setting IS the list emission form — the serialization writes the steps
    alone; any authored setting switches to the container form. This cell
    materializes no settings defaults.

    Args:
        steps: The compiled check steps in authored order.
        max_failures: The authored iteration bound (from
            ``max_iterations``), or ``None`` when not authored. An authored
            ``0`` is a VALUE, never an omission.
        review_patience: The authored stalemate tolerance (from
            ``patience``), or ``None`` when not authored. An authored ``0``
            is a VALUE, never an omission.
        fresh_correction: The authored correction-session mode, or ``None``
            when not authored. An authored ``False`` is a VALUE, never an
            omission.
    """

    steps: list[FlowVerifyStep]
    max_failures: int | None = None
    review_patience: int | None = None
    fresh_correction: bool | None = None
