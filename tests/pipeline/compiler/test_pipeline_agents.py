"""Contract and logic tests for the ``PipelineAgents`` dataclass."""

from __future__ import annotations

import dataclasses

import pytest
from goga.pipeline.compiler import PipelineAgents


class TestPipelineAgentsContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_pipeline_agents_importable_from_facade(self) -> None:
        """PipelineAgents must be importable from the compiler facade."""
        assert PipelineAgents is not None

    def test_pipeline_agents_constructible_kw_only_no_args(self) -> None:
        """PipelineAgents is constructible with no arguments — every field defaults to None."""
        agents = PipelineAgents()

        assert agents.planning is None
        assert agents.implementation is None
        assert agents.review is None
        assert agents.summary is None

    def test_pipeline_agents_field_order_is_fixed(self) -> None:
        """Field order is exactly planning, implementation, review, summary."""
        field_names = [f.name for f in dataclasses.fields(PipelineAgents)]

        assert field_names == ["planning", "implementation", "review", "summary"]

    @pytest.mark.parametrize("key", ["planning", "implementation", "review", "summary"])
    def test_each_field_settable_and_defaults_none(self, key: str) -> None:
        """Each field is settable via keyword and defaults to None when omitted."""
        default_agents = PipelineAgents()

        assert getattr(default_agents, key) is None

        override = PipelineAgents(**{key: f"override-{key}"})

        assert getattr(override, key) == f"override-{key}"

    def test_all_four_fields_settable_together(self) -> None:
        """All four fields can be set together."""
        agents = PipelineAgents(
            planning="plan",
            implementation="impl",
            review="review",
            summary="summary",
        )

        assert agents.planning == "plan"
        assert agents.implementation == "impl"
        assert agents.review == "review"
        assert agents.summary == "summary"

    def test_all_fields_are_kw_only(self) -> None:
        """Every field is keyword-only (no positional construction)."""
        with pytest.raises(TypeError):
            PipelineAgents("plan")  # type: ignore[misc]


class TestPipelineAgentsLogic:
    """Edge-case / behavior tests."""

    def test_partial_override_leaves_others_none(self) -> None:
        """A partial override leaves the unspecified fields as None."""
        agents = PipelineAgents(planning="P")

        assert agents.planning == "P"
        assert agents.implementation is None
        assert agents.review is None
        assert agents.summary is None

    def test_no_validation_no_merge_empty_string(self) -> None:
        """Empty-string prompt text passes through verbatim — no validation, no merging."""
        agents = PipelineAgents(planning="")

        assert agents.planning == ""

    def test_passes_through_multiline_text_verbatim(self) -> None:
        """Inline prompt text is carried verbatim, including newlines."""
        text = "Custom planning prompt.\nSecond line.\n"
        agents = PipelineAgents(planning=text)

        assert agents.planning == text
