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

        assert stage == WorkflowStage(agent=None, prompt=None, loop=None)

    def test_partial_construction_agent_only(self) -> None:
        """Specifying only ``agent`` leaves the other two fields at None."""
        stage = WorkflowStage(agent="claude")

        assert stage.agent == "claude"
        assert stage.prompt is None
        assert stage.loop is None

    def test_partial_construction_prompt_only(self) -> None:
        """Specifying only ``prompt`` leaves the other two fields at None."""
        stage = WorkflowStage(prompt="extra guidance")

        assert stage.agent is None
        assert stage.prompt == "extra guidance"
        assert stage.loop is None

    def test_partial_construction_loop_only(self) -> None:
        """Specifying only ``loop`` leaves the other two fields at None."""
        stage = WorkflowStage(loop=4)

        assert stage.agent is None
        assert stage.prompt is None
        assert stage.loop == 4

    def test_fields_independent(self) -> None:
        """Each field holds the value it was constructed with, independently."""
        stage = WorkflowStage(agent="codex", prompt="text", loop=2)

        assert stage.agent == "codex"
        assert stage.prompt == "text"
        assert stage.loop == 2

    def test_provided_values_round_trip_unchanged(self) -> None:
        """Provided values are immutable in the round-trip sense — set once, read verbatim."""
        stage = WorkflowStage(agent="codex", prompt="text", loop=2)

        assert stage.agent == "codex"
        assert stage.prompt == "text"
        assert stage.loop == 2

    def test_loop_accepts_boundary_one(self) -> None:
        """loop == 1 (the minimum) is accepted by the dataclass itself."""
        stage = WorkflowStage(loop=1)

        assert stage.loop == 1

    def test_equality_of_identical_constructions(self) -> None:
        """Two stages with identical fields compare equal."""
        first = WorkflowStage(agent="codex", prompt="text", loop=2)
        second = WorkflowStage(agent="codex", prompt="text", loop=2)

        assert first == second
