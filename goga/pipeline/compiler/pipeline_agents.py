"""The ``PipelineAgents`` dataclass — data model of the header-level ``agents`` directive.

A goga DSL pipeline-file header may carry an optional ``agents`` block with four
fixed keys (planning, implementation, review, summary). Each value is inline
prompt text that fully replaces (not merges with) the corresponding default
prompt file during pipeline-run materialization. ``PipelineAgents`` is the data
model of that block — four optional string overrides, one per fixed agent key.

``parse_dsl`` constructs this dataclass when the header segment contains a
non-empty ``agents`` block; it is carried verbatim inside ``PipelineHeader``
(its ``agents`` field) and surfaced to the consumer through
``PipelineDocument``. The dataclass performs no validation and no merging of
the prompt text — it is a pure passive carrier (per ``convention`` and the
cell's verbatim pass-through constraint).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class PipelineAgents:
    """Data model of the header-level ``agents`` directive — four optional inline prompt overrides.

    Each field is inline prompt text that overrides the corresponding default
    prompt file (``goga/assets/afm/prompts/<key>.md``) during pipeline-run
    materialization, or ``None`` when not specified. The four fields are
    passed through verbatim to the consumer (``run_pipeline`` writes them
    unchanged to the prompt file); no merging or validation is performed.

    Args:
        planning: Inline prompt text overriding ``planning.md``, or None.
        implementation: Inline prompt text overriding ``implementation.md``,
            or None.
        review: Inline prompt text overriding ``review.md``, or None.
        summary: Inline prompt text overriding ``summary.md``, or None.
    """

    planning: str | None = None
    implementation: str | None = None
    review: str | None = None
    summary: str | None = None
