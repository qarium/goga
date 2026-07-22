"""Contract and logic tests for the ``PipelineHeader`` dataclass."""

from __future__ import annotations

import dataclasses

import pytest
from goga.pipeline.compiler import PipelineHeader, PipelineRoles


class TestPipelineHeaderContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_pipeline_header_importable_from_facade(self) -> None:
        """PipelineHeader must be importable from the compiler facade."""
        assert PipelineHeader is not None

    def test_pipeline_header_field_order_keeps_roles_last(self) -> None:
        """Existing name/description fields are unchanged; roles is appended last."""
        field_names = [f.name for f in dataclasses.fields(PipelineHeader)]

        assert field_names == ["name", "description", "roles"]

    def test_pipeline_header_accepts_roles_field(self) -> None:
        """A roles override is carried verbatim under header.roles."""
        header = PipelineHeader(name="x", description="y", roles=PipelineRoles(planner="P"))

        assert header.roles is not None
        assert header.roles.planner == "P"

    def test_pipeline_header_roles_defaults_to_none(self) -> None:
        """When roles is omitted, header.roles is None (no roles block or empty)."""
        header = PipelineHeader(name="x", description="y")

        assert header.roles is None

    def test_pipeline_header_roles_accepts_none_explicit(self) -> None:
        """An explicit roles=None is accepted and stored as None."""
        header = PipelineHeader(name="x", description="y", roles=None)

        assert header.roles is None

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
    """Edge-case / behavior tests for the ``roles`` field."""

    def test_pipeline_header_roles_partial_override(self) -> None:
        """A partial roles override leaves the unspecified role keys as None."""
        header = PipelineHeader(name="x", description="y", roles=PipelineRoles(planner="P"))

        assert header.roles is not None
        assert header.roles.planner == "P"
        assert header.roles.executor is None
        assert header.roles.reviewer is None

    def test_pipeline_header_roles_full_override(self) -> None:
        """All three role overrides are carried verbatim."""
        header = PipelineHeader(
            name="x",
            description="y",
            roles=PipelineRoles(
                planner="plan",
                executor="impl",
                reviewer="review",
            ),
        )

        assert header.roles is not None
        assert header.roles.planner == "plan"
        assert header.roles.executor == "impl"
        assert header.roles.reviewer == "review"

    def test_pipeline_header_roles_field_is_optional_with_default_none(self) -> None:
        """The roles field has a default value of None — it is optional."""
        roles_field = {f.name: f for f in dataclasses.fields(PipelineHeader)}["roles"]

        assert roles_field.default is None
