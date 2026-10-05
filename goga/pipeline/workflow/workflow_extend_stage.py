"""The ``WorkflowExtendStage`` dataclass — one extend-entry instruction (new-stage declaration)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(kw_only=True)
class WorkflowExtendStage:
    """A single extend-entry instruction from a workflow-file.

    Args:
        before: Names of stages the new stage precedes (the compiler adds
            this stage to the ``depends_on`` of each named stage), or ``None``
            when not specified.
        after: Names of stages the new stage follows (the compiler adds each
            named stage to this stage's ``depends_on``), or ``None`` when not
            specified.
        agent: Agent name the compiler composes into the new stage's command
            wrapper path — a DEFAULT override, so an explicit ``stages``-block
            entry for the same name wins (per-field) — or ``None`` when not
            specified.
        loop: Positive iteration count (>= 1) instructing the compiler to
            expand the new stage into N copies — a DEFAULT override, so an
            explicit ``stages``-block entry for the same name wins (per-field)
            — or ``None`` when not specified (no expansion).
        approve: Optional auto-approval directive (one of ``"auto"``/
            ``"plan"``/``"dialog"``, validated by ``parse_workflow``), extracted
            from the extend-entry into the model — exactly like
            ``agent``/``loop``. Acts as a DEFAULT override (an explicit
            ``stages``-block entry for the same name wins per-field); ``None``
            (the default) means no directive.
        body: Verbatim copy of the stage body (``title``, ``prompt``,
            ``skills``, ``roles``, ``communication``, and any other stage field)
            excluding ``before``, ``after``, ``agent``, ``loop``, ``approve``,
            and ``depends_on``. Open-ended — this cell does not know the stage
            field schema.
    """

    before: list[str] | None = None
    after: list[str] | None = None
    agent: str | None = None
    loop: int | None = None
    approve: str | None = None
    body: dict[str, Any]
