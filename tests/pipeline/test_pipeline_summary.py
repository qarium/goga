"""Contract and logic tests for the ``PipelineSummary`` Entity.

The pipeline cell's CODEMANIFEST declares a value model ``PipelineSummary``
that carries one row of the pipeline overview: the discovered name stem, the
:class:`~goga.pipeline.pipeline_entry.PipelineSource` it was found in, and the
description from the pipeline DSL header. It is a ``kw_only`` dataclass whose
``__post_init__`` mirrors the ``PipelineEntry`` name validation verbatim (the
same three checks, the same three messages).

Contract tests pin the surface (construction with keyword arguments, the
``name``/``source``/``description`` fields). Logic tests cover the mirrored
validation and the ``kw_only`` enforcement.
"""

from __future__ import annotations

import pytest
from goga.pipeline.pipeline_entry import PipelineSource
from goga.pipeline.pipeline_summary import PipelineSummary


class TestPipelineSummaryContract:
    def test_pipeline_summary_constructs_with_keyword_arguments(self) -> None:
        """PipelineSummary builds from kwargs and exposes its three fields."""
        summary = PipelineSummary(name="deploy", source=PipelineSource.PROJECT, description="Deploy the service")

        assert summary.name == "deploy"
        assert summary.source is PipelineSource.PROJECT
        assert summary.description == "Deploy the service"

    def test_pipeline_summary_exposes_declared_field_names(self) -> None:
        """The dataclass declares exactly name, source, description, and display_name."""
        fields = {f.name for f in PipelineSummary.__dataclass_fields__.values()}

        assert fields == {"name", "source", "description", "display_name"}


class TestPipelineSummaryLogic:
    def test_pipeline_summary_constructs_with_kw_only_fields(self) -> None:
        """A well-formed summary round-trips all keyword arguments."""
        summary = PipelineSummary(name="deploy", source=PipelineSource.PROJECT, description="Deploy the service")

        assert summary.name == "deploy"
        assert summary.source is PipelineSource.PROJECT
        assert summary.description == "Deploy the service"

    def test_pipeline_summary_display_name_defaults_to_empty_string(self) -> None:
        """The authored header name is optional — omitted constructions default to an empty string."""
        summary = PipelineSummary(name="deploy", source=PipelineSource.PROJECT, description="Deploy the service")

        assert summary.display_name == ""

    def test_pipeline_summary_round_trips_display_name(self) -> None:
        """A well-formed summary round-trips the authored header name."""
        summary = PipelineSummary(
            name="deploy", source=PipelineSource.PROJECT, description="Deploy the service", display_name="Deploy"
        )

        assert summary.display_name == "Deploy"

    def test_pipeline_summary_rejects_positional_arguments(self) -> None:
        """kw_only is enforced: positional construction is rejected."""
        with pytest.raises(TypeError):
            PipelineSummary("deploy", PipelineSource.PROJECT, "d")

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "a/b",
            "a\\b",
            "deploy.yml",
        ],
    )
    def test_pipeline_summary_rejects_invalid_names(self, name: str) -> None:
        """The PipelineEntry name rules are mirrored verbatim."""
        with pytest.raises(ValueError, match="pipeline name"):
            PipelineSummary(name=name, source=PipelineSource.PROJECT, description="d")

    def test_pipeline_summary_empty_description_is_allowed(self) -> None:
        """An empty description is a valid overview row (no falsy filter)."""
        summary = PipelineSummary(name="deploy", source=PipelineSource.USER, description="")

        assert summary.description == ""

    def test_pipeline_summary_error_messages_match_pipeline_entry(self) -> None:
        """The three mirrored messages are byte-identical to PipelineEntry."""
        with pytest.raises(ValueError, match=r"^pipeline name must not be empty$"):
            PipelineSummary(name="", source=PipelineSource.PROJECT, description="d")

        with pytest.raises(ValueError, match=r"^pipeline name must not contain path separators \('/' or '\\'\)$"):
            PipelineSummary(name="a/b", source=PipelineSource.PROJECT, description="d")

        with pytest.raises(ValueError, match=r"^pipeline name must not include the '\.yml' extension$"):
            PipelineSummary(name="deploy.yml", source=PipelineSource.PROJECT, description="d")
