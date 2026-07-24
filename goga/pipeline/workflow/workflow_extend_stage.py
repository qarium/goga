"""The ``WorkflowExtendStage`` dataclass — one extend-entry instruction.

A workflow-file's ``extend`` map carries one entry per new stage the workflow
wants to add to a target pipeline (as opposed to overriding an existing stage).
``WorkflowExtendStage`` is the parsed representation of a single such entry:
the stage names it should be positioned relative to (``before``/``after``), an
inline default ``agent``/``loop`` override, and the verbatim body of the new
stage. It is constructed by ``parse_workflow`` and carried verbatim inside
``WorkflowDocument`` (its ``extend`` field).

The model is intentionally declarative — it holds instructions, never their
resolution. ``before``/``after`` name existing stages (the compiler places the
new stage around them and derives ``depends_on``); ``agent``/``loop`` are
DEFAULT overrides (an explicit ``stages``-block entry for the same name wins
per-field); ``body`` is the verbatim stage content (the compiler embeds it).
No validation lives here either: ``parse_workflow`` enforces every invariant
(mapping shape, ``before``/``after`` as ``list[str]``, the
``depends_on``-forbidden rule, at-least-one-of before/after, inline
``agent``/``loop`` extraction) and raises a structural error before this
dataclass is built.

Field order is fixed — ``before``, ``after``, ``agent``, ``loop``, ``body`` —
to match the canonical order of the extend-entry keys in the workflow-file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(kw_only=True)
class WorkflowExtendStage:
    """A single extend-entry instruction from a workflow-file.

    ``before``, ``after``, ``agent``, and ``loop`` default to ``None`` — an
    extend-entry may omit any of them (``parse_workflow`` enforces that at
    least one of ``before``/``after`` is present before this dataclass is
    built). ``body`` is required — every extend-stage carries stage content.
    Field order is fixed (``before``, ``after``, ``agent``, ``loop``, ``body``)
    to match the canonical order of the extend-entry keys in the workflow-file.

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
        body: Verbatim copy of the stage body (``title``, ``prompt``,
            ``skills``, ``roles``, ``communication``, and any other stage field)
            excluding ``before``, ``after``, ``agent``, ``loop``, and
            ``depends_on``. Open-ended — this cell does not know the stage
            field schema.
    """

    before: list[str] | None = None
    after: list[str] | None = None
    agent: str | None = None
    loop: int | None = None
    body: dict[str, Any]
