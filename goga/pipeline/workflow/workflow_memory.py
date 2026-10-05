"""The ``WorkflowMemory`` dataclass — the declarative workflow-memory configuration block."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowMemory:
    """The workflow-memory configuration extracted from a workflow-file's ``memory`` block.

    Args:
        method: The authoring method — ``"reflect"`` or ``"alignment"``. A
            goga-side selector of the instruction vocabulary; never part of
            any output. This cell does not act on ``method`` — it is
            declarative; the consumer selects the emission form.
        path: Authored suffix inside the fixed memory root; ``None`` means no
            suffix. Carries the authored suffix only — the fixed root prefix
            is not part of this model; the consumer composes the final path.
        max_rules: The maximum number of memory rules; always ``>= 1``.
            ``parse_workflow`` enforces the bound during parsing.
        commit: Whether memory changes are committed.
        mode: The project-memory access mode — one of ``"r"``, ``"w"``,
            ``"rw"``; exists only for the ``"alignment"`` method, ``None``
            for ``"reflect"``. ``parse_workflow`` enforces the domain (and
            forbids ``mode`` under ``"reflect"``) during parsing.
    """

    method: str = "reflect"
    path: str | None = None
    max_rules: int = 25
    commit: bool = False
    mode: str | None = None
