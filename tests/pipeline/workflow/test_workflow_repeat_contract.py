"""Contract tests for the ``WorkflowRepeat`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the two
declared properties in the fixed order (``max_cycles``, ``keep_runs``), the
exact defaults (both ``None`` — the model carries authored values only and
materializes NO defaults; an authored ``0`` is a VALUE, never an absence),
and kw_only construction. These tests pin the contract surface — behavior
lives in the logic test module.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
from goga.pipeline.workflow import WorkflowRepeat

from tests.conftest import is_kw_only_dataclass


class TestWorkflowRepeatContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_repeat_importable_from_facade(self) -> None:
        """WorkflowRepeat is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.WorkflowRepeat is WorkflowRepeat
        assert "WorkflowRepeat" in facade.__all__

    def test_workflow_repeat_is_kw_only_dataclass(self) -> None:
        """Every field of WorkflowRepeat is keyword-only (``kw_only=True``)."""
        assert is_kw_only_dataclass(WorkflowRepeat)
        assert WorkflowRepeat.__dataclass_params__.kw_only is True

    def test_workflow_repeat_signature_matches_contract(self) -> None:
        """The signature matches the contract exactly — two parameters, both defaulting to None.

        ``max_cycles, keep_runs`` in the declared order; the annotations pin
        the declared ``int | None`` types.
        """
        parameters = list(inspect.signature(WorkflowRepeat).parameters.values())

        assert [parameter.name for parameter in parameters] == ["max_cycles", "keep_runs"]
        assert [parameter.default for parameter in parameters] == [None, None]
        assert [parameter.annotation for parameter in parameters] == ["int | None", "int | None"]

    def test_workflow_repeat_field_order_fixed(self) -> None:
        """Field order is fixed: max_cycles, keep_runs."""
        names = [field.name for field in fields(WorkflowRepeat)]

        assert names == ["max_cycles", "keep_runs"]

    def test_workflow_repeat_default_construction_carries_no_authored_key(self) -> None:
        """A no-argument construction carries no authored key — both fields None."""
        repeat = WorkflowRepeat()

        assert repeat.max_cycles is None
        assert repeat.keep_runs is None

    def test_workflow_repeat_authored_zero_is_a_value(self) -> None:
        """An authored ``0`` is a VALUE — distinguishable from the ``None`` absence."""
        assert WorkflowRepeat(max_cycles=0).max_cycles == 0
        assert WorkflowRepeat(keep_runs=0).keep_runs == 0
        assert WorkflowRepeat(max_cycles=0).keep_runs is None
        assert WorkflowRepeat(max_cycles=0) != WorkflowRepeat()

    def test_workflow_repeat_constructible_kw_only(self) -> None:
        """WorkflowRepeat is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowRepeat(3)  # type: ignore[misc]
