"""Contract and logic tests for the ``PipelineCard`` and ``CardStage`` Entities.

The pipeline cell's CODEMANIFEST declares two value models for the single
pipeline card: ``PipelineCard`` (the author-facing name and description from
the DSL header plus the ordered stage rows) and ``CardStage`` (one row:
the stage id and the display name of the compiled
:class:`~goga.pipeline.compiler.FlowStage`). Both are ``kw_only`` dataclasses
without ``__post_init__`` and without defaults — every field is required, and
an empty ``stages`` list is a legitimate value. The ``stages`` order is part of
the contract: it is the execution order produced by
:func:`~goga.pipeline.order_stages.order_stages`, and nobody re-sorts it
afterwards.

Contract tests pin the surface (fields, required construction). Logic tests
cover dataclass equality of the stage rows and the preserved order.
"""

from __future__ import annotations

import pytest
from goga.pipeline.pipeline_card import CardStage, PipelineCard


class TestCardStageContract:
    def test_card_stage_constructs_with_keyword_arguments(self) -> None:
        """CardStage builds from kwargs and exposes id and title."""
        stage = CardStage(id="build", title="Build")

        assert stage.id == "build"
        assert stage.title == "Build"

    def test_card_stage_exposes_declared_field_names(self) -> None:
        """The dataclass declares exactly id and title."""
        fields = {f.name for f in CardStage.__dataclass_fields__.values()}

        assert fields == {"id", "title"}

    def test_card_stage_rejects_positional_arguments(self) -> None:
        """kw_only is enforced: positional construction is rejected."""
        with pytest.raises(TypeError):
            CardStage("build", "Build")

    def test_card_stage_requires_both_fields(self) -> None:
        """There are no defaults: omitting a field is a TypeError."""
        with pytest.raises(TypeError):
            CardStage(id="build")  # type: ignore[call-arg]


class TestPipelineCardContract:
    def test_pipeline_card_constructs_with_keyword_arguments(self) -> None:
        """PipelineCard builds from kwargs and exposes name, description, stages."""
        card = PipelineCard(
            name="Deploy",
            description="Deploy the service",
            stages=[CardStage(id="build", title="Build")],
        )

        assert card.name == "Deploy"
        assert card.description == "Deploy the service"
        assert card.stages == [CardStage(id="build", title="Build")]

    def test_pipeline_card_exposes_declared_field_names(self) -> None:
        """The dataclass declares exactly name, description, and stages."""
        fields = {f.name for f in PipelineCard.__dataclass_fields__.values()}

        assert fields == {"name", "description", "stages"}


class TestPipelineCardLogic:
    def test_pipeline_card_and_card_stage_hold_stage_rows(self) -> None:
        """Stage rows compare by dataclass equality and keep the given order."""
        card = PipelineCard(
            name="Deploy",
            description="Deploy the service",
            stages=[CardStage(id="build", title="Build"), CardStage(id="test", title="Test")],
        )

        assert card.stages == [CardStage(id="build", title="Build"), CardStage(id="test", title="Test")]
        assert [stage.id for stage in card.stages] == ["build", "test"]

    def test_pipeline_card_accepts_empty_stages(self) -> None:
        """An empty stages list is a valid card and does not raise."""
        card = PipelineCard(name="Deploy", description="Deploy the service", stages=[])

        assert card.stages == []

    def test_pipeline_card_preserves_stage_order_as_given(self) -> None:
        """The card never re-sorts: the passed order is the contract."""
        stages = [CardStage(id="test", title="Test"), CardStage(id="build", title="Build")]
        card = PipelineCard(name="Deploy", description="Deploy the service", stages=stages)

        assert [stage.id for stage in card.stages] == ["test", "build"]
