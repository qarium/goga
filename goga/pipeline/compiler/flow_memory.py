"""The ``FlowMemory`` dataclass — the emitted top-level memory block of a flow-file.

A flow-file may carry a top-level ``memory`` block between ``description`` and
``stages``. ``FlowMemory`` is the compiled form of the workflow-memory
configuration: it is built by ``compile_flow`` when memory participates and
consumed by ``serialize_flow``. The model is intentionally declarative — it
holds the emitted values, never their resolution.

The field order IS the emission order of the block keys — ``path``, ``mode``,
``memory_use``, ``max_rules``, ``commit``. ``path`` is the composed memory
root: the fixed root joined with the authored suffix (the bare root when no
suffix was authored) — the caller composes it, this model never does.
``mode`` is the project-memory access mode; it is present only for the
alignment method (``None`` for the reflect method). ``memory_use`` is the
global participation default; ``True`` only for the alignment method
(``None`` for the reflect method). ``max_rules`` is the maximum number of
memory rules (always ``>= 1``); ``commit`` is whether memory changes are
committed. A ``None`` field is omitted from the output entirely — the
serializer drops it, it never emits an empty value.

Only ``mode`` / ``memory_use`` default (to ``None``); ``path`` / ``max_rules``
/ ``commit`` carry NO defaults — a block is always complete, and
``compile_flow`` is its single construction site.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class FlowMemory:
    """The emitted top-level memory block of a flow-file.

    Field order is fixed (``path``, ``mode``, ``memory_use``, ``max_rules``,
    ``commit``) — the emission order of the block keys. reflect method —
    ``mode`` ``None``, ``memory_use`` ``None``; alignment method — ``mode``
    the materialized value, ``memory_use`` ``True``. A ``None`` field is
    omitted from the output entirely.

    Args:
        path: The composed memory root — the fixed root joined with the
            authored suffix. Composed by ``compile_flow``; carried verbatim
            here.
        mode: The project-memory access mode; present only for the alignment
            method.
        memory_use: The global participation default; ``True`` only for the
            alignment method.
        max_rules: The maximum number of memory rules; always ``>= 1``.
        commit: Whether memory changes are committed.
    """

    path: str
    mode: str | None = None
    memory_use: bool | None = None
    max_rules: int
    commit: bool
