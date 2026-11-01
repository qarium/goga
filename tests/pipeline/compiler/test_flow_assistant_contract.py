"""Contract tests for the ``FlowAssistant`` dataclass.

Verifies the public API declared by the compiler-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the
five declared properties in the fixed emission order (``profile``, ``title``,
``instruction``, ``mode``, ``trigger``), the no-default pins of every field
(the emission materializes every default — the checkpoints trigger is written
explicitly, never inherited from the engine default), the absence of a
``skills`` field (the engine strict-parses stage entries and rejects unknown
fields), and kw_only construction. These tests pin the contract surface —
behavior lives in the logic test module.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
from goga.pipeline.compiler import FlowAssistant

from tests.conftest import is_kw_only_dataclass


class TestFlowAssistantContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_flow_assistant_importable_from_facade(self) -> None:
        """FlowAssistant is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.compiler as facade

        assert facade.FlowAssistant is FlowAssistant
        assert "FlowAssistant" in facade.__all__

    def test_flow_assistant_is_kw_only_dataclass(self) -> None:
        """Every field of FlowAssistant is keyword-only."""
        assert is_kw_only_dataclass(FlowAssistant)

    def test_flow_assistant_signature_matches_contract(self) -> None:
        """The signature matches the contract exactly — five required parameters.

        profile, title, instruction, mode, trigger in the declared order;
        every field carries NO default (an entry is always complete — the
        emission materializes the instruction empty string and the
        advisory/checkpoints defaults; only ``compile_flow`` builds this
        type). No ``skills`` parameter — the engine strict-parses
        ``stages[].assistants`` entries and rejects unknown fields; an
        assistant's skills travel on its ``FlowTeamMember`` entry.
        """
        parameters = list(inspect.signature(FlowAssistant).parameters.values())
        empty = inspect.Parameter.empty

        assert [parameter.name for parameter in parameters] == [
            "profile",
            "title",
            "instruction",
            "mode",
            "trigger",
        ]
        assert [parameter.default for parameter in parameters] == [empty] * 5
        assert [parameter.annotation for parameter in parameters] == [
            "str",
            "str",
            "str",
            "str",
            "str",
        ]

    def test_flow_assistant_field_order_fixed(self) -> None:
        """Field order is fixed — the emission order of the entry keys."""
        names = [field.name for field in fields(FlowAssistant)]

        assert names == ["profile", "title", "instruction", "mode", "trigger"]

    def test_flow_assistant_carries_no_skills_field(self) -> None:
        """The model has no ``skills`` field — the engine rejects it on stage entries."""
        assert "skills" not in {field.name for field in fields(FlowAssistant)}

    def test_flow_assistant_fields_all_required(self) -> None:
        """Constructing without any field raises TypeError — no silent defaults."""
        with pytest.raises(TypeError):
            FlowAssistant()  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            FlowAssistant(profile="goga-reviewer", title="reviewer", instruction="Review.")  # type: ignore[call-arg]

    def test_flow_assistant_constructible_kw_only(self) -> None:
        """FlowAssistant is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            FlowAssistant("goga-reviewer", "reviewer", "Review.", "advisory", "checkpoints")  # type: ignore[misc]
