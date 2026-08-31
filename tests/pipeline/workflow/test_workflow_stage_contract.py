"""Contract tests for the ``WorkflowStage`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade, the declared properties (``agent``, ``prompt``,
``loop``, ``skills``, ``skip``, ``approve``, ``manual``, ``notes``, ``reflect``,
``memory``), the all-``None`` defaults (``skip`` defaults to ``False``), and
kw_only construction. These tests pin the contract surface — behavior lives in
the logic test module.
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowReflect, WorkflowStage


class TestWorkflowStageContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_stage_importable_from_facade(self) -> None:
        """WorkflowStage must be importable from the goga.pipeline.workflow facade."""
        assert WorkflowStage is not None

    def test_workflow_stage_has_agent_property(self) -> None:
        """WorkflowStage exposes an ``agent`` property."""
        stage = WorkflowStage(agent="codex")

        assert hasattr(stage, "agent")
        assert stage.agent == "codex"

    def test_workflow_stage_has_prompt_property(self) -> None:
        """WorkflowStage exposes a ``prompt`` property."""
        stage = WorkflowStage(prompt="additional instruction")

        assert hasattr(stage, "prompt")
        assert stage.prompt == "additional instruction"

    def test_workflow_stage_has_loop_property(self) -> None:
        """WorkflowStage exposes a ``loop`` property."""
        stage = WorkflowStage(loop=3)

        assert hasattr(stage, "loop")
        assert stage.loop == 3

    def test_workflow_stage_has_skills_property(self) -> None:
        """WorkflowStage exposes a ``skills`` property."""
        stage = WorkflowStage(skills=["web-search"])

        assert hasattr(stage, "skills")
        assert stage.skills == ["web-search"]

    def test_workflow_stage_has_skip_property(self) -> None:
        """WorkflowStage exposes a ``skip`` property defaulting to False."""
        assert hasattr(WorkflowStage(), "skip")
        assert WorkflowStage(skip=True).skip is True

    def test_workflow_stage_has_approve_property(self) -> None:
        """WorkflowStage exposes an ``approve`` property defaulting to None."""
        assert hasattr(WorkflowStage(), "approve")
        assert WorkflowStage(approve="auto").approve == "auto"

    def test_workflow_stage_has_manual_property(self) -> None:
        """WorkflowStage exposes a ``manual`` property defaulting to None (NOT False).

        The property is declared by the workflow-cell CODEMANIFEST as the last
        field of the fixed canonical order; the tri-state default keeps an
        absent key and an explicit ``manual: false`` distinguishable.
        """
        assert hasattr(WorkflowStage(), "manual")
        assert WorkflowStage().manual is None
        assert WorkflowStage(manual=True).manual is True
        assert WorkflowStage(manual=False).manual is False

    def test_workflow_stage_has_notes_property(self) -> None:
        """WorkflowStage exposes a ``notes`` property defaulting to None (NOT {}).

        The ``None`` default pins the "None | non-empty map" model invariant —
        ``parse_workflow`` normalizes an empty map to ``None`` upstream, and a
        mutable ``{}`` default would silently diverge from the ``is not None``
        check the compiler relies on.
        """
        assert hasattr(WorkflowStage(), "notes")
        assert WorkflowStage().notes is None
        assert WorkflowStage(notes={"fix": "F"}).notes == {"fix": "F"}

    def test_workflow_stage_has_reflect_property(self) -> None:
        """WorkflowStage exposes a ``reflect`` property defaulting to None.

        The property carries the optional memory-reflection instruction (a
        :class:`WorkflowReflect`) — declarative, consumed by the compiler to
        emit the stage's ``reflect`` field.
        """
        assert hasattr(WorkflowStage(), "reflect")
        assert WorkflowStage().reflect is None
        assert WorkflowStage(reflect=WorkflowReflect(file="a.md")).reflect == WorkflowReflect(file="a.md")

    def test_workflow_stage_has_memory_property(self) -> None:
        """WorkflowStage exposes a ``memory`` property defaulting to None.

        The property is tri-state in the authoring file but two-valued in the
        model — ``None`` (no instruction) or ``True``; an explicit
        ``memory: false`` is normalized to ``None`` by ``parse_workflow``.
        """
        assert hasattr(WorkflowStage(), "memory")
        assert WorkflowStage().memory is None
        assert WorkflowStage(memory=True).memory is True

    def test_workflow_stage_defaults_all_none(self) -> None:
        """Every field defaults to None when constructed with no arguments."""
        stage = WorkflowStage()

        assert stage.agent is None
        assert stage.prompt is None
        assert stage.loop is None
        assert stage.skills is None
        assert stage.approve is None

    def test_workflow_stage_constructible_kw_only(self) -> None:
        """WorkflowStage accepts all ten fields as keyword-only arguments."""
        stage = WorkflowStage(
            agent="codex",
            prompt="text",
            loop=2,
            skills=["web-search", "goga-propose"],
            skip=True,
            approve="auto",
            manual=True,
            notes={"fix": "Fix and continue"},
            reflect=WorkflowReflect(file="a.md"),
            memory=True,
        )

        assert stage.agent == "codex"
        assert stage.prompt == "text"
        assert stage.loop == 2
        assert stage.skills == ["web-search", "goga-propose"]
        assert stage.skip is True
        assert stage.approve == "auto"
        assert stage.manual is True
        assert stage.notes == {"fix": "Fix and continue"}
        assert stage.reflect == WorkflowReflect(file="a.md")
        assert stage.memory is True
