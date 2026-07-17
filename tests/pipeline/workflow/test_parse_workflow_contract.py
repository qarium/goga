"""Contract tests for the ``parse_workflow`` routine.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability of ``parse_workflow`` from the facade, callability with a single
``Path`` argument, and that a valid workflow-file yields a ``WorkflowDocument``.
These tests pin the contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

from pathlib import Path

from goga.pipeline.workflow import WorkflowDocument, parse_workflow


class TestParseWorkflowContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_parse_workflow_importable_from_facade(self) -> None:
        """parse_workflow must be importable from the goga.pipeline.workflow facade."""
        assert parse_workflow is not None

    def test_parse_workflow_callable_with_single_path_argument(self, tmp_path: Path) -> None:
        """parse_workflow accepts a single Path positional argument."""
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text("prompt: top-level guidance\n")

        document = parse_workflow(workflow_path)

        assert isinstance(document, WorkflowDocument)

    def test_parse_workflow_returns_workflow_document_for_valid_input(self, tmp_path: Path) -> None:
        """parse_workflow returns a WorkflowDocument for a valid workflow-file."""
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "prompt: top-level guidance\n"
            "stages:\n"
            "  propose:\n"
            "    agent: codex\n"
        )

        document = parse_workflow(workflow_path)

        assert isinstance(document, WorkflowDocument)
        assert document.prompt == "top-level guidance"
        assert "propose" in document.stages
        assert document.stages["propose"].agent == "codex"
