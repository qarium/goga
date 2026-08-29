"""Logic tests for the ``WorkflowStage`` dataclass.

Covers construction behavior beyond the contract surface: all-defaults
construction, partial construction, field independence, and immutability of
the provided values (the dataclass is not frozen, but supplied values must
round-trip unchanged).
"""

from __future__ import annotations

from dataclasses import fields

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

    def test_workflow_stage_skip_defaults_false(self) -> None:
        """skip defaults to False and is read back as a genuine bool."""
        assert WorkflowStage().skip is False
        assert WorkflowStage(agent="codex").skip is False
        assert WorkflowStage(skip=True).skip is True

    def test_field_order_fixed_canonical(self) -> None:
        """Field order is fixed: agent, prompt, loop, skills, skip, approve, manual, notes."""
        names = [field.name for field in fields(WorkflowStage)]

        assert names == ["agent", "prompt", "loop", "skills", "skip", "approve", "manual", "notes"]

    def test_workflow_stage_approve_defaults_none(self) -> None:
        """Omitting ``approve`` yields None — no auto-approval directive."""
        assert WorkflowStage().approve is None
        assert WorkflowStage(agent="codex").approve is None
        assert WorkflowStage(skip=True).approve is None

    def test_workflow_stage_approve_accepts_auto(self) -> None:
        """approve stores ``"auto"`` verbatim (validation lives in parse_workflow)."""
        assert WorkflowStage(approve="auto").approve == "auto"

    def test_workflow_stage_approve_accepts_plan(self) -> None:
        """approve stores ``"plan"`` verbatim (validation lives in parse_workflow)."""
        assert WorkflowStage(approve="plan").approve == "plan"

    def test_workflow_stage_approve_accepts_dialog(self) -> None:
        """approve stores ``"dialog"`` verbatim (validation lives in parse_workflow)."""
        assert WorkflowStage(approve="dialog").approve == "dialog"

    def test_approve_field_order_sixth_final(self) -> None:
        """approve is the 6th field, before manual."""
        names = [field.name for field in fields(WorkflowStage)]

        assert names.index("skip") == 4
        assert names.index("approve") == 5
        assert names.index("manual") == 6

    def test_workflow_stage_manual_defaults_none_not_false(self) -> None:
        """manual defaults to None (NOT False) — absent and explicit false are distinct states.

        ``None`` anchors the tri-state contract: no instruction (the stage's
        body decides the launch mode), ``True`` force, ``False`` explicit
        cancel. ``WorkflowStage(skip=True)`` mirrors the ``apply_skip_stages``
        consumer construction and must keep ``manual`` at ``None``.
        """
        assert WorkflowStage().manual is None
        assert WorkflowStage(skip=True).manual is None
        assert WorkflowStage(manual=True).manual is True
        assert WorkflowStage(manual=False).manual is False

    def test_workflow_stage_notes_defaults_none(self) -> None:
        """Omitting ``notes`` yields None — no note-buttons instruction."""
        assert WorkflowStage().notes is None
        assert WorkflowStage(agent="codex").notes is None

    def test_workflow_stage_notes_stored_verbatim(self) -> None:
        """notes stores the keyword-passed map verbatim (same object, mirroring skills)."""
        notes = {"fix": "F"}
        stage = WorkflowStage(notes=notes)

        assert stage.notes == {"fix": "F"}
        assert stage.notes is notes

    def test_skip_accepts_true_and_false(self) -> None:
        """skip=True and skip=False round-trip verbatim."""
        assert WorkflowStage(skip=True).skip is True
        assert WorkflowStage(skip=False).skip is False

    def test_skip_in_stage_with_other_fields(self) -> None:
        """skip coexists with the other fields without interfering."""
        stage = WorkflowStage(agent="codex", prompt="text", loop=2, skills=["a"], skip=True)

        assert stage.agent == "codex"
        assert stage.prompt == "text"
        assert stage.loop == 2
        assert stage.skills == ["a"]
        assert stage.skip is True

    def test_all_defaults_construction_yields_skip_false(self) -> None:
        """The all-None construction still equals the skip-less construction (skip defaults False)."""
        stage = WorkflowStage()

        assert stage == WorkflowStage(agent=None, prompt=None, loop=None, skills=None)
        assert stage.skip is False
