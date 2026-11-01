"""The ``WorkflowDelegation`` dataclass — the workflow delegation-block bounds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowDelegation:
    """The workflow delegation block — the bounds of helper delegation for the run.

    Constructed by :func:`parse_workflow` from the optional top-level block
    with materialized defaults; carried inside :class:`WorkflowDocument`.

    Args:
        depth: The maximum delegation depth — an integer ``>= 0``, or
            ``None`` when not authored (no depth bound is delivered). An
            authored ``0`` is a VALUE, never an absence.
        max_tasks: The whole-run helper task budget; materialized ``50``
            whenever the block is authored, the authored value otherwise.

    The model is pure data: no validation, no channel decision —
    :func:`parse_workflow` enforces the types and bounds during parsing, and
    the consumers deliver ``depth`` into the flow and ``max_tasks`` into the
    engine configuration.
    """

    depth: int | None = None
    max_tasks: int = 50
