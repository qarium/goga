"""Value models for the single pipeline card."""

from __future__ import annotations

from dataclasses import dataclass, field


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

    Args:
        name: author-facing pipeline name from the DSL header.
        description: author-facing pipeline description from the DSL header.
        stages: stage rows in execution order — the post-workflow composition
            with loop copies as separate rows; the order is part of the
            contract and is never re-sorted after construction; may be empty.
        provenance: tools whose contributions committed into the composition,
            in enumeration order; empty when none contributed.
    """

    name: str
    description: str
    stages: list[CardStage]
    provenance: list[str] = field(default_factory=list)
