"""Contract tests for the ``FlowVerifyStep`` dataclass.

Verifies the public API declared by the compiler-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation — the
name sorts after ``FlowTeamMember``, before ``PhaseStep``), the five declared
properties in the fixed order (``name``, ``run``, ``command``, ``timeout``,
``prompt`` — the emission order of the step keys), the exact defaults
(``name`` required, no default; every other field ``None``), and kw_only
construction. These tests pin the contract surface — behavior lives in the
logic test module.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
from goga.pipeline.compiler import FlowVerifyStep

from tests.conftest import is_kw_only_dataclass


class TestFlowVerifyStepContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_flow_verify_step_importable_from_facade(self) -> None:
        """FlowVerifyStep is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.compiler as facade

        assert facade.FlowVerifyStep is FlowVerifyStep
        assert "FlowVerifyStep" in facade.__all__

    def test_flow_verify_step_is_kw_only_dataclass(self) -> None:
        """Every field of FlowVerifyStep is keyword-only (``kw_only=True``)."""
        assert is_kw_only_dataclass(FlowVerifyStep)

    def test_flow_verify_step_signature_matches_contract(self) -> None:
        """The signature matches the contract exactly — name required, the rest defaulting to None.

        ``name, run, command, timeout, prompt`` in the declared order; the
        annotations pin the declared types.
        """
        parameters = list(inspect.signature(FlowVerifyStep).parameters.values())

        assert [parameter.name for parameter in parameters] == ["name", "run", "command", "timeout", "prompt"]
        assert [parameter.default for parameter in parameters] == [inspect.Parameter.empty, None, None, None, None]
        assert [parameter.annotation for parameter in parameters] == [
            "str",
            "str | None",
            "str | None",
            "str | None",
            "str | None",
        ]

    def test_flow_verify_step_field_order_fixed(self) -> None:
        """Field order is fixed: name, run, command, timeout, prompt."""
        names = [field.name for field in fields(FlowVerifyStep)]

        assert names == ["name", "run", "command", "timeout", "prompt"]

    def test_flow_verify_step_name_has_no_default(self) -> None:
        """``name`` is required — construction without it raises TypeError."""
        with pytest.raises(TypeError):
            FlowVerifyStep()  # type: ignore[call-arg]

    def test_flow_verify_step_default_construction_carries_no_authored_key(self) -> None:
        """Beyond the required name, a bare construction carries no authored key."""
        step = FlowVerifyStep(name="Unit tests")

        assert step.name == "Unit tests"
        assert step.run is None
        assert step.command is None
        assert step.timeout is None
        assert step.prompt is None

    def test_flow_verify_step_constructible_kw_only(self) -> None:
        """FlowVerifyStep is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            FlowVerifyStep("checks")  # type: ignore[misc]
