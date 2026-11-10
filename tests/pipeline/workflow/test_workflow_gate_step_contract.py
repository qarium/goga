"""Contract tests for the ``WorkflowGateStep`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation — the
name sorts before ``WorkflowGates``, after ``WorkflowExtendStage``), the six
declared properties in the fixed order (``name``, ``script``, ``agent``,
``timeout``, ``prompt``, ``env``), the exact defaults (``name`` required, no
default; every other field ``None``), and kw_only construction. These tests
pin the contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
from goga.pipeline.workflow import WorkflowGateStep

from tests.conftest import is_kw_only_dataclass


class TestWorkflowGateStepContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_gate_step_importable_from_facade(self) -> None:
        """WorkflowGateStep is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.WorkflowGateStep is WorkflowGateStep
        assert "WorkflowGateStep" in facade.__all__

    def test_workflow_gate_step_is_kw_only_dataclass(self) -> None:
        """Every field of WorkflowGateStep is keyword-only (``kw_only=True``)."""
        assert is_kw_only_dataclass(WorkflowGateStep)

    def test_workflow_gate_step_signature_matches_contract(self) -> None:
        """The signature matches the contract exactly — name required, the rest defaulting to None.

        ``name, script, agent, timeout, prompt, env`` in the declared order;
        the annotations pin the declared types.
        """
        parameters = list(inspect.signature(WorkflowGateStep).parameters.values())

        assert [parameter.name for parameter in parameters] == [
            "name",
            "script",
            "agent",
            "timeout",
            "prompt",
            "env",
        ]
        assert [parameter.default for parameter in parameters] == [
            inspect.Parameter.empty,
            None,
            None,
            None,
            None,
            None,
        ]
        assert [parameter.annotation for parameter in parameters] == [
            "str",
            "str | None",
            "str | None",
            "str | None",
            "str | None",
            "dict[str, str] | None",
        ]

    def test_workflow_gate_step_field_order_fixed(self) -> None:
        """Field order is fixed: name, script, agent, timeout, prompt, env."""
        names = [field.name for field in fields(WorkflowGateStep)]

        assert names == ["name", "script", "agent", "timeout", "prompt", "env"]

    def test_workflow_gate_step_name_has_no_default(self) -> None:
        """``name`` is required — construction without it raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowGateStep()  # type: ignore[call-arg]

    def test_workflow_gate_step_default_construction_carries_no_authored_key(self) -> None:
        """Beyond the required name, a bare construction carries no authored key."""
        step = WorkflowGateStep(name="checks")

        assert step.name == "checks"
        assert step.script is None
        assert step.agent is None
        assert step.timeout is None
        assert step.prompt is None
        assert step.env is None

    def test_workflow_gate_step_constructible_kw_only(self) -> None:
        """WorkflowGateStep is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowGateStep("checks")  # type: ignore[misc]
