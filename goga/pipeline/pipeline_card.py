"""Value models for the single pipeline card."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class CardStage:
    """One stage row of a pipeline card.

    Args:
        id: identifier of the stage (``FlowStage.id``; loop copies carry the
            ``NAME-1..N`` identifiers produced by the compiler).
        title: display name of the compiled
            :class:`~goga.pipeline.compiler.FlowStage` (``FlowStage.name``).
    """

    id: str
    title: str


@dataclass(kw_only=True)
class PipelineCard:
    """The card of a single pipeline: author name, description, and stage rows.

    ``name`` and ``description`` are the author-facing values from the pipeline
    DSL header (they may differ from the discovered file stem). ``stages`` is
    the post-workflow composition in execution order — loop copies appear as
    separate rows — as produced by
    :func:`~goga.pipeline.order_stages.order_stages`. The order is part of the
    contract and is never re-sorted after construction.

    Args:
        name: author-facing pipeline name from the DSL header.
        description: author-facing pipeline description from the DSL header.
        stages: stage rows in execution order; may be empty.
    """

    name: str
    description: str
    stages: list[CardStage]
