"""Contract tests for the ``WorkflowMemory`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the five
declared properties, the fixed field order, and kw_only construction. These
tests pin the contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

from dataclasses import fields

import pytest
from goga.pipeline.workflow import WorkflowMemory


class TestWorkflowMemoryContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_memory_importable_from_facade(self) -> None:
        """WorkflowMemory is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.WorkflowMemory is WorkflowMemory
        assert "WorkflowMemory" in facade.__all__

    def test_workflow_memory_has_method_property(self) -> None:
        """WorkflowMemory exposes a ``method`` property defaulting to "reflect"."""
        assert hasattr(WorkflowMemory(), "method")
        assert WorkflowMemory().method == "reflect"
        assert WorkflowMemory(method="alignment").method == "alignment"

    def test_workflow_memory_has_path_property(self) -> None:
        """WorkflowMemory exposes a ``path`` property defaulting to None."""
        assert hasattr(WorkflowMemory(), "path")
        assert WorkflowMemory().path is None
        assert WorkflowMemory(path="goga-development").path == "goga-development"

    def test_workflow_memory_has_max_rules_property(self) -> None:
        """WorkflowMemory exposes a ``max_rules`` property defaulting to 25."""
        assert hasattr(WorkflowMemory(), "max_rules")
        assert WorkflowMemory().max_rules == 25
        assert WorkflowMemory(max_rules=40).max_rules == 40

    def test_workflow_memory_has_commit_property(self) -> None:
        """WorkflowMemory exposes a ``commit`` property defaulting to False."""
        assert hasattr(WorkflowMemory(), "commit")
        assert WorkflowMemory().commit is False
        assert WorkflowMemory(commit=True).commit is True

    def test_workflow_memory_has_mode_property(self) -> None:
        """WorkflowMemory exposes a ``mode`` property defaulting to None."""
        assert hasattr(WorkflowMemory(), "mode")
        assert WorkflowMemory().mode is None
        assert WorkflowMemory(mode="rw").mode == "rw"

    def test_workflow_memory_field_order_fixed(self) -> None:
        """Field order is fixed: method, path, max_rules, commit, mode."""
        names = [field.name for field in fields(WorkflowMemory)]

        assert names == ["method", "path", "max_rules", "commit", "mode"]

    def test_workflow_memory_constructible_kw_only(self) -> None:
        """WorkflowMemory is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowMemory("reflect")  # type: ignore[misc]
