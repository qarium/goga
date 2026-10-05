"""The ``FlowMemory`` dataclass — the emitted top-level memory block of a flow-file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class FlowMemory:
    """The emitted top-level memory block of a flow-file, fields in key-emission order; ``None`` fields are omitted.

    Args:
        path: The composed memory root — the fixed root joined with the
            authored suffix. Composed by ``compile_flow``; carried verbatim
            here.
        mode: The project-memory access mode — ``"r"`` for the reflect method,
            the materialized authored value for the alignment method.
        memory_use: The global participation default; ``False`` in every
            emitted block (participation is per-stage opt-in).
        max_rules: The maximum number of memory rules; always ``>= 1``.
        commit: Whether memory changes are committed.
    """

    path: str
    mode: str | None = None
    memory_use: bool | None = None
    max_rules: int
    commit: bool
