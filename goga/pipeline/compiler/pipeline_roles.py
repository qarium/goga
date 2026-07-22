"""The ``PipelineRoles`` dataclass — data model of the header-level ``roles`` directive.

A goga DSL pipeline-file header may carry an optional ``roles`` block with three
fixed keys (planner, executor, reviewer). Each value is inline prompt text that
fully replaces (not merges with) the corresponding default prompt file during
pipeline-run materialization; the role alias is translated to its afm agent
name / prompt-file stem via ``translate_role`` (planner→planning,
executor→implementation, reviewer→review). ``summary`` is NOT an overridable
role — it is a separate, always-default channel. ``PipelineRoles`` is the data
model of that block — three optional string overrides, one per fixed role key.

``parse_dsl`` constructs this dataclass when the header segment contains a
non-empty ``roles`` block; it is carried verbatim inside ``PipelineHeader``
(its ``roles`` field) and surfaced to the consumer through
``PipelineDocument``. The dataclass performs no validation and no merging of
the prompt text — it is a pure passive carrier (per ``convention`` and the
cell's verbatim pass-through constraint).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class PipelineRoles:
    """Data model of the header-level ``roles`` directive — three optional inline prompt overrides.

    Each field is inline prompt text that overrides the corresponding default
    prompt file (``goga/assets/afm/prompts/<stem>.md``, stem resolved via
    ``translate_role``: planner→planning, executor→implementation,
    reviewer→review) during pipeline-run materialization, or ``None`` when not
    specified. The three fields are passed through verbatim to the consumer
    (``run_pipeline`` writes them unchanged to the prompt file); no merging or
    validation is performed.

    Args:
        planner: Inline prompt text overriding ``planning.md``, or None.
        executor: Inline prompt text overriding ``implementation.md``, or None.
        reviewer: Inline prompt text overriding ``review.md``, or None.
    """

    planner: str | None = None
    executor: str | None = None
    reviewer: str | None = None
