"""The ``WorkflowMemory`` dataclass — the workflow-memory configuration block.

A workflow-file may carry a top-level ``memory`` block — the authoring form of
the flow-level memory settings. ``WorkflowMemory`` is the parsed representation
of that block. It is constructed by ``parse_workflow`` with materialized
defaults and carried verbatim inside ``WorkflowDocument``.

The model is intentionally declarative — it holds the configuration, never
its resolution. ``method`` is the authoring method — ``"reflect"`` or
``"alignment"``: a goga-side selector of the instruction vocabulary, never
part of any output (the consumer selects the emission form). ``path`` is the
authored suffix inside the fixed memory root (``None`` means no suffix) — the
fixed root prefix is NOT part of this model; the consumer composes the final
path. ``max_rules`` is the maximum number of memory rules (always ``>= 1``).
``commit`` is whether memory changes are committed. ``mode`` is the
project-memory access mode — one of ``"r"``, ``"w"``, ``"rw"``; it exists only
for the ``"alignment"`` method (``None`` for ``"reflect"``). No validation
lives here either: ``parse_workflow`` enforces every invariant (the block key
set, field types, value domains, path shapes, the mode-only-under-alignment
rule) and raises a structural error before this dataclass is built.

The field defaults ARE the materialized authoring defaults — the consumer
default-constructs ``WorkflowMemory()`` when the workflow carries no block,
sourcing ``max_rules`` / ``commit`` (and the default method) from them.

Field order is fixed — ``method``, ``path``, ``max_rules``, ``commit``,
``mode`` — matching the canonical order of the block keys in the
workflow-file.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowMemory:
    """The workflow-memory configuration extracted from a workflow-file's ``memory`` block.

    Every field carries a materialized default — defaults are values, not
    omissions: ``method`` ``"reflect"``, ``path`` ``None``, ``max_rules``
    ``25``, ``commit`` ``False``, ``mode`` ``None`` for the ``"reflect"``
    method (``"rw"`` for ``"alignment"`` once ``parse_workflow`` materializes
    it). Field order is fixed (``method``, ``path``, ``max_rules``,
    ``commit``, ``mode``) to match the canonical order of the block keys in
    the workflow-file.

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
