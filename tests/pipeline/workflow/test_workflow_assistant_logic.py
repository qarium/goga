"""Logic tests for the ``WorkflowAssistant`` dataclass.

Covers construction behavior beyond the contract surface: the
absence-preserving defaults (constructing with only ``name`` leaves every
other parameter ``None``), the verbatim round-trip of every authored field,
dataclass equality, and the discriminator premises — a reference-shaped
instance never invents declaration fields (``prompt``/``skills``/``agent``/
``delegate``/``env`` stay ``None``) and a skip-shaped instance carries
nothing but the veto, which is what lets the consumers separate the entry
kinds by presence alone.
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowAssistant


class TestWorkflowAssistantLogic:
    """Logic tests — construction behavior of the ``WorkflowAssistant`` dataclass."""

    def test_workflow_assistant_defaults_are_absence_preserving(self) -> None:
        """Constructing with only ``name`` yields absence on every attachment parameter.

        prompt None, skills None, agent None, delegate None (the
        not-authored, inheritable tri-state value), env None, gate None,
        when None, skip None — absence stays distinguishable from every
        authored value (an authored ``gate: false`` downgrades where an
        absent gate inherits). The pin prevents a silent drift of the
        defaults into the consumers' presence-based discriminators and the
        compiled output.
        """
        assistant = WorkflowAssistant(name="reviewer")

        assert assistant.name == "reviewer"
        assert assistant.prompt is None
        assert assistant.skills is None
        assert assistant.agent is None
        assert assistant.delegate is None
        assert assistant.env is None
        assert assistant.gate is None
        assert assistant.when is None
        assert assistant.skip is None

    def test_skip_shaped_instance_carries_only_the_veto(self) -> None:
        """A ``{skip: true}`` entry shape carries ``skip=True`` and nothing else.

        Every other field stays ``None`` — the veto is pure (no declaration
        content, no attachment parameters), so the consumers discriminate
        it by ``skip is True`` alone, never by truthiness of another field.
        """
        veto = WorkflowAssistant(name="watcher", skip=True)

        assert veto.name == "watcher"
        assert veto.prompt is None
        assert veto.skills is None
        assert veto.agent is None
        assert veto.delegate is None
        assert veto.env is None
        assert veto.gate is None
        assert veto.when is None
        assert veto.skip is True

    def test_workflow_assistant_stores_authored_values_verbatim(self) -> None:
        """Every field round-trips an authored value verbatim (no composition, no rewrite).

        The model is pure data — it stores any authored combination
        (including ``skip`` beside declaration fields); the grammar of
        combinable keys belongs to the parser.
        """
        assistant = WorkflowAssistant(
            name="security",
            prompt="Audit the stage output.",
            skills=["code-audit"],
            agent="codex",
            delegate=True,
            env={"REVIEW_MODE": "strict"},
            gate=True,
            when="finish",
            skip=True,
        )

        assert assistant.name == "security"
        assert assistant.prompt == "Audit the stage output."
        assert assistant.skills == ["code-audit"]
        assert assistant.agent == "codex"
        assert assistant.delegate is True
        assert assistant.env == {"REVIEW_MODE": "strict"}
        assert assistant.gate is True
        assert assistant.when == "finish"
        assert assistant.skip is True

    def test_equality_of_identical_constructions(self) -> None:
        """Two assistants with identical fields compare equal (the dataclass __eq__)."""
        left = WorkflowAssistant(name="reviewer", prompt="Review.")
        right = WorkflowAssistant(name="reviewer", prompt="Review.")

        assert left == right
        assert left != WorkflowAssistant(name="reviewer", prompt="Other.")
        assert left != WorkflowAssistant(name="reviewer", prompt="Review.", skip=True)

    def test_reference_shaped_instance_never_invents_declaration_fields(self) -> None:
        """A reference with attachment overrides keeps all five declaration fields at None.

        The model is one shape for every entry form — a reference carries
        only its own ``gate``/``when`` overrides (never a veto), so the
        consumers' presence-based five-field discriminator (any of
        ``prompt``, ``skills``, ``agent``, ``delegate``, ``env`` authored)
        classifies it as a reference, never a declaration.
        """
        reference = WorkflowAssistant(name="reviewer", gate=True, when="finish")

        assert reference.prompt is None
        assert reference.skills is None
        assert reference.agent is None
        assert reference.delegate is None
        assert reference.env is None
        assert reference.gate is True
        assert reference.when == "finish"
        assert reference.skip is None
