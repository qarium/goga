"""The ``WorkflowReflect`` dataclass — one per-stage memory-reflection instruction.

A workflow-file's ``stages`` map may carry a ``reflect`` entry per stage — the
memory-reflection instruction. ``WorkflowReflect`` is the parsed representation
of a single such entry: which memory file the stage reflects into (``file``)
and with which access mode (``mode``). It is constructed by ``parse_workflow``
and carried verbatim inside ``WorkflowStage``.

The model is intentionally declarative — it holds the instruction, never its
resolution. ``file`` is the reflection file — a path shape inside the memory
root, carried verbatim (the compiler emits it into the stage's ``reflect``
field; the consumer composes paths). ``mode`` is the access mode — one of
``"r"``, ``"w"``, ``"rw"``, materialized to ``"rw"`` when the authoring entry
omits it. No validation lives here either: ``parse_workflow`` enforces every
invariant (the ``{file, mode}`` key set, ``file`` required and a valid path
shape, the ``mode`` domain) and raises a structural error before this
dataclass is built. This cell does not resolve ``file`` against any memory
root — the consumer composes the final path.

Field order is fixed — ``file``, ``mode`` — matching the canonical order of
the reflect-instruction keys in the workflow-file.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowReflect:
    """A single per-stage memory-reflection instruction from a workflow-file.

    ``file`` is required — every reflect instruction names a reflection file.
    ``mode`` defaults to ``"rw"`` — a materialized value, not an omission, so
    a consumer reading the model never distinguishes an authored ``rw`` from
    an omitted mode. Field order is fixed (``file``, ``mode``) to match the
    canonical order of the reflect-instruction keys in the workflow-file.

    Args:
        file: The reflection file — a path shape inside the memory root;
            carried verbatim. Required (no default); ``parse_workflow``
            enforces the path shape before this dataclass is built.
        mode: The access mode — one of ``"r"``, ``"w"``, ``"rw"``;
            materialized to ``"rw"`` when the authoring entry omits it. This
            cell does not validate the mode domain — ``parse_workflow``
            enforces it during parsing.
    """

    file: str
    mode: str = "rw"
