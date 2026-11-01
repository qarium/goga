"""Contract tests for the ``WorkflowDelegation`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the two
declared properties in the fixed order (``depth``, ``max_tasks``), the exact
defaults (``depth=None`` — absence; ``max_tasks=50`` — the materialized
engine-side default), and kw_only construction. These tests pin the contract
surface — behavior lives in the logic test module.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
from goga.pipeline.workflow import WorkflowDelegation

from tests.conftest import is_kw_only_dataclass


class TestWorkflowDelegationContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_delegation_importable_from_facade(self) -> None:
        """WorkflowDelegation is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.WorkflowDelegation is WorkflowDelegation
        assert "WorkflowDelegation" in facade.__all__

    def test_workflow_delegation_is_kw_only_dataclass(self) -> None:
        """Every field of WorkflowDelegation is keyword-only."""
        assert is_kw_only_dataclass(WorkflowDelegation)

    def test_workflow_delegation_signature_matches_contract(self) -> None:
        """The signature matches the contract exactly — two parameters, both defaulted.

        depth, max_tasks in the declared order; ``depth`` defaults to ``None``
        (an authored ``0`` is a VALUE, never an absence), ``max_tasks``
        materializes to ``50`` when absent (the engine default of 20 is never
        relied upon), and the annotations pin the declared types.
        """
        parameters = list(inspect.signature(WorkflowDelegation).parameters.values())

        assert [parameter.name for parameter in parameters] == ["depth", "max_tasks"]
        assert [parameter.default for parameter in parameters] == [None, 50]
        assert [parameter.annotation for parameter in parameters] == ["int | None", "int"]

    def test_workflow_delegation_field_order_fixed(self) -> None:
        """Field order is fixed: depth, max_tasks."""
        names = [field.name for field in fields(WorkflowDelegation)]

        assert names == ["depth", "max_tasks"]

    def test_workflow_delegation_default_construction(self) -> None:
        """A no-argument construction materializes the absence/default pair (None, 50)."""
        delegation = WorkflowDelegation()

        assert delegation.depth is None
        assert delegation.max_tasks == 50

    def test_workflow_delegation_constructible_kw_only(self) -> None:
        """WorkflowDelegation is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowDelegation(3)  # type: ignore[misc]
