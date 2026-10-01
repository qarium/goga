"""Facade contract tests for the ``goga.pipeline`` package.

The pipeline cell's CODEMANIFEST declares fourteen facade names: the six
pre-existing entities/routines (``PipelineEntry``, ``PipelineSource``,
``apply_skip_stages``, ``list_pipelines``, ``pipeline_cli``,
``run_pipeline``), the seven informational-surface names built by the
``pipeline-info`` plan (``CardStage``, ``PipelineCard``,
``PipelineSummary``, ``describe_pipeline``, ``describe_pipelines``,
``order_stages``, ``resolve_workflow``), and the in-container afm
configuration authorship routine (``write_afm_config``) added by the
``fix-pipeline-context`` topic. Per the language rule recorded in the
plan's Re-exports section, only identifiers listed in ``__all__``
constitute the facade — a name importable by accident but absent from
``__all__`` is not part of the contract surface.
"""

from __future__ import annotations

import goga.pipeline as pipeline_facade

NEW_FACADE_NAMES = (
    "PipelineSummary",
    "PipelineCard",
    "CardStage",
    "describe_pipelines",
    "resolve_workflow",
    "order_stages",
    "describe_pipeline",
)


class TestPipelineFacade:
    def test_facade_exports_new_names(self) -> None:
        """Every informational-surface name is defined on the package and in __all__."""
        for name in NEW_FACADE_NAMES:
            assert hasattr(pipeline_facade, name), f"{name} is not defined on goga.pipeline"
            assert name in pipeline_facade.__all__, f"{name} is missing from goga.pipeline.__all__"

    def test_facade_all_is_alphabetical(self) -> None:
        """__all__ keeps the alphabetical ordering convention (uppercase first)."""
        assert pipeline_facade.__all__ == sorted(pipeline_facade.__all__)

    def test_facade_all_has_fourteen_names(self) -> None:
        """Six pre-existing names plus seven new ones plus write_afm_config."""
        assert len(pipeline_facade.__all__) == 14
        assert "write_afm_config" in pipeline_facade.__all__

    def test_facade_preserves_pre_existing_names(self) -> None:
        """The six names exported before the pipeline-info work stay exported."""
        for name in (
            "PipelineEntry",
            "PipelineSource",
            "apply_skip_stages",
            "list_pipelines",
            "pipeline_cli",
            "run_pipeline",
        ):
            assert name in pipeline_facade.__all__
            assert hasattr(pipeline_facade, name)

    def test_facade_names_are_the_declared_modules_symbols(self) -> None:
        """The facade re-exports the declaring modules' objects, not copies."""
        from goga.pipeline.describe_pipeline import describe_pipeline
        from goga.pipeline.describe_pipelines import describe_pipelines
        from goga.pipeline.order_stages import order_stages
        from goga.pipeline.pipeline_card import CardStage, PipelineCard
        from goga.pipeline.pipeline_summary import PipelineSummary
        from goga.pipeline.resolve_workflow import resolve_workflow

        assert pipeline_facade.PipelineSummary is PipelineSummary
        assert pipeline_facade.PipelineCard is PipelineCard
        assert pipeline_facade.CardStage is CardStage
        assert pipeline_facade.describe_pipelines is describe_pipelines
        assert pipeline_facade.resolve_workflow is resolve_workflow
        assert pipeline_facade.order_stages is order_stages
        assert pipeline_facade.describe_pipeline is describe_pipeline
