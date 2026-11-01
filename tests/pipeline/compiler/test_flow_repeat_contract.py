"""Contract tests for the ``FlowRepeat`` dataclass.

Verifies the public API declared by the compiler-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the two
declared properties, the fixed field order (the emission order of the block
keys), kw_only construction, and the authored-values-only rule — both fields
default to ``None`` and an authored zero is a VALUE, never an omission. These
tests pin the contract surface — behavior lives in the logic test modules.
"""

from __future__ import annotations

from dataclasses import fields

import pytest
from goga.pipeline.compiler import FlowRepeat

from tests.conftest import is_kw_only_dataclass


class TestFlowRepeatContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_flow_repeat_importable_from_facade(self) -> None:
        """FlowRepeat is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.compiler as facade

        assert facade.FlowRepeat is FlowRepeat
        assert "FlowRepeat" in facade.__all__

    def test_flow_repeat_defaults_carry_no_authored_key(self) -> None:
        """A default-constructed directive carries no authored key (the scalar form)."""
        directive = FlowRepeat()

        assert directive.max_cycles is None
        assert directive.keep_runs is None

    def test_flow_repeat_has_max_cycles_property(self) -> None:
        """FlowRepeat exposes a ``max_cycles`` property."""
        assert hasattr(FlowRepeat(), "max_cycles")
        assert FlowRepeat(max_cycles=3).max_cycles == 3

    def test_flow_repeat_has_keep_runs_property(self) -> None:
        """FlowRepeat exposes a ``keep_runs`` property."""
        assert hasattr(FlowRepeat(), "keep_runs")
        assert FlowRepeat(keep_runs=5).keep_runs == 5

    def test_flow_repeat_zero_is_a_value_not_an_omission(self) -> None:
        """An authored ``0`` stays distinguishable from ``None`` on both fields."""
        directive = FlowRepeat(max_cycles=0, keep_runs=0)

        assert directive.max_cycles == 0
        assert directive.max_cycles is not None
        assert directive.keep_runs == 0
        assert directive.keep_runs is not None

    def test_flow_repeat_field_order_fixed(self) -> None:
        """Field order is fixed: max_cycles, keep_runs."""
        names = [field.name for field in fields(FlowRepeat)]

        assert names == ["max_cycles", "keep_runs"]

    def test_flow_repeat_constructible_kw_only(self) -> None:
        """FlowRepeat is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            FlowRepeat(3, 5)  # type: ignore[misc]

    def test_flow_repeat_is_kw_only_dataclass(self) -> None:
        """Every field of FlowRepeat is keyword-only (``kw_only=True``)."""
        assert is_kw_only_dataclass(FlowRepeat)

    def test_flow_repeat_both_fields_default_none(self) -> None:
        """Each field's declared default is ``None`` — authored values only."""
        by_name = {field.name: field for field in fields(FlowRepeat)}

        assert by_name["max_cycles"].default is None
        assert by_name["keep_runs"].default is None
