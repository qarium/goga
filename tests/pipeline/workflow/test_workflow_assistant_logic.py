"""Logic tests for the ``WorkflowAssistant`` dataclass.

Covers construction behavior beyond the contract surface: the materialized
defaults (values, not omissions), the verbatim round-trip of every authored
field, dataclass equality, and the discriminator premise — a reference-shaped
instance never invents declaration fields (``prompt``/``skills`` stay
``None``), which is what lets the consumers separate a reference from an
inline declaration by presence alone.
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowAssistant


class TestWorkflowAssistantLogic:
    """Logic tests — construction behavior of the ``WorkflowAssistant`` dataclass."""

    def test_workflow_assistant_defaults_are_materialized(self) -> None:
        """Constructing with only ``name`` yields the materialized authoring defaults.

        prompt None, skills None, agent None, delegate False, env None, gate
        False, when "checkpoints" — the values a bare stage reference carries
        after parsing. The pin prevents a silent drift of the defaults into
        the consumers' declaration discriminator and the compiled output.
        """
        assistant = WorkflowAssistant(name="reviewer")

        assert assistant.name == "reviewer"
        assert assistant.prompt is None
        assert assistant.skills is None
        assert assistant.agent is None
        assert assistant.delegate is False
        assert assistant.env is None
        assert assistant.gate is False
        assert assistant.when == "checkpoints"

    def test_workflow_assistant_stores_authored_values_verbatim(self) -> None:
        """Every field round-trips an authored declaration verbatim (no composition, no rewrite)."""
        assistant = WorkflowAssistant(
            name="security",
            prompt="Audit the stage output.",
            skills=["code-audit"],
            agent="codex",
            delegate=True,
            env={"REVIEW_MODE": "strict"},
            gate=True,
            when="finish",
        )

        assert assistant.name == "security"
        assert assistant.prompt == "Audit the stage output."
        assert assistant.skills == ["code-audit"]
        assert assistant.agent == "codex"
        assert assistant.delegate is True
        assert assistant.env == {"REVIEW_MODE": "strict"}
        assert assistant.gate is True
        assert assistant.when == "finish"

    def test_equality_of_identical_constructions(self) -> None:
        """Two assistants with identical fields compare equal (the dataclass __eq__)."""
        left = WorkflowAssistant(name="reviewer", prompt="Review.")
        right = WorkflowAssistant(name="reviewer", prompt="Review.")

        assert left == right
        assert left != WorkflowAssistant(name="reviewer", prompt="Other.")

    def test_reference_shaped_instance_never_invents_declaration_fields(self) -> None:
        """A reference with attachment overrides keeps ``prompt`` and ``skills`` at None.

        The model is one shape for all three entry forms — a reference
        carries only its own ``gate``/``when`` overrides, so the consumers'
        presence-based discriminator (``prompt is not None or skills is not
        None``) classifies it as a reference, never a declaration.
        """
        reference = WorkflowAssistant(name="reviewer", gate=True, when="finish")

        assert reference.prompt is None
        assert reference.skills is None
        assert reference.gate is True
        assert reference.when == "finish"
