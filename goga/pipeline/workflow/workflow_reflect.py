"""The ``WorkflowReflect`` dataclass — one per-stage memory-reflection instruction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowReflect:
    """A single per-stage memory-reflection instruction from a workflow-file.

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
