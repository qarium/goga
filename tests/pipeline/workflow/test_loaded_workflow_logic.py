"""Logic tests for the ``LoadedWorkflow`` dataclass.

Covers behavior beyond the contract surface: the ``profile`` slot accepting
None and a ``ResolvedProfile``, the document carried verbatim, and value
equality.
"""

from __future__ import annotations

from goga.pipeline.workflow import (
    LoadedWorkflow,
    ProfileSource,
    ResolvedProfile,
    WorkflowDocument,
)


class TestLoadedWorkflowLogic:
    """Logic tests — value carriage of the ``LoadedWorkflow`` dataclass."""

    def test_profile_accepts_none(self) -> None:
        """``profile=None`` — a load that ran with an empty rendering context."""
        document = WorkflowDocument(prompt="hello")
        loaded = LoadedWorkflow(document=document, profile=None)

        assert loaded.profile is None
        assert loaded.document is document

    def test_profile_accepts_resolved_profile(self) -> None:
        """``profile`` accepts a ``ResolvedProfile`` — carried verbatim (same object)."""
        profile = ResolvedProfile(
            name="mixa",
            data={"worker": {"agent": "codex", "model": "sonnet"}},
            source=ProfileSource.PROJECT,
        )
        loaded = LoadedWorkflow(document=WorkflowDocument(), profile=profile)

        assert loaded.profile is profile
        assert loaded.profile.name == "mixa"
        assert loaded.profile.source is ProfileSource.PROJECT

    def test_document_carried_verbatim(self) -> None:
        """The parsed document is carried verbatim — no copy, no revalidation."""
        document = WorkflowDocument(prompt="hello")
        loaded = LoadedWorkflow(document=document, profile=None)

        assert loaded.document is document
        assert loaded.document.prompt == "hello"

    def test_equality_of_identical_constructions(self) -> None:
        """Two loads with identical document and profile compare equal."""
        document = WorkflowDocument(prompt="hello")
        profile = ResolvedProfile(name="mixa", data={}, source=ProfileSource.HOME)

        first = LoadedWorkflow(document=document, profile=profile)
        second = LoadedWorkflow(document=document, profile=profile)

        assert first == second

    def test_inequality_on_differing_profile(self) -> None:
        """A loaded workflow with a profile differs from one without."""
        document = WorkflowDocument(prompt="hello")
        profile = ResolvedProfile(name="mixa", data={}, source=ProfileSource.HOME)

        assert LoadedWorkflow(document=document, profile=profile) != LoadedWorkflow(document=document, profile=None)
