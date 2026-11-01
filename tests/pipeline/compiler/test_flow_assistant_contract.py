"""Contract tests for the ``FlowAssistant`` dataclass.

Verifies the public API declared by the compiler-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the
six declared properties in the fixed emission order (``profile``, ``title``,
``instruction``, ``mode``, ``trigger``, ``skills``), the no-default pins of
every field (the emission materializes every default — the checkpoints
trigger is written explicitly, never inherited from the engine default), and
kw_only construction. These tests pin the contract surface — behavior lives
in the logic test module.
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
        """The signature matches the contract exactly — six required parameters.

        profile, title, instruction, mode, trigger, skills in the declared
        order; every field carries NO default (an entry is always complete —
        the emission materializes the instruction empty string, the empty
        skills list, and the advisory/checkpoints defaults; only
        ``compile_flow`` builds this type).
        """
        parameters = list(inspect.signature(FlowAssistant).parameters.values())
        empty = inspect.Parameter.empty

        assert [parameter.name for parameter in parameters] == [
            "profile",
            "title",
            "instruction",
            "mode",
            "trigger",
            "skills",
        ]
        assert [parameter.default for parameter in parameters] == [empty] * 6
        assert [parameter.annotation for parameter in parameters] == [
            "str",
            "str",
            "str",
            "str",
            "str",
            "list[str]",
        ]

    def test_flow_assistant_field_order_fixed(self) -> None:
        """Field order is fixed — the emission order of the entry keys."""
        names = [field.name for field in fields(FlowAssistant)]

        assert names == ["profile", "title", "instruction", "mode", "trigger", "skills"]

    def test_flow_assistant_fields_all_required(self) -> None:
        """Constructing without any field raises TypeError — no silent defaults."""
        with pytest.raises(TypeError):
            FlowAssistant()  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            FlowAssistant(profile="goga-reviewer", title="reviewer", instruction="Review.")  # type: ignore[call-arg]

    def test_flow_assistant_constructible_kw_only(self) -> None:
        """FlowAssistant is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            FlowAssistant("goga-reviewer", "reviewer", "Review.", "advisory", "checkpoints", [])  # type: ignore[misc]
