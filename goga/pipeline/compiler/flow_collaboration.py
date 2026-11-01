"""The ``FlowCollaboration`` dataclass — the emitted top-level collaboration block of a flow-file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class FlowCollaboration:
    """The emitted top-level collaboration block of a flow-file, fields in key-emission order.

    Args:
        mode: The dashboard collaboration mode — ``"assistants"`` in every
            emitted block (``compile_flow`` constructs the block on every
            compilation).
        max_depth: The authored delegation depth, or ``None`` when no depth
            is authored. ``None`` omits the key from the output entirely —
            the omission rule is ``is None``, never truthiness (an authored
            ``0`` is a value).
    """

    mode: str = "assistants"
    max_depth: int | None = None
