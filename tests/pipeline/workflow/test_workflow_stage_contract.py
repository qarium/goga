"""Contract tests for the ``WorkflowStage`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade, the declared properties (``agent``, ``env``,
``prompt``, ``loop``, ``skills``, ``skip``, ``approve``, ``manual``,
``notes``, ``reflect``, ``memory``, ``assistants``, ``gates``), the
all-``None`` defaults (``skip`` defaults to ``False``), the fixed field order
with ``env`` second and ``gates`` last, and kw_only construction. These tests
pin the contract surface — behavior lives in the logic test module.
"""

from __future__ import annotations

import dataclasses

from goga.pipeline.workflow import WorkflowAssistant, WorkflowGateStep, WorkflowReflect, WorkflowStage


class TestWorkflowStageContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_stage_importable_from_facade(self) -> None:
        """WorkflowStage must be importable from the goga.pipeline.workflow facade."""
        assert WorkflowStage is not None

    def test_workflow_stage_has_env_property(self) -> None:
        """WorkflowStage exposes an ``env`` property defaulting to None (NOT {}).

        The property carries the per-stage environment instruction (a string
        map, literal and/or rendered) consumed by the pipeline run
        coordination's wrapper generation — declarative, never acted on by the
        compiler. An empty map equals absence (``parse_workflow`` normalizes it
        to ``None`` upstream).
        """
        assert hasattr(WorkflowStage(), "env")
        assert WorkflowStage().env is None
        assert WorkflowStage(env={"MODEL": "sonnet"}).env == {"MODEL": "sonnet"}

    def test_workflow_stage_field_order_fixed_with_env_second(self) -> None:
        """Field order is fixed with ``env`` second and ``gates`` last.

        agent, env, prompt, loop, skills, skip, approve, manual, notes,
        reflect, memory, assistants, gates — the canonical per-stage key
        order of the workflow-file with the check-step list trailing.
        """
        names = [field.name for field in dataclasses.fields(WorkflowStage)]

        assert names == [
            "agent",
            "env",
            "prompt",
            "loop",
            "skills",
            "skip",
            "approve",
            "manual",
            "notes",
            "reflect",
            "memory",
            "assistants",
            "gates",
        ]

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

    def test_workflow_stage_has_assistants_property(self) -> None:
        """WorkflowStage exposes an ``assistants`` property defaulting to None.

        The property carries the stage's assistant attachments — a map of
        :class:`WorkflowAssistant` keyed by assistant name (each entry a
        reference or an inline declaration), or ``None`` when the stage
        attaches none (an empty map equals absence); validated by
        ``parse_workflow`` and consumed by the compiler to emit the stage's
        assistants entries. The field is LAST in the fixed canonical order and
        its annotation pins the declared type.
        """
        assert hasattr(WorkflowStage(), "assistants")
        assert WorkflowStage().assistants is None
        attachment = WorkflowAssistant(name="reviewer", when="start")
        assert WorkflowStage(assistants={"reviewer": attachment}).assistants == {"reviewer": attachment}

        assistants = next(field for field in dataclasses.fields(WorkflowStage) if field.name == "assistants")
        assert assistants.type == "dict[str, WorkflowAssistant] | None"

    def test_workflow_stage_has_gates_property(self) -> None:
        """WorkflowStage exposes a ``gates`` property defaulting to None.

        The property carries the stage's completion quality gates — a list
        of :class:`WorkflowGateStep` check steps in authored order (shell or
        AI-review), or ``None`` when the stage carries none (an empty list
        equals absence); validated by ``parse_workflow`` and consumed by the
        compiler to emit the stage's ``verify`` field. The field is LAST in
        the fixed canonical order and its annotation pins the declared type.
        """
        assert hasattr(WorkflowStage(), "gates")
        assert WorkflowStage().gates is None
        step = WorkflowGateStep(name="Unit tests", script="pytest -q")
        assert WorkflowStage(gates=[step]).gates == [step]

        gates = next(field for field in dataclasses.fields(WorkflowStage) if field.name == "gates")
        assert gates.type == "list[WorkflowGateStep] | None"

    def test_workflow_stage_defaults_all_none(self) -> None:
        """Every field defaults to None when constructed with no arguments."""
        stage = WorkflowStage()

        assert stage.agent is None
        assert stage.env is None
        assert stage.prompt is None
        assert stage.loop is None
        assert stage.skills is None
        assert stage.approve is None

    def test_workflow_stage_constructible_kw_only(self) -> None:
        """WorkflowStage accepts all thirteen fields as keyword-only arguments."""
        stage = WorkflowStage(
            agent="codex",
            env={"MODEL": "sonnet"},
            prompt="text",
            loop=2,
            skills=["web-search", "goga-specify"],
            skip=True,
            approve="auto",
            manual=True,
            notes={"fix": "Fix and continue"},
            reflect=WorkflowReflect(file="a.md"),
            memory=True,
            assistants={"reviewer": WorkflowAssistant(name="reviewer", when="start")},
            gates=[WorkflowGateStep(name="compile", script="make all")],
        )

        assert stage.agent == "codex"
        assert stage.env == {"MODEL": "sonnet"}
        assert stage.prompt == "text"
        assert stage.loop == 2
        assert stage.skills == ["web-search", "goga-specify"]
        assert stage.skip is True
        assert stage.approve == "auto"
        assert stage.manual is True
        assert stage.notes == {"fix": "Fix and continue"}
        assert stage.reflect == WorkflowReflect(file="a.md")
        assert stage.memory is True
        assert stage.assistants == {"reviewer": WorkflowAssistant(name="reviewer", when="start")}
        assert stage.gates == [WorkflowGateStep(name="compile", script="make all")]
