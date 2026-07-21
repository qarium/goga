"""Contract tests for the ``WorkflowDocument`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade, the three declared properties (``prompt``,
``stages``, and ``extend``), the ``prompt=None`` / ``stages={}`` /
``extend={}`` defaults (the factories are applied at construction, so the
default ``stages``/``extend`` are empty dicts, not None), and kw_only
construction with explicit stages and extend maps. These tests pin the
contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowStage,
)


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

    def test_workflow_document_has_extend_property(self) -> None:
        """WorkflowDocument exposes an ``extend`` property."""
        document = WorkflowDocument()

        assert hasattr(document, "extend")

    def test_workflow_document_default_extend_is_empty_dict(self) -> None:
        """The default ``extend`` is an empty dict — the factory is applied at construction."""
        document = WorkflowDocument()

        assert document.extend == {}
        # Factory default, not the None DSL representation.
        assert document.extend is not None

    def test_workflow_document_constructible_kw_only_with_explicit_extend(self) -> None:
        """WorkflowDocument accepts extend as a keyword-only argument and stores the map."""
        extend = {"extra": WorkflowExtendStage(after=["review"], body={"title": "Extra"})}
        document = WorkflowDocument(extend=extend)

        assert set(document.extend) == {"extra"}
        assert document.extend["extra"].after == ["review"]
        assert document.extend["extra"].body == {"title": "Extra"}
