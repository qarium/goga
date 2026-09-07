"""Contract tests for the ``WorkflowReflect`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the two
declared properties, the fixed field order, and kw_only construction. These
tests pin the contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

from dataclasses import fields

import pytest
from goga.pipeline.workflow import WorkflowReflect


class TestWorkflowReflectContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_reflect_importable_from_facade(self) -> None:
        """WorkflowReflect is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.WorkflowReflect is WorkflowReflect
        assert "WorkflowReflect" in facade.__all__

    def test_workflow_reflect_has_file_property(self) -> None:
        """WorkflowReflect exposes a ``file`` property."""
        reflect = WorkflowReflect(file="a.md")

        assert hasattr(reflect, "file")
        assert reflect.file == "a.md"

    def test_workflow_reflect_has_mode_property(self) -> None:
        """WorkflowReflect exposes a ``mode`` property defaulting to the materialized "rw"."""
        assert hasattr(WorkflowReflect(file="a.md"), "mode")
        assert WorkflowReflect(file="a.md").mode == "rw"
        assert WorkflowReflect(file="a.md", mode="r").mode == "r"

    def test_workflow_reflect_field_order_fixed(self) -> None:
        """Field order is fixed: file, mode."""
        names = [field.name for field in fields(WorkflowReflect)]

        assert names == ["file", "mode"]

    def test_workflow_reflect_constructible_kw_only(self) -> None:
        """WorkflowReflect is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowReflect("a.md")  # type: ignore[misc]
