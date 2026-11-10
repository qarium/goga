"""Contract tests for the ``LoadedWorkflow`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the two
declared properties (``document``, ``profile``), kw_only construction, frozen
immutability, and the None-able ``profile`` slot. These tests pin the contract
surface — behavior lives in the logic test module.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest
from goga.pipeline.workflow import LoadedWorkflow, ProfileSource, ResolvedProfile, WorkflowDocument


class TestLoadedWorkflowContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_loaded_workflow_importable_from_facade(self) -> None:
        """LoadedWorkflow is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.LoadedWorkflow is LoadedWorkflow
        assert "LoadedWorkflow" in facade.__all__

    def test_loaded_workflow_has_document_property(self) -> None:
        """LoadedWorkflow exposes a ``document`` property carrying the parsed document."""
        document = WorkflowDocument(prompt="hello")
        loaded = LoadedWorkflow(document=document, profile=None)

        assert hasattr(loaded, "document")
        assert loaded.document is document

    def test_loaded_workflow_has_profile_property(self) -> None:
        """LoadedWorkflow exposes a ``profile`` property."""
        profile = ResolvedProfile(name="mixa", data={}, source=ProfileSource.HOME)
        loaded = LoadedWorkflow(document=WorkflowDocument(), profile=profile)

        assert hasattr(loaded, "profile")
        assert loaded.profile is profile

    def test_loaded_workflow_profile_accepts_none(self) -> None:
        """The ``profile`` slot accepts None — a load without an active profile."""
        loaded = LoadedWorkflow(document=WorkflowDocument(), profile=None)

        assert loaded.profile is None

    def test_loaded_workflow_field_order_fixed(self) -> None:
        """Field order is fixed: document, profile."""
        names = [field.name for field in fields(LoadedWorkflow)]

        assert names == ["document", "profile"]

    def test_loaded_workflow_constructible_kw_only(self) -> None:
        """LoadedWorkflow is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            LoadedWorkflow(WorkflowDocument(), None)  # type: ignore[misc]

    def test_loaded_workflow_frozen_immutable(self) -> None:
        """LoadedWorkflow is frozen — field assignment raises FrozenInstanceError."""
        loaded = LoadedWorkflow(document=WorkflowDocument(), profile=None)

        with pytest.raises(FrozenInstanceError):
            loaded.profile = None  # type: ignore[misc]
