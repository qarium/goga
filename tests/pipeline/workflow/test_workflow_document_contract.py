"""Contract tests for the ``WorkflowDocument`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade, the two declared properties (``prompt`` and
``stages``), the ``prompt=None`` / ``stages={}`` defaults (the factory is
applied at construction, so the default ``stages`` is an empty dict, not
None), and kw_only construction with explicit stages. These tests pin the
contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowDocument, WorkflowStage


class TestWorkflowDocumentContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_document_importable_from_facade(self) -> None:
        """WorkflowDocument must be importable from the goga.pipeline.workflow facade."""
        assert WorkflowDocument is not None

    def test_workflow_document_has_prompt_property(self) -> None:
        """WorkflowDocument exposes a ``prompt`` property."""
        document = WorkflowDocument(prompt="top-level guidance")

        assert hasattr(document, "prompt")
        assert document.prompt == "top-level guidance"

    def test_workflow_document_has_stages_property(self) -> None:
        """WorkflowDocument exposes a ``stages`` property."""
        document = WorkflowDocument()

        assert hasattr(document, "stages")

    def test_workflow_document_default_prompt_is_none(self) -> None:
        """The default ``prompt`` is None when constructed with no arguments."""
        document = WorkflowDocument()

        assert document.prompt is None

    def test_workflow_document_default_stages_is_empty_dict(self) -> None:
        """The default ``stages`` is an empty dict — the factory is applied at construction."""
        document = WorkflowDocument()

        assert document.stages == {}
        # Factory default, not the None DSL representation.
        assert document.stages is not None

    def test_workflow_document_constructible_kw_only_with_explicit_stages(self) -> None:
        """WorkflowDocument accepts prompt and stages as keyword-only arguments."""
        stages = {"propose": WorkflowStage(agent="codex")}
        document = WorkflowDocument(prompt="guidance", stages=stages)

        assert document.prompt == "guidance"
        assert document.stages == stages
        assert document.stages["propose"].agent == "codex"
