"""Contract tests for the ``render_workflow`` routine.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the
three-parameter signature with its single default (``source_name=""``), and
the ``str`` return contract. These tests pin the contract surface — behavior
lives in the logic test module.
"""

from __future__ import annotations

import inspect
from typing import Any, get_type_hints

from goga.pipeline.workflow import render_workflow


class TestRenderWorkflowContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_render_workflow_importable_from_facade(self) -> None:
        """render_workflow is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.render_workflow is render_workflow
        assert "render_workflow" in facade.__all__

    def test_render_workflow_signature_declares_context_and_source_name(self) -> None:
        """The signature declares text, profile_data, and source_name with its empty default."""
        parameters = inspect.signature(render_workflow).parameters

        assert list(parameters) == ["text", "profile_data", "source_name"]
        assert parameters["source_name"].default == ""

    def test_render_workflow_annotations_declare_mapping(self) -> None:
        """The annotations declare the text/context/name parameters and the ``str`` return."""
        hints = get_type_hints(render_workflow)

        assert hints["text"] is str
        assert hints["profile_data"] == dict[str, Any]
        assert hints["source_name"] is str
        assert hints["return"] is str

    def test_render_workflow_template_free_text_renders_to_itself(self) -> None:
        """A plain template-free text renders unchanged — the identity baseline."""
        text = "stages:\n  build:\n    agent: claude\n"

        assert render_workflow(text, {}, source_name="plain.yml") == text
