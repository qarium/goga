"""Contract tests for the ``WorkflowExtendStage`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade, the three declared properties
(``before``/``after`` defaulting to ``None``, required ``body``), kw_only
construction, and the field-order / required-argument invariants. These tests
pin the contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

import pytest

from goga.pipeline.workflow import WorkflowExtendStage


class TestWorkflowExtendStageContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_extend_stage_importable_from_facade(self) -> None:
        """WorkflowExtendStage must be importable from the goga.pipeline.workflow facade."""
        assert WorkflowExtendStage is not None

    def test_workflow_extend_stage_has_before_property(self) -> None:
        """WorkflowExtendStage exposes a ``before`` property."""
        ext = WorkflowExtendStage(before=["a"], body={})

        assert hasattr(ext, "before")
        assert ext.before == ["a"]

    def test_workflow_extend_stage_has_after_property(self) -> None:
        """WorkflowExtendStage exposes an ``after`` property."""
        ext = WorkflowExtendStage(after=["b"], body={})

        assert hasattr(ext, "after")
        assert ext.after == ["b"]

    def test_workflow_extend_stage_has_body_property(self) -> None:
        """WorkflowExtendStage exposes a ``body`` property."""
        ext = WorkflowExtendStage(body={"title": "T"})

        assert hasattr(ext, "body")
        assert ext.body == {"title": "T"}

    def test_workflow_extend_stage_before_after_default_none(self) -> None:
        """``before`` and ``after`` default to None when constructed without them."""
        ext = WorkflowExtendStage(body={})

        assert ext.before is None
        assert ext.after is None

    def test_workflow_extend_stage_constructible_kw_only(self) -> None:
        """All three fields are accepted as keyword-only arguments."""
        ext = WorkflowExtendStage(before=["a"], after=["b"], body={"title": "T"})

        assert ext.before == ["a"]
        assert ext.after == ["b"]
        assert ext.body == {"title": "T"}

    def test_workflow_extend_stage_body_required(self) -> None:
        """``body`` has no default — constructing without it raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowExtendStage()  # type: ignore[call-arg]

    def test_workflow_extend_stage_kw_only_enforced(self) -> None:
        """Positional construction must fail — fields are keyword-only."""
        with pytest.raises(TypeError):
            WorkflowExtendStage(["a"], ["b"], {})  # type: ignore[misc]
