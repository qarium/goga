"""Contract tests for the ``WorkflowGates`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation —
``WorkflowGateStep`` sorts before ``WorkflowGates``, both after
``WorkflowExtendStage``), the three declared properties in the fixed order
(``patience``, ``max_iterations``, ``fresh_correction``), the exact defaults
(all ``None`` — the model carries authored values only and materializes NO
defaults; an authored ``0`` is a VALUE, never an absence), and kw_only
construction. These tests pin the contract surface — behavior lives in the
logic test module.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
from goga.pipeline.workflow import WorkflowGates

from tests.conftest import is_kw_only_dataclass


class TestWorkflowGatesContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_gates_importable_from_facade(self) -> None:
        """WorkflowGates is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.WorkflowGates is WorkflowGates
        assert "WorkflowGates" in facade.__all__

    def test_workflow_gates_all_position_between_extend_stage_and_gate_step(self) -> None:
        """The facade ``__all__`` places the two gate names after WorkflowExtendStage.

        ``WorkflowGateStep`` sorts before ``WorkflowGates`` in ASCII — the
        facade list carries both, in that order, right after
        ``WorkflowExtendStage``.
        """
        import goga.pipeline.workflow as facade

        names = facade.__all__

        assert names.index("WorkflowExtendStage") < names.index("WorkflowGateStep") < names.index("WorkflowGates")

    def test_workflow_gates_is_kw_only_dataclass(self) -> None:
        """Every field of WorkflowGates is keyword-only (``kw_only=True``)."""
        assert is_kw_only_dataclass(WorkflowGates)

    def test_workflow_gates_signature_matches_contract(self) -> None:
        """The signature matches the contract exactly — three parameters, all defaulting to None.

        ``patience, max_iterations, fresh_correction`` in the declared order;
        the annotations pin the declared types (``int | None`` twice, then
        ``bool | None``).
        """
        parameters = list(inspect.signature(WorkflowGates).parameters.values())

        assert [parameter.name for parameter in parameters] == ["patience", "max_iterations", "fresh_correction"]
        assert [parameter.default for parameter in parameters] == [None, None, None]
        assert [parameter.annotation for parameter in parameters] == ["int | None", "int | None", "bool | None"]

    def test_workflow_gates_field_order_fixed(self) -> None:
        """Field order is fixed: patience, max_iterations, fresh_correction."""
        names = [field.name for field in fields(WorkflowGates)]

        assert names == ["patience", "max_iterations", "fresh_correction"]

    def test_workflow_gates_default_construction_carries_no_authored_key(self) -> None:
        """A no-argument construction carries no authored key — all fields None."""
        gates = WorkflowGates()

        assert gates.patience is None
        assert gates.max_iterations is None
        assert gates.fresh_correction is None

    def test_workflow_gates_authored_zero_is_a_value(self) -> None:
        """An authored ``0`` is a VALUE — distinguishable from the ``None`` absence."""
        assert WorkflowGates(patience=0).patience == 0
        assert WorkflowGates(max_iterations=0).max_iterations == 0
        assert WorkflowGates(patience=0, max_iterations=0).patience is not None
        assert WorkflowGates(patience=0, max_iterations=0).max_iterations is not None
        assert WorkflowGates(patience=0, max_iterations=0) != WorkflowGates()

    def test_workflow_gates_constructible_kw_only(self) -> None:
        """WorkflowGates is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowGates(3)  # type: ignore[misc]
