"""Contract tests for the ``WorkflowExtendStage`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade, the five declared properties
(``before``/``after``/``agent``/``loop`` defaulting to ``None``, required
``body``), kw_only construction, and the field-order / required-argument
invariants. These tests pin the contract surface — behavior lives in the
logic test module.
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

    def test_workflow_extend_stage_has_agent_property(self) -> None:
        """WorkflowExtendStage exposes an ``agent`` property."""
        ext = WorkflowExtendStage(after=["x"], agent="codex", body={"title": "T"})

        assert hasattr(ext, "agent")
        assert ext.agent == "codex"

    def test_workflow_extend_stage_has_loop_property(self) -> None:
        """WorkflowExtendStage exposes a ``loop`` property."""
        ext = WorkflowExtendStage(after=["x"], loop=3, body={"title": "T"})

        assert hasattr(ext, "loop")
        assert ext.loop == 3

    def test_workflow_extend_stage_has_body_property(self) -> None:
        """WorkflowExtendStage exposes a ``body`` property."""
        ext = WorkflowExtendStage(body={"title": "T"})

        assert hasattr(ext, "body")
        assert ext.body == {"title": "T"}

    def test_workflow_extend_stage_before_after_agent_loop_default_none(self) -> None:
        """``before``/``after``/``agent``/``loop`` default to None when omitted."""
        ext = WorkflowExtendStage(body={})

        assert ext.before is None
        assert ext.after is None
        assert ext.agent is None
        assert ext.loop is None

    def test_workflow_extend_stage_constructible_kw_only(self) -> None:
        """All five fields are accepted as keyword-only arguments."""
        ext = WorkflowExtendStage(before=["a"], after=["b"], agent="codex", loop=2, body={"title": "T"})

        assert ext.before == ["a"]
        assert ext.after == ["b"]
        assert ext.agent == "codex"
        assert ext.loop == 2
        assert ext.body == {"title": "T"}

    def test_workflow_extend_stage_body_required(self) -> None:
        """``body`` has no default — constructing without it raises TypeError."""
        with pytest.raises(TypeError):
            WorkflowExtendStage()  # type: ignore[call-arg]

    def test_workflow_extend_stage_kw_only_enforced(self) -> None:
        """Positional construction must fail — fields are keyword-only."""
        with pytest.raises(TypeError):
            WorkflowExtendStage(["a"], ["b"], {})  # type: ignore[misc]
