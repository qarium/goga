"""Contract tests for the ``load_workflow`` routine.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the
four-parameter signature with its three ``None`` defaults, and the
annotations of every parameter and the ``LoadedWorkflow`` return. Behavior
lives in the logic test module.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, get_type_hints

from goga.pipeline.workflow import LoadedWorkflow, load_workflow


class TestLoadWorkflowContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_load_workflow_importable_from_facade(self) -> None:
        """load_workflow is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.load_workflow is load_workflow
        assert "load_workflow" in facade.__all__

    def test_load_workflow_signature_declares_channels(self) -> None:
        """The signature declares the path and the three optional channel parameters."""
        parameters = inspect.signature(load_workflow).parameters

        assert list(parameters) == ["workflow_path", "cli_profile", "env_profile", "home_profiles"]
        assert parameters["cli_profile"].default is None
        assert parameters["env_profile"].default is None
        assert parameters["home_profiles"].default is None

    def test_load_workflow_annotations_declare_channels_and_result(self) -> None:
        """The annotations declare the path, the channel optionals, and the return type."""
        hints = get_type_hints(load_workflow)

        assert hints["workflow_path"] is Path
        assert hints["cli_profile"] == str | None
        assert hints["env_profile"] == str | None
        assert hints["home_profiles"] == dict[str, dict[str, Any]] | None
        assert hints["return"] is LoadedWorkflow
