"""Contract and logic tests for the ``compile_flow`` collaboration emission (step 4.10).

Covers the collaboration half of the compiler: the always-emitted top-level
``collaboration`` block, the ``team`` list, and the per-stage ``assistants``
entries —

- the block is constructed on EVERY compilation (mode ``assistants``;
  ``max_depth`` from the delegation block, omitted when absent);
- the team list carries one member per catalog entry in authored order, and
  is empty (key omitted) when the workflow carries no catalog;
- attachments resolve against the assistant namespace (catalog plus inline
  declarations of every stage): a REFERENCE takes the declaration's
  ``prompt`` while keeping its OWN ``gate``/``when`` (the entry carries no
  ``skills`` — the engine rejects the key on stage entries);
- the four attachment checks fire in contract order — unknown reference,
  duplicate name in one stage list, attachment on a script stage,
  attachment on a planning-only stage (the translated-agents comparison —
  an authored ``roles: [planning]`` equals ``[planner]``);
- loop-expanded copies share one attachment list (uniform across copies);
- an authored ``assistants`` key in a stage body is a structural error;
- an extend-seeded stage with a stages-block entry keeps its attachments
  (the C2.4 regression guard);
- skipped stages are removed before the attachment walk (no checks, no ids);
- a collaboration-free workflow compiles byte-identically to the pre-change
  output except for the inserted two-line block.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest
from goga.pipeline.compiler import (
    FlowAssistant,
    FlowCollaboration,
    FlowDocument,
    PipelineDocument,
    StructuralError,
    compile_flow,
)
from goga.pipeline.compiler.compile_flow import (
    _CANONICAL_KEY_ORDER,
    _canonical_fields,
)
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowStage,
    parse_workflow,
)

# Base STAGES-format pipeline-file for the compiler tests — two stages.
_BASE_STAGES = (
    "name: demo\n"
    "description: Demo pipeline\n"
    "---\n"
    "build:\n"
    "  title: Build\n"
    "  prompt: Make\n"
    "review:\n"
    "  title: Review\n"
    "  prompt: Check\n"
)


def _compile(
    tmp_path: Path,
    pipeline_text: str,
    workflow_text: str | None = None,
) -> tuple[PipelineDocument, FlowDocument, str]:
    """Write the pipeline (and optional workflow), compile, return documents + text.

    Mirrors the ``_compile`` helper of ``test_compile_flow_memory.py`` so the
    collaboration tests can assert on the assembled ``FlowDocument`` and the
    written flow-file text.
    """
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(pipeline_text)
    flow_path = tmp_path / "flow.yml"

    workflow = None

    if workflow_text is not None:
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(workflow_text)
        workflow = parse_workflow(workflow_path.read_text())

    pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

    return pipeline_doc, flow_doc, flow_path.read_text()


class TestCompileFlowCollaborationContract:
    """Contract tests — the collaboration surface declared by the compiler CODEMANIFEST."""

    def test_compile_flow_accepts_assistant_blocks(self, tmp_path: Path) -> None:
        """A workflow carrying the catalog, delegation, and attachments compiles cleanly."""
        _pipeline_doc, flow_doc, _text = _compile(
            tmp_path,
            _BASE_STAGES,
            "assistants:\n"
            "  - name: reviewer\n"
            "    prompt: Review.\n"
            "    skills: [code-audit]\n"
            "delegation:\n"
            "  depth: 2\n"
            "stages:\n"
            "  build:\n"
            "    assistants: [reviewer]\n",
        )

        assert flow_doc.collaboration == FlowCollaboration(mode="assistants", max_depth=2)

    def test_collaboration_block_on_every_compile(self, tmp_path: Path) -> None:
        """The workflow-less compile still carries the collaboration block."""
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES)

        assert flow_doc.collaboration == FlowCollaboration(mode="assistants", max_depth=None)
        assert "collaboration:\n  mode: assistants\n" in text

    def test_authored_assistants_key_in_stage_body_rejected(self, tmp_path: Path) -> None:
        """An authored ``assistants`` key in a stage body raises the pinned prohibition."""
        pipeline_text = (
            "name: demo\n"
            "description: Demo pipeline\n"
            "---\n"
            "build:\n"
            "  title: Build\n"
            "  prompt: Make\n"
            "  assistants:\n"
            "  - profile: goga-reviewer\n"
        )

        with pytest.raises(
            StructuralError,
            match=re.escape("assistants key is forbidden in stage body; use assistants in workflow.stages"),
        ):
            _compile(tmp_path, pipeline_text)

    def test_canonical_key_order_ends_with_assistants(self) -> None:
        """``assistants`` closes the canonical order after ``memory_use``."""
        assert _CANONICAL_KEY_ORDER[-3:] == ["reflect", "memory_use", "assistants"]
        assert _CANONICAL_KEY_ORDER.index("assistants") == _CANONICAL_KEY_ORDER.index("memory_use") + 1

    def test_canonical_fields_accepts_assistants_fields(self) -> None:
        """``_canonical_fields`` takes ``(body, stage_name, notes, memory_fields, assistants_fields)``."""
        parameters = list(inspect.signature(_canonical_fields).parameters)

        assert parameters == ["body", "stage_name", "notes", "memory_fields", "assistants_fields"]
        assert inspect.signature(_canonical_fields).parameters["assistants_fields"].default is None

    def test_collaboration_helpers_not_on_facade(self) -> None:
        """``_collaboration_emission`` & co. are module-internal, not facade names."""
        from goga.pipeline.compiler import __all__ as facade_all

        assert "_collaboration_emission" not in facade_all
        assert "_CollaborationEmission" not in facade_all
        assert "_assistant_namespace" not in facade_all
        assert "_assemble_assistants" not in facade_all

    def test_workflow_document_default_catalog_is_empty(self) -> None:
        """A default ``WorkflowDocument`` carries an empty catalog and no delegation."""
        document = WorkflowDocument(prompt="p", stages={"build": WorkflowStage()})

        assert document.assistants == {}
        assert document.delegation is None


class TestCollaborationBlockEmission:
    """Step 4.10 block — emitted on every compilation, delegation-fed when authored."""

    def test_compile_collaboration_block_always_emitted(self, tmp_path: Path) -> None:
        """A workflow-less compile still writes the block — and nothing else changes."""
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES)

        assert flow_doc.collaboration == FlowCollaboration(mode="assistants", max_depth=None)
        assert "collaboration:\n  mode: assistants\n" in text
        assert "max_depth" not in text
        assert "team:" not in text

        # The remainder is byte-identical to the pre-change golden — remove
        # the two inserted lines and compare.
        stripped = text.replace("collaboration:\n  mode: assistants\n", "")
        assert stripped == (
            "name: demo\n"
            "description: Demo pipeline\n"
            "stages:\n"
            "- id: build\n"
            "  name: Build\n"
            "  prompt: Make\n"
            "  agents: [auto]\n"
            "- id: review\n"
            "  name: Review\n"
            "  prompt: Check\n"
            "  agents: [auto]\n"
        )

    def test_compile_delegation_depth_zero_survives_to_max_depth_zero(self, tmp_path: Path) -> None:
        """An authored ``depth: 0`` is a VALUE — the flow-file carries ``max_depth: 0``."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            _BASE_STAGES,
            "delegation:\n  depth: 0\nstages:\n  build:\n    skip: false\n",
        )

        assert flow_doc.collaboration == FlowCollaboration(mode="assistants", max_depth=0)
        assert "max_depth: 0" in text

    def test_compile_collaboration_free_workflow_byte_identical_except_mode(self, tmp_path: Path) -> None:
        """A workflow without collaboration surfaces gains exactly the two-line block."""
        pipeline_text = (
            "name: T\n"
            "description: D\n"
            "---\n"
            "a:\n"
            "  title: A\n"
            "  communication: true\n"
            "  roles:\n"
            "    - planner\n"
            "  prompt: p\n"
            "b:\n"
            "  title: B\n"
            "  depends_on: [a]\n"
            "  prompt: q\n"
        )

        workflow_text = "prompt: Use this.\nstages:\n  a:\n    agent: coder\n"
        _pipeline_doc, flow_doc, text = _compile(tmp_path, pipeline_text, workflow_text)

        assert flow_doc.collaboration == FlowCollaboration(mode="assistants", max_depth=None)
        assert flow_doc.team == []
        # The pre-change golden with exactly the collaboration block inserted
        # after ``description`` (no memory block in this pair).
        assert text == (
            "prompt: |-\n"
            "  Use this.\n"
            "name: T\n"
            "description: D\n"
            "collaboration:\n"
            "  mode: assistants\n"
            "stages:\n"
            "- id: a\n"
            "  name: A\n"
            "  interactive: true\n"
            "  command: /home/goga/bin/coder-as-claude.sh\n"
            "  prompt: p\n"
            "  agents: [planning]\n"
            "- id: b\n"
            "  name: B\n"
            "  prompt: q\n"
            "  agents: [auto]\n"
            "  depends_on:\n"
            "  - a\n"
        )


class TestTeamAndAttachmentMaterialization:
    """Steps 4.10 / 5 / 6 — the team list and the per-stage attachment entries."""

    def test_compile_team_and_stage_attachments_full_materialization(self, tmp_path: Path) -> None:
        """Catalog + delegation + gated attachment compile into team, block, and entries."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            "name: demo\ndescription: Demo pipeline\n---\nbuild:\n  title: Build\n  prompt: Make\n",
            "assistants:\n"
            "  - name: reviewer\n"
            "    prompt: Review.\n"
            "    skills: [code-audit]\n"
            "delegation:\n"
            "  depth: 2\n"
            "memory:\n"
            "  path: shared.md\n"
            "stages:\n"
            "  build:\n"
            "    reflect:\n"
            "      file: build.md\n"
            "    assistants:\n"
            "      - name: reviewer\n"
            "        gate: true\n"
            "        when: finish\n",
        )

        assert "max_depth: 2" in text
        assert (
            "team:\n"
            "- id: reviewer\n"
            "  title: reviewer\n"
            "  profile: goga-reviewer\n"
            "  instruction: Review.\n"
            "  skills:\n"
            "  - code-audit\n" in text
        )
        # The attachment entry slots after the memory/reflect keys of the stage —
        # no skills key on the entry (the engine rejects it there).
        assert (
            "  reflect:\n"
            "    file: build.md\n"
            "    mode: rw\n"
            "  assistants:\n"
            "  - profile: goga-reviewer\n"
            "    title: reviewer\n"
            "    instruction: Review.\n"
            "    mode: required\n"
            "    trigger: on_completion\n" in text
        )
        assert flow_doc.stages[0].fields["assistants"][0].trigger == "on_completion"

    def test_compile_reference_takes_declaration_fields_keeps_own_gate_when(self, tmp_path: Path) -> None:
        """A reference resolves against the catalog but keeps its own gate/when."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            _BASE_STAGES,
            "assistants:\n"
            "  - name: reviewer\n"
            "    prompt: Review.\n"
            "    skills: [code-audit]\n"
            "stages:\n"
            "  build:\n"
            "    assistants:\n"
            "      - name: reviewer\n"
            "        gate: true\n"
            "        when: finish\n",
        )

        entry = flow_doc.stages[0].fields["assistants"][0]

        assert entry.instruction == "Review."
        assert entry.mode == "required"
        assert entry.trigger == "on_completion"
        assert "trigger: on_completion" in text

    def test_compile_reference_to_inline_declaration_of_another_stage(self, tmp_path: Path) -> None:
        """A reference may name an inline declaration authored on another stage."""
        _pipeline_doc, flow_doc, _text = _compile(
            tmp_path,
            _BASE_STAGES,
            "stages:\n"
            "  build:\n"
            "    assistants:\n"
            "      - name: security\n"
            "        prompt: Guard.\n"
            "        skills: [sec-audit]\n"
            "  review:\n"
            "    assistants: [security]\n",
        )

        build_entry = flow_doc.stages[0].fields["assistants"][0]
        review_entry = flow_doc.stages[1].fields["assistants"][0]

        assert build_entry.profile == "goga-security"
        assert build_entry.instruction == "Guard."
        assert review_entry.profile == "goga-security"
        assert review_entry.instruction == "Guard."
        # The reference keeps its own gate/when defaults, not the declaration's.
        assert review_entry.mode == "advisory"
        assert review_entry.trigger == "checkpoints"
        # An inline declaration never joins the team list.
        assert flow_doc.team == []

    def test_compile_attachments_uniform_across_loop_copies(self, tmp_path: Path) -> None:
        """Loop-expanded copies share identical attachment entries — one profile per name."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            _BASE_STAGES,
            "assistants:\n"
            "  - name: reviewer\n"
            "    prompt: Review.\n"
            "stages:\n"
            "  build:\n"
            "    loop: 3\n"
            "    assistants: [reviewer]\n",
        )

        assert [stage.id for stage in flow_doc.stages] == ["build-1", "build-2", "build-3", "review"]
        for stage in flow_doc.stages[:3]:
            assert stage.fields["assistants"] == [
                _expected_entry("reviewer", "Review."),
            ]

        stages_text = text.split("stages:")[1]
        assert stages_text.count("profile: goga-reviewer") == 3
        # Exactly one team member — the config side collapses the three refs.
        assert text.count("- id: reviewer\n") == 1

    def test_compile_extend_seeded_stage_keeps_stages_block_attachments(self, tmp_path: Path) -> None:
        """C2.4 — a stage with BOTH an extend-entry and a stages-block entry keeps its attachments."""
        _pipeline_doc, flow_doc, _text = _compile(
            tmp_path,
            _BASE_STAGES,
            "assistants:\n"
            "  - name: reviewer\n"
            "    prompt: Review.\n"
            "extend:\n"
            "  extra:\n"
            "    after: [build]\n"
            "    title: Extra\n"
            "    prompt: Added\n"
            "stages:\n"
            "  extra:\n"
            "    assistants: [reviewer]\n",
        )

        assert [stage.id for stage in flow_doc.stages] == ["build", "review", "extra"]
        assert "assistants" in flow_doc.stages[2].fields
        assert flow_doc.stages[2].fields["assistants"][0].title == "reviewer"

    def test_compile_when_start_maps_to_one_shot(self, tmp_path: Path) -> None:
        """``when: start`` compiles to the engine's ``one_shot`` engagement."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            _BASE_STAGES,
            "assistants:\n"
            "  - name: reviewer\n"
            "    prompt: Review.\n"
            "stages:\n"
            "  build:\n"
            "    assistants:\n"
            "      - name: reviewer\n"
            "        when: start\n",
        )

        entry = flow_doc.stages[0].fields["assistants"][0]

        assert entry.trigger == "one_shot"
        assert "trigger: one_shot" in text

    def test_compile_skills_only_catalog_member_materializes_empty_instruction(self, tmp_path: Path) -> None:
        """A skills-only catalog member compiles — team ``instruction: ''``, skills verbatim."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            _BASE_STAGES,
            "assistants:\n  - name: auditor\n    skills: [code-audit]\nstages:\n  build:\n    assistants: [auditor]\n",
        )

        member = flow_doc.team[0]

        assert member.id == "auditor"
        assert member.instruction == ""
        assert member.skills == ["code-audit"]
        assert "  instruction: ''\n  skills:\n  - code-audit\n" in text

        entry = flow_doc.stages[0].fields["assistants"][0]

        assert entry.instruction == ""
        assert entry.trigger == "checkpoints"

    def test_compile_phases_format_emits_stage_attachments(self, tmp_path: Path) -> None:
        """A PHASES-format pipeline carries the attachment entries like STAGES does."""
        pipeline_text = (
            "name: demo\n"
            "description: Demo pipeline\n"
            "---\n"
            "- name: build\n"
            "  title: Build\n"
            "  prompt: Make\n"
            "- name: review\n"
            "  title: Review\n"
            "  prompt: Check\n"
        )
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            pipeline_text,
            "assistants:\n  - name: reviewer\n    prompt: Review.\nstages:\n  review:\n    assistants: [reviewer]\n",
        )

        assert [stage.id for stage in flow_doc.stages] == ["build", "review"]
        assert flow_doc.stages[1].fields["assistants"] == [
            _expected_entry("reviewer", "Review."),
        ]
        assert "profile: goga-reviewer" in text


class TestAttachmentChecks:
    """The four attachment checks of step 4.10 — contract order, pinned messages."""

    def test_compile_unknown_reference_raises(self, tmp_path: Path) -> None:
        """A reference naming no namespace member is rejected."""
        with pytest.raises(
            StructuralError,
            match=re.escape("unknown assistant reference in workflow.stages.build: ghost"),
        ):
            _compile(tmp_path, _BASE_STAGES, "stages:\n  build:\n    assistants: [ghost]\n")

    def test_compile_duplicate_same_stage_raises(self, tmp_path: Path) -> None:
        """The same name twice in one stage list is rejected — both variants."""
        workflow_catalog = "assistants:\n  - name: reviewer\n    prompt: Review.\n"
        with pytest.raises(
            StructuralError,
            match=re.escape("duplicate assistant in workflow.stages.build: reviewer"),
        ):
            _compile(
                tmp_path,
                _BASE_STAGES,
                workflow_catalog + "stages:\n  build:\n    assistants: [reviewer, reviewer]\n",
            )

        with pytest.raises(
            StructuralError,
            match=re.escape("duplicate assistant in workflow.stages.build: reviewer"),
        ):
            _compile(
                tmp_path,
                _BASE_STAGES,
                "stages:\n"
                "  build:\n"
                "    assistants:\n"
                "      - reviewer\n"
                "      - name: reviewer\n"
                "        prompt: Review.\n",
            )

    def test_compile_script_and_planning_only_rejected(self, tmp_path: Path) -> None:
        """Attachments are forbidden on script and planning-only stages."""
        workflow_text = "stages:\n  build:\n    assistants:\n      - name: r\n        prompt: P\n"
        pipeline_script = "name: demo\ndescription: D\n---\nbuild:\n  title: Build\n  script: echo hi\n"
        pipeline_planner = "name: demo\ndescription: D\n---\nbuild:\n  title: Build\n  roles: [planner]\n"
        pipeline_planning = "name: demo\ndescription: D\n---\nbuild:\n  title: Build\n  roles: [planning]\n"

        with pytest.raises(
            StructuralError,
            match=re.escape("assistant is forbidden on a script stage in workflow.stages.build: r"),
        ):
            _compile(tmp_path, pipeline_script, workflow_text)

        with pytest.raises(
            StructuralError,
            match=re.escape("assistant is forbidden on a planning-only stage in workflow.stages.build: r"),
        ):
            _compile(tmp_path, pipeline_planner, workflow_text)

        # An authored afm-side ``roles: [planning]`` equals the alias — the
        # comparison is TRANSLATED.
        with pytest.raises(
            StructuralError,
            match=re.escape("assistant is forbidden on a planning-only stage in workflow.stages.build: r"),
        ):
            _compile(tmp_path, pipeline_planning, workflow_text)

    def test_compile_non_str_roles_with_attachment_raises_structural_error(self, tmp_path: Path) -> None:
        """A verbatim non-str roles element raises the clean error even with an attachment.

        The attachment checks run BEFORE the ``_inject_defaults`` translation
        pass that guards ``roles`` — without the mirrored guard in the
        attachment walk, a mapping element would surface as a raw
        ``TypeError`` from the alias lookup instead of the pinned
        ``StructuralError``.
        """
        pipeline_text = "name: demo\ndescription: D\n---\nbuild:\n  title: Build\n  roles: [{}]\n"
        workflow_text = "stages:\n  build:\n    assistants:\n      - name: r\n        prompt: P\n"

        with pytest.raises(
            StructuralError,
            match=re.escape("non-str value in stage roles list: {}"),
        ):
            _compile(tmp_path, pipeline_text, workflow_text)

    def test_compile_skipped_stage_attachments_never_checked(self, tmp_path: Path) -> None:
        """A skipped stage is removed before the walk — even a dangling reference is silent."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            _BASE_STAGES,
            "stages:\n  review:\n    skip: true\n    assistants: [ghost]\n",
        )

        assert [stage.id for stage in flow_doc.stages] == ["build"]
        assert "ghost" not in text
        assert flow_doc.collaboration == FlowCollaboration(mode="assistants", max_depth=None)


def _expected_entry(name: str, instruction: str) -> FlowAssistant:
    """Build the expected attachment entry for a default gate/when reference."""
    return FlowAssistant(
        profile=f"goga-{name}",
        title=name,
        instruction=instruction,
        mode="advisory",
        trigger="checkpoints",
    )
