"""Logic tests for the ``WorkflowStage`` dataclass.

Covers construction behavior beyond the contract surface: all-defaults
construction, partial construction, field independence, and immutability of
the provided values (the dataclass is not frozen, but supplied values must
round-trip unchanged).
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowStage


class TestWorkflowStageLogic:
    """Logic tests — construction behavior of the ``WorkflowStage`` dataclass."""

    def test_all_defaults_construction(self) -> None:
        """Constructing with no arguments yields the canonical all-None stage."""
        stage = WorkflowStage()

        assert stage == WorkflowStage(agent=None, prompt=None, loop=None, skills=None)

    def test_partial_construction_agent_only(self) -> None:
        """Specifying only ``agent`` leaves the other three fields at None."""
        stage = WorkflowStage(agent="claude")

        assert stage.agent == "claude"
        assert stage.prompt is None
        assert stage.loop is None
        assert stage.skills is None

    def test_partial_construction_prompt_only(self) -> None:
        """Specifying only ``prompt`` leaves the other three fields at None."""
        stage = WorkflowStage(prompt="extra guidance")

        assert stage.agent is None
        assert stage.prompt == "extra guidance"
        assert stage.loop is None
        assert stage.skills is None

    def test_partial_construction_loop_only(self) -> None:
        """Specifying only ``loop`` leaves the other three fields at None."""
        stage = WorkflowStage(loop=4)

        assert stage.agent is None
        assert stage.prompt is None
        assert stage.loop == 4
        assert stage.skills is None

    def test_partial_construction_skills_only(self) -> None:
        """Specifying only ``skills`` leaves the other three fields at None."""
        stage = WorkflowStage(skills=["web-search"])

        assert stage.agent is None
        assert stage.prompt is None
        assert stage.loop is None
        assert stage.skills == ["web-search"]

    def test_fields_independent(self) -> None:
        """Each field holds the value it was constructed with, independently."""
        stage = WorkflowStage(agent="codex", prompt="text", loop=2, skills=["a", "b"])

        assert stage.agent == "codex"
        assert stage.prompt == "text"
        assert stage.loop == 2
        assert stage.skills == ["a", "b"]

    def test_provided_values_round_trip_unchanged(self) -> None:
        """Provided values are immutable in the round-trip sense — set once, read verbatim."""
        stage = WorkflowStage(agent="codex", prompt="text", loop=2, skills=["a", "b"])

        assert stage.agent == "codex"
        assert stage.prompt == "text"
        assert stage.loop == 2
        assert stage.skills == ["a", "b"]

    def test_loop_accepts_boundary_one(self) -> None:
        """loop == 1 (the minimum) is accepted by the dataclass itself."""
        stage = WorkflowStage(loop=1)

        assert stage.loop == 1

    def test_skills_defaults_to_none_when_omitted(self) -> None:
        """Omitting ``skills`` yields None — no merge semantics for the consumer."""
        stage = WorkflowStage(agent="codex")

        assert stage.skills is None

    def test_skills_accepts_empty_list(self) -> None:
        """An empty ``skills`` list is a valid value (distinct from None)."""
        stage = WorkflowStage(skills=[])

        assert stage.skills == []

    def test_skills_accepts_multiple_entries(self) -> None:
        """A ``skills`` list with several names round-trips verbatim."""
        stage = WorkflowStage(skills=["web-search", "goga-propose", "dataviz"])

        assert stage.skills == ["web-search", "goga-propose", "dataviz"]

    def test_equality_of_identical_constructions(self) -> None:
        """Two stages with identical fields compare equal."""
        first = WorkflowStage(agent="codex", prompt="text", loop=2, skills=["a"])
        second = WorkflowStage(agent="codex", prompt="text", loop=2, skills=["a"])

        assert first == second
