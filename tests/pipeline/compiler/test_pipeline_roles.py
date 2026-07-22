"""Contract and logic tests for the ``PipelineRoles`` dataclass."""

from __future__ import annotations

import dataclasses

import pytest
from goga.pipeline.compiler import PipelineRoles


class TestPipelineRolesContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_pipeline_roles_importable_from_facade(self) -> None:
        """PipelineRoles must be importable from the compiler facade."""
        assert PipelineRoles is not None

    def test_pipeline_roles_constructible_kw_only_no_args(self) -> None:
        """PipelineRoles is constructible with no arguments — every field defaults to None."""
        roles = PipelineRoles()

        assert roles.planner is None
        assert roles.executor is None
        assert roles.reviewer is None

    def test_pipeline_roles_field_order_is_fixed(self) -> None:
        """Field order is exactly planner, executor, reviewer (no summary)."""
        field_names = [f.name for f in dataclasses.fields(PipelineRoles)]

        assert field_names == ["planner", "executor", "reviewer"]

    def test_pipeline_roles_has_no_summary_field(self) -> None:
        """``summary`` is NOT a role — it must not be a field (separate always-default channel)."""
        field_names = {f.name for f in dataclasses.fields(PipelineRoles)}

        assert "summary" not in field_names

    @pytest.mark.parametrize("key", ["planner", "executor", "reviewer"])
    def test_each_field_settable_and_defaults_none(self, key: str) -> None:
        """Each field is settable via keyword and defaults to None when omitted."""
        default_roles = PipelineRoles()

        assert getattr(default_roles, key) is None

        override = PipelineRoles(**{key: f"override-{key}"})

        assert getattr(override, key) == f"override-{key}"

    def test_all_three_fields_settable_together(self) -> None:
        """All three fields can be set together."""
        roles = PipelineRoles(
            planner="plan",
            executor="impl",
            reviewer="review",
        )

        assert roles.planner == "plan"
        assert roles.executor == "impl"
        assert roles.reviewer == "review"

    def test_all_fields_are_kw_only(self) -> None:
        """Every field is keyword-only (no positional construction)."""
        with pytest.raises(TypeError):
            PipelineRoles("plan")  # type: ignore[misc]


class TestPipelineRolesLogic:
    """Edge-case / behavior tests."""

    def test_partial_override_leaves_others_none(self) -> None:
        """A partial override leaves the unspecified fields as None."""
        roles = PipelineRoles(planner="P")

        assert roles.planner == "P"
        assert roles.executor is None
        assert roles.reviewer is None

    def test_no_validation_no_merge_empty_string(self) -> None:
        """Empty-string prompt text passes through verbatim — no validation, no merging."""
        roles = PipelineRoles(planner="")

        assert roles.planner == ""

    def test_passes_through_multiline_text_verbatim(self) -> None:
        """Inline prompt text is carried verbatim, including newlines."""
        text = "Custom planning prompt.\nSecond line.\n"
        roles = PipelineRoles(planner=text)

        assert roles.planner == text
