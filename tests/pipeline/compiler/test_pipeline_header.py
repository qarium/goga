"""Contract and logic tests for the ``PipelineHeader`` dataclass."""

from __future__ import annotations

import dataclasses

import pytest
from goga.pipeline.compiler import PipelineAgents, PipelineHeader


class TestPipelineHeaderContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_pipeline_header_importable_from_facade(self) -> None:
        """PipelineHeader must be importable from the compiler facade."""
        assert PipelineHeader is not None

    def test_pipeline_header_field_order_keeps_agents_last(self) -> None:
        """Existing name/description fields are unchanged; agents is appended last."""
        field_names = [f.name for f in dataclasses.fields(PipelineHeader)]

        assert field_names == ["name", "description", "agents"]

    def test_pipeline_header_accepts_agents_field(self) -> None:
        """An agents override is carried verbatim under header.agents."""
        header = PipelineHeader(name="x", description="y", agents=PipelineAgents(planning="P"))

        assert header.agents is not None
        assert header.agents.planning == "P"

    def test_pipeline_header_agents_defaults_to_none(self) -> None:
        """When agents is omitted, header.agents is None (no agents block or empty)."""
        header = PipelineHeader(name="x", description="y")

        assert header.agents is None

    def test_pipeline_header_agents_accepts_none_explicit(self) -> None:
        """An explicit agents=None is accepted and stored as None."""
        header = PipelineHeader(name="x", description="y", agents=None)

        assert header.agents is None

    def test_existing_name_and_description_fields_unchanged(self) -> None:
        """The name and description fields keep their required, default-less semantics."""
        header = PipelineHeader(name="Goga feature", description="Feature implementation")

        assert header.name == "Goga feature"
        assert header.description == "Feature implementation"

        with pytest.raises(TypeError):
            PipelineHeader(description="d")  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            PipelineHeader(name="n")  # type: ignore[call-arg]

    def test_all_fields_are_kw_only(self) -> None:
        """Every field is keyword-only (no positional construction)."""
        with pytest.raises(TypeError):
            PipelineHeader("n", "d")  # type: ignore[misc]


class TestPipelineHeaderLogic:
    """Edge-case / behavior tests for the ``agents`` field."""

    def test_pipeline_header_agents_partial_override(self) -> None:
        """A partial agents override leaves the unspecified agent keys as None."""
        header = PipelineHeader(name="x", description="y", agents=PipelineAgents(planning="P"))

        assert header.agents is not None
        assert header.agents.planning == "P"
        assert header.agents.implementation is None
        assert header.agents.review is None
        assert header.agents.summary is None

    def test_pipeline_header_agents_full_override(self) -> None:
        """All four agent overrides are carried verbatim."""
        header = PipelineHeader(
            name="x",
            description="y",
            agents=PipelineAgents(
                planning="plan",
                implementation="impl",
                review="review",
                summary="summary",
            ),
        )

        assert header.agents is not None
        assert header.agents.planning == "plan"
        assert header.agents.implementation == "impl"
        assert header.agents.review == "review"
        assert header.agents.summary == "summary"

    def test_pipeline_header_agents_field_is_optional_with_default_none(self) -> None:
        """The agents field has a default value of None — it is optional."""
        agents_field = {f.name: f for f in dataclasses.fields(PipelineHeader)}["agents"]

        assert agents_field.default is None
