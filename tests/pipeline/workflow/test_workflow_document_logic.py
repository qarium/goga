"""Logic tests for the ``WorkflowDocument`` dataclass.

Covers construction behavior beyond the contract surface: the canonical
default construction, ``default_factory`` isolation between instances (two
documents never share a ``stages`` map), round-tripping of an explicit
prompt plus stages map, and the equality semantics of identical documents.
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowDocument, WorkflowStage


class TestWorkflowDocumentLogic:
    """Logic tests — construction behavior of the ``WorkflowDocument`` dataclass."""

    def test_default_construction(self) -> None:
        """Constructing with no arguments yields the canonical empty document."""
        document = WorkflowDocument()

        assert document == WorkflowDocument(prompt=None, stages={})
        assert document.prompt is None
        assert document.stages == {}

    def test_default_factory_isolates_stages_across_instances(self) -> None:
        """Two default-constructed documents get independent ``stages`` dicts."""
        first = WorkflowDocument()
        second = WorkflowDocument()

        first.stages["propose"] = WorkflowStage(agent="codex")

        # The second document's stages must be unaffected.
        assert second.stages == {}
        assert first.stages is not second.stages

    def test_prompt_and_explicit_stages_round_trip(self) -> None:
        """A document built with a prompt and an explicit stages map round-trips."""
        stages = {"propose": WorkflowStage(prompt="Additional prompt")}
        document = WorkflowDocument(prompt="guidance", stages=stages)

        assert document.prompt == "guidance"
        assert document.stages == stages
        assert document.stages["propose"].prompt == "Additional prompt"

    def test_explicit_stages_are_not_copied(self) -> None:
        """The supplied ``stages`` map is stored verbatim — the factory is not applied."""
        stages = {"propose": WorkflowStage(agent="codex")}
        document = WorkflowDocument(stages=stages)

        assert document.stages is stages

    def test_prompt_only_construction(self) -> None:
        """A document carrying only a top-level prompt leaves ``stages`` empty."""
        document = WorkflowDocument(prompt="only a prompt")

        assert document.prompt == "only a prompt"
        assert document.stages == {}

    def test_stages_with_multiple_entries_round_trip(self) -> None:
        """A document carrying several stage overrides round-trips each entry."""
        stages = {
            "propose": WorkflowStage(agent="codex"),
            "review": WorkflowStage(prompt="be thorough", loop=2),
        }
        document = WorkflowDocument(stages=stages)

        assert document.stages["propose"].agent == "codex"
        assert document.stages["review"].prompt == "be thorough"
        assert document.stages["review"].loop == 2

    def test_equality_of_identical_documents(self) -> None:
        """Two documents with identical fields compare equal."""
        stages = {"propose": WorkflowStage(agent="codex")}
        first = WorkflowDocument(prompt="guidance", stages=dict(stages))
        second = WorkflowDocument(prompt="guidance", stages=dict(stages))

        assert first == second
