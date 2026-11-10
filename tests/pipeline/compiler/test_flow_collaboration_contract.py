"""Contract tests for the ``FlowCollaboration`` dataclass.

Verifies the public API declared by the compiler-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the
two declared properties in the fixed emission order (``mode``, ``max_depth``),
the exact defaults (``mode="assistants"`` — the block is emitted into every
compiled flow; ``max_depth=None`` — the key is omitted from the output), and
kw_only construction. These tests pin the contract surface — behavior lives
in the logic test module.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
from goga.pipeline.compiler import FlowCollaboration

from tests.conftest import is_kw_only_dataclass


class TestFlowCollaborationContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_flow_collaboration_importable_from_facade(self) -> None:
        """FlowCollaboration is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.compiler as facade

        assert facade.FlowCollaboration is FlowCollaboration
        assert "FlowCollaboration" in facade.__all__

    def test_flow_collaboration_is_kw_only_dataclass(self) -> None:
        """Every field of FlowCollaboration is keyword-only."""
        assert is_kw_only_dataclass(FlowCollaboration)

    def test_flow_collaboration_signature_matches_contract(self) -> None:
        """The signature matches the contract exactly — mode, max_depth.

        ``mode`` defaults to ``"assistants"`` (the block is emitted into every
        compiled flow) and ``max_depth`` defaults to ``None`` (the key is
        omitted from the output entirely — the omission rule is ``is None``,
        never truthiness).
        """
        parameters = list(inspect.signature(FlowCollaboration).parameters.values())

        assert [parameter.name for parameter in parameters] == ["mode", "max_depth"]
        assert [parameter.default for parameter in parameters] == ["assistants", None]
        assert [parameter.annotation for parameter in parameters] == ["str", "int | None"]

    def test_flow_collaboration_field_order_fixed(self) -> None:
        """Field order is fixed: mode, max_depth — the emission order of the block keys."""
        names = [field.name for field in fields(FlowCollaboration)]

        assert names == ["mode", "max_depth"]

    def test_flow_collaboration_defaults_materialize(self) -> None:
        """A bare construction materializes the block defaults."""
        block = FlowCollaboration()

        assert block.mode == "assistants"
        assert block.max_depth is None

    def test_flow_collaboration_constructible_kw_only(self) -> None:
        """FlowCollaboration is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            FlowCollaboration("assistants", 2)  # type: ignore[misc]
