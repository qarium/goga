"""Contract tests for the ``FlowTeamMember`` dataclass.

Verifies the public API declared by the compiler-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the
five declared properties in the fixed emission order (``id``, ``title``,
``profile``, ``instruction``, ``skills``), the no-default pins of every field
(only ``compile_flow`` builds this type, always with materialized values),
and kw_only construction. These tests pin the contract surface — behavior
lives in the logic test module.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
from goga.pipeline.compiler import FlowTeamMember

from tests.conftest import is_kw_only_dataclass


class TestFlowTeamMemberContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_flow_team_member_importable_from_facade(self) -> None:
        """FlowTeamMember is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.compiler as facade

        assert facade.FlowTeamMember is FlowTeamMember
        assert "FlowTeamMember" in facade.__all__

    def test_flow_team_member_is_kw_only_dataclass(self) -> None:
        """Every field of FlowTeamMember is keyword-only."""
        assert is_kw_only_dataclass(FlowTeamMember)

    def test_flow_team_member_signature_matches_contract(self) -> None:
        """The signature matches the contract exactly — five required parameters.

        id, title, profile, instruction, skills in the declared order; every
        field carries NO default (a member is always complete — the emission
        materializes the instruction empty string and the skills empty list;
        only ``compile_flow`` builds this type).
        """
        parameters = list(inspect.signature(FlowTeamMember).parameters.values())
        empty = inspect.Parameter.empty

        assert [parameter.name for parameter in parameters] == [
            "id",
            "title",
            "profile",
            "instruction",
            "skills",
        ]
        assert [parameter.default for parameter in parameters] == [empty] * 5
        assert [parameter.annotation for parameter in parameters] == [
            "str",
            "str",
            "str",
            "str",
            "list[str]",
        ]

    def test_flow_team_member_field_order_fixed(self) -> None:
        """Field order is fixed — the emission order of the member keys."""
        names = [field.name for field in fields(FlowTeamMember)]

        assert names == ["id", "title", "profile", "instruction", "skills"]

    def test_flow_team_member_fields_all_required(self) -> None:
        """Constructing without any field raises TypeError — no silent defaults."""
        with pytest.raises(TypeError):
            FlowTeamMember()  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            FlowTeamMember(id="reviewer", title="reviewer", profile="goga-reviewer")  # type: ignore[call-arg]

    def test_flow_team_member_constructible_kw_only(self) -> None:
        """FlowTeamMember is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            FlowTeamMember("reviewer", "reviewer", "goga-reviewer", "Review.", [])  # type: ignore[misc]
