"""Contract tests for the ``FlowVerify`` dataclass.

Verifies the public API declared by the compiler-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation — the
name sorts after ``FlowTeamMember``, before ``PhaseStep``, preceding
``FlowVerifyStep``), the four declared properties in the fixed order
(``steps``, ``max_failures``, ``review_patience``, ``fresh_correction`` —
the emission order of the block keys), the exact defaults (``steps``
required, no default; every setting ``None`` — authored keys only, an
authored zero is a VALUE, never an omission), and kw_only construction.
These tests pin the contract surface — behavior lives in the logic test
module.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
from goga.pipeline.compiler import FlowVerify, FlowVerifyStep

from tests.conftest import is_kw_only_dataclass


class TestFlowVerifyContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_flow_verify_importable_from_facade(self) -> None:
        """FlowVerify is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.compiler as facade

        assert facade.FlowVerify is FlowVerify
        assert "FlowVerify" in facade.__all__

    def test_flow_verify_is_kw_only_dataclass(self) -> None:
        """Every field of FlowVerify is keyword-only (``kw_only=True``)."""
        assert is_kw_only_dataclass(FlowVerify)

    def test_flow_verify_signature_matches_contract(self) -> None:
        """The signature matches the contract exactly — steps required, the settings defaulting to None.

        ``steps, max_failures, review_patience, fresh_correction`` in the
        declared order; the annotations pin the declared types.
        """
        parameters = list(inspect.signature(FlowVerify).parameters.values())

        assert [parameter.name for parameter in parameters] == [
            "steps",
            "max_failures",
            "review_patience",
            "fresh_correction",
        ]
        assert [parameter.default for parameter in parameters] == [inspect.Parameter.empty, None, None, None]
        assert [parameter.annotation for parameter in parameters] == [
            "list[FlowVerifyStep]",
            "int | None",
            "int | None",
            "bool | None",
        ]

    def test_flow_verify_field_order_fixed(self) -> None:
        """Field order is fixed: steps, max_failures, review_patience, fresh_correction."""
        names = [field.name for field in fields(FlowVerify)]

        assert names == ["steps", "max_failures", "review_patience", "fresh_correction"]

    def test_flow_verify_steps_has_no_default(self) -> None:
        """``steps`` is required — construction without it raises TypeError."""
        with pytest.raises(TypeError):
            FlowVerify()  # type: ignore[call-arg]

    def test_flow_verify_settings_default_none(self) -> None:
        """Each setting field's declared default is ``None`` — authored values only."""
        by_name = {field.name: field for field in fields(FlowVerify)}

        assert by_name["max_failures"].default is None
        assert by_name["review_patience"].default is None
        assert by_name["fresh_correction"].default is None

    def test_flow_verify_zero_is_a_value_not_an_omission(self) -> None:
        """An authored ``0`` stays distinguishable from ``None`` on both int settings."""
        gate = FlowVerify(steps=[], max_failures=0, review_patience=0)

        assert gate.max_failures == 0
        assert gate.max_failures is not None
        assert gate.review_patience == 0
        assert gate.review_patience is not None

    def test_flow_verify_constructible_kw_only(self) -> None:
        """FlowVerify is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            FlowVerify([FlowVerifyStep(name="t", run="pytest")])  # type: ignore[misc]
