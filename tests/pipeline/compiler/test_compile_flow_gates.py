"""Contract and logic tests for the ``compile_flow`` gates emission (step 4.11).

Covers the gates half of the compiler: when the supplied workflow authors
per-stage check steps, ``compile_flow`` translates them into the engine's
stage-completion gate — the ``verify`` field of the flow-file —

- one ``FlowVerifyStep`` per authored ``WorkflowGateStep``, in authored
  order: ``script`` → ``run`` with the timeout materialized to ``1h`` when
  not authored; ``agent`` → ``command`` composed into the in-container
  wrapper path (no agent-name existence check, no host-side resolution);
  ``name``/``prompt``/an authored ``timeout`` carried verbatim; an AI step
  materializes no timeout default;
- the settings ride only on gated stages and only when the workflow-level
  ``gates`` block authored any key (``patience`` → ``review_patience``,
  ``max_iterations`` → ``max_failures``, ``fresh_correction`` unchanged) —
  with no settings block authored the verify value is the list form;
- the settings block without per-stage steps is inert (no verify key
  anywhere, no error);
- the ``verify`` key occupies the canonical fields slot after ``assistants``
  and is uniform across every loop-expanded copy (the same gate object
  mapped onto every produced id);
- gates on a script stage and on a planning-only stage (translated agents
  exactly ``["planning"]``) are strict pre-run errors naming the stage —
  checked once per stage name on the original, after skip removal (the
  gates of a skipped stage drop silently);
- a check step carrying both or neither of ``script``/``agent``, or
  carrying ``prompt`` alongside ``script``, fails the compile with the
  parser's message — authored files hit the parser's own checks first, but
  a programmatic workflow (the tool-contribution path bypasses
  ``parse_workflow``) can reach the compiler with a degenerate step, and
  the guard fires instead of composing a ``None``-agent wrapper path or
  emitting a ``run``+``prompt`` step the engine rejects at load;
- an empty gates list equals absence — authored emptiness normalizes at
  parse, and an empty programmatic list (a tool contribution carries it
  verbatim through the overlay merge) emits no verify key and fires no
  body check;
- a stage failing both an attachment check (4.10) and a gates check (4.11)
  reports the attachment error — the emission order is deterministic;
- an authoring ``gates`` key and a raw ``verify`` key in a stage body
  (pipeline-file stage OR embedded extend-stage body) are strict compile
  errors — ``verify`` is a compiled-only key, authored through
  ``workflow.stages``;
- a gate-free workflow compiles byte-identically (no verify key anywhere);
- the effective-override merge passes the stages-block gates explicitly —
  a stage carrying BOTH an extend-entry and a stages-block entry keeps its
  gate;
- output-side only — the source bodies and the ``PipelineDocument`` mirror
  stay untouched.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest
from goga.pipeline.compiler import (
    FlowVerify,
    PipelineDocument,
    StructuralError,
    compile_flow,
)
from goga.pipeline.compiler.compile_flow import (
    _CANONICAL_KEY_ORDER,
    _assemble_verify,
    _canonical_fields,
    _effective_overrides,
    _gates_emission,
)
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowGateStep,
    WorkflowStage,
    parse_workflow,
)

# Base STAGES-format pipeline-file for the compiler tests — three stages,
# verbatim from the design.
_BASE_STAGES = (
    "name: demo\n"
    "description: Demo pipeline\n"
    "---\n"
    "brainstorm:\n"
    "  title: Brainstorm\n"
    "  prompt: Think\n"
    "build:\n"
    "  title: Build\n"
    "  prompt: Make\n"
    "review:\n"
    "  title: Review\n"
    "  prompt: Check\n"
)

# Repeatable base — the byte-identical golden rides the repeat block so the
# guard covers the whole top-level emission too.
_BASE_STAGES_REPEATABLE = (
    "name: demo\n"
    "description: Demo pipeline\n"
    "repeatable: true\n"
    "---\n"
    "brainstorm:\n"
    "  title: Brainstorm\n"
    "  prompt: Think\n"
    "build:\n"
    "  title: Build\n"
    "  prompt: Make\n"
    "review:\n"
    "  title: Review\n"
    "  prompt: Check\n"
)

# The full-string golden of the gate-free compilation (captured against the
# pre-feature output in the REPL): a workflow carrying a top-level prompt, a
# repeat block, a per-stage agent override, and a notes instruction — every
# companion emission active, no gate anywhere. Byte-identical means exactly
# this text.
_GATE_FREE_GOLDEN = (
    "prompt: |-\n"
    "  Ship it.\n"
    "name: demo\n"
    "description: Demo pipeline\n"
    "repeat:\n"
    "  max_cycles: 3\n"
    "collaboration:\n"
    "  mode: assistants\n"
    "stages:\n"
    "- id: brainstorm\n"
    "  name: Brainstorm\n"
    "  prompt: Think\n"
    "  agents: [auto]\n"
    "- id: build\n"
    "  name: Build\n"
    "  command: /home/goga/bin/codex-as-claude.sh\n"
    "  prompt: Make\n"
    "  buttons:\n"
    "    deploy: Ship the artifact.\n"
    "  agents: [auto]\n"
    "- id: review\n"
    "  name: Review\n"
    "  prompt: Check\n"
    "  agents: [auto]\n"
)

_GATE_FREE_WORKFLOW = (
    "prompt: Ship it.\n"
    "repeat:\n"
    "  max_cycles: 3\n"
    "stages:\n"
    "  build:\n"
    "    agent: codex\n"
    "    notes:\n"
    "      deploy: Ship the artifact.\n"
)


def _compile(
    tmp_path: Path,
    pipeline_text: str,
    workflow_text: str | None = None,
) -> tuple[PipelineDocument, object, str]:
    """Write the pipeline (and optional workflow), compile, return documents + text.

    Mirrors the ``_compile`` helper of ``test_compile_flow_memory.py``; the
    gates tests assert on the serialized text and on the returned
    ``FlowDocument`` stages.
    """
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(pipeline_text)
    flow_path = tmp_path / "flow.yml"

    workflow = None

    if workflow_text is not None:
        workflow = parse_workflow(workflow_text)

    pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

    return pipeline_doc, flow_doc, flow_path.read_text()


class TestCompileFlowGatesContract:
    """Contract tests — the gates surface declared by the compiler CODEMANIFEST."""

    def test_compile_flow_signature_unchanged_no_gates_parameter(self) -> None:
        """``compile_flow`` keeps its five parameters — gates travel inside ``WorkflowDocument``."""
        parameters = list(inspect.signature(compile_flow).parameters)

        assert parameters == ["pipeline_path", "flow_path", "workflow", "root_dir", "project_name"]

    def test_gates_helpers_not_on_facade(self) -> None:
        """``_gates_emission`` & co. are module-internal, not facade names."""
        from goga.pipeline.compiler import __all__ as facade_all

        assert "_gates_emission" not in facade_all
        assert "_assemble_verify" not in facade_all

    def test_gates_helpers_exist_in_module(self) -> None:
        """The step-4.11 helpers exist with the contract shape."""
        assert callable(_gates_emission)
        assert callable(_assemble_verify)

    def test_canonical_key_order_ends_with_verify_slot(self) -> None:
        """``verify`` is the LAST canonical slot, immediately after ``assistants``."""
        assert _CANONICAL_KEY_ORDER[-1] == "verify"
        assert _CANONICAL_KEY_ORDER.index("verify") == _CANONICAL_KEY_ORDER.index("assistants") + 1
        assert _CANONICAL_KEY_ORDER.index("assistants") == _CANONICAL_KEY_ORDER.index("memory_use") + 1

    def test_canonical_fields_accepts_verify_fields(self) -> None:
        """``_canonical_fields`` gains the trailing ``verify_fields`` parameter (default None)."""
        parameters = list(inspect.signature(_canonical_fields).parameters)

        assert parameters == ["body", "stage_name", "notes", "memory_fields", "assistants_fields", "verify_fields"]
        assert inspect.signature(_canonical_fields).parameters["verify_fields"].default is None


class TestCompileFlowGatesEmission:
    """Step 4.11 / 5 — the verify emission and its slot across the authored forms."""

    def test_gated_stage_compiles_verify_with_steps_and_materialized_timeout(self, tmp_path: Path) -> None:
        """A shell gate step compiles to the list form with the ``1h`` timeout default."""
        workflow_text = "stages:\n  build:\n    gates:\n      - name: compile\n        script: make all\n"
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        build_stage = next(stage for stage in flow_doc.stages if stage.id == "build")
        verify = build_stage.fields["verify"]

        assert "verify:\n" in text
        assert "  - name: compile\n" in text
        assert "    run: make all\n" in text
        assert "    timeout: 1h\n" in text
        assert text.index("verify:") > text.index("prompt:")
        assert "max_failures" not in text
        assert "steps:" not in text
        assert isinstance(verify, FlowVerify)
        assert verify.steps[0].name == "compile"
        assert verify.steps[0].run == "make all"
        assert verify.steps[0].command is None
        assert verify.steps[0].timeout == "1h"
        assert verify.max_failures is None
        assert verify.review_patience is None
        assert verify.fresh_correction is None

    def test_list_form_gate_script_compiles_to_joined_run(self, tmp_path: Path) -> None:
        """A list-form gate ``script`` compiles to the newline-joined multi-line ``run``.

        The parser joins the authored lines into one script string, so the
        emitted shell step carries the same multi-line payload a block
        scalar authors — serialized as a block literal.
        """
        workflow_text = (
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: checks\n"
            "        script:\n"
            "          - pytest ./\n"
            "          - ruff check .\n"
        )
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        build_stage = next(stage for stage in flow_doc.stages if stage.id == "build")
        verify = build_stage.fields["verify"]

        assert verify.steps[0].run == "pytest ./\nruff check ."
        assert "    run: |-\n      pytest ./\n      ruff check ." in text

    def test_ai_step_command_composed_from_agent_wrapper_path(self, tmp_path: Path) -> None:
        """An AI gate step composes the wrapper-path command and keeps its authored fields verbatim."""
        workflow_text = (
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: Check\n"
            "        agent: codex\n"
            "        prompt: Be strict.\n"
            "        timeout: 15m\n"
        )
        _pipeline_doc, _flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert "- name: Check\n" in text
        assert "command: /home/goga/bin/codex-as-claude.sh\n" in text
        assert "timeout: 15m\n" in text
        assert "prompt: 'Be strict.'\n" in text or "prompt: Be strict.\n" in text
        # The authored timeout rides verbatim — the shell default never fires on an AI step.
        assert "timeout: 1h" not in text

    def test_ai_step_materializes_no_timeout_default(self, tmp_path: Path) -> None:
        """An AI gate step without an authored timeout carries no timeout key at all."""
        workflow_text = (
            "stages:\n  build:\n    gates:\n      - name: Review\n        agent: codex\n        prompt: Check.\n"
        )
        _pipeline_doc, _flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert "timeout:" not in text

    def test_settings_block_authors_container_form_on_every_gated_stage(self, tmp_path: Path) -> None:
        """An authored settings key switches EVERY gated stage to the container form."""
        workflow_text = (
            "gates:\n"
            "  max_iterations: 2\n"
            "  fresh_correction: true\n"
            "stages:\n"
            "  brainstorm:\n"
            "    gates:\n"
            "      - name: unit\n"
            "        script: pytest -q\n"
            "  review:\n"
            "    gates:\n"
            "      - name: lint\n"
            "        script: ruff check .\n"
        )
        _pipeline_doc, _flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert text.count("steps:\n") == 2
        assert "max_failures: 2\n" in text
        assert "fresh_correction: true\n" in text
        assert "review_patience" not in text

    def test_loop_expanded_copies_carry_the_same_gate(self, tmp_path: Path) -> None:
        """Every loop-expanded copy ``NAME-i`` carries its base's gate — uniform across copies."""
        workflow_text = "stages:\n  review:\n    loop: 2\n    gates:\n      - name: tests\n        script: pytest -q\n"
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        copies = [stage for stage in flow_doc.stages if stage.id.startswith("review")]

        assert text.count("verify:\n") == 2
        assert "- id: review-1\n" in text
        assert "- id: review-2\n" in text
        assert len(copies) == 2
        assert copies[0].fields["verify"] == copies[1].fields["verify"]

    def test_settings_block_alone_compiles_inert(self, tmp_path: Path) -> None:
        """A settings block without per-stage steps emits nothing — no verify key, no error."""
        _pipeline_doc, _flow_doc, text = _compile(tmp_path, _BASE_STAGES, "gates:\n  patience: 2\n")

        assert "verify" not in text

    def test_phases_gated_stage_carries_verify(self, tmp_path: Path) -> None:
        """The PHASES list body emits the gate identically — format-agnostic."""
        pipeline_text = "name: demo\ndescription: Demo pipeline\n---\n- name: build\n  title: Build\n  prompt: Make\n"
        workflow_text = "stages:\n  build:\n    gates:\n      - name: compile\n        script: make all\n"
        _pipeline_doc, flow_doc, text = _compile(tmp_path, pipeline_text, workflow_text)

        assert "verify:\n" in text
        assert flow_doc.stages[0].fields["verify"].steps[0].run == "make all"


class TestCompileFlowGatesRejections:
    """Step 4.11 — the gates cross-reference checks over the working body."""

    def test_gates_on_script_stage_rejected(self, tmp_path: Path) -> None:
        """A gate on a stage compiling to a script stage is a strict error naming the stage."""
        pipeline_text = "name: T\ndescription: T\n---\ns:\n  title: S\n  script: make check\n"
        workflow_text = "stages:\n  s:\n    gates:\n      - name: g\n        script: pytest\n"

        with pytest.raises(
            StructuralError,
            match=re.escape("gates are forbidden on a script stage in workflow.stages.s"),
        ):
            _compile(tmp_path, pipeline_text, workflow_text)

    @pytest.mark.parametrize(
        "roles_line",
        [
            pytest.param("  roles: [planner]\n", id="alias-planner"),
            pytest.param("  roles: [planning]\n", id="already-afm-planning"),
        ],
    )
    def test_gates_on_planning_only_stage_rejected(self, tmp_path: Path, roles_line: str) -> None:
        """A gate on a planning-only stage errors — the comparison is TRANSLATED (both role spellings)."""
        pipeline_text = "name: T\ndescription: T\n---\np:\n  title: P\n  prompt: Think\n" + roles_line
        workflow_text = "stages:\n  p:\n    gates:\n      - name: g\n        script: pytest\n"

        with pytest.raises(
            StructuralError,
            match=re.escape("gates are forbidden on a planning-only stage in workflow.stages.p"),
        ):
            _compile(tmp_path, pipeline_text, workflow_text)

    @pytest.mark.parametrize(
        ("stage_body", "message"),
        [
            pytest.param(
                "  gates: []\n",
                "gates key is forbidden in stage body; use gates in workflow.stages",
                id="gates",
            ),
            pytest.param(
                "  verify: make test\n",
                "verify key is forbidden in stage body; use gates in workflow.stages",
                id="verify",
            ),
        ],
    )
    def test_gates_and_verify_keys_forbidden_in_stage_body(
        self,
        tmp_path: Path,
        stage_body: str,
        message: str,
    ) -> None:
        """A pipeline-file stage body cannot author the authoring/compiled gate keys."""
        pipeline_text = (
            "name: demo\ndescription: Demo pipeline\n---\nbuild:\n  title: Build\n  prompt: Make\n" + stage_body
        )

        with pytest.raises(StructuralError, match=re.escape(message)):
            _compile(tmp_path, pipeline_text)

    def test_verify_key_forbidden_in_extend_body(self, tmp_path: Path) -> None:
        """An embedded extend-stage body hits the same prohibition (same ``_canonical_fields`` pass)."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_BASE_STAGES)
        workflow = WorkflowDocument(
            extend={
                "extra": WorkflowExtendStage(
                    after=["build"],
                    body={"title": "Extra", "verify": "make test"},
                ),
            },
        )

        with pytest.raises(
            StructuralError,
            match=re.escape("verify key is forbidden in stage body; use gates in workflow.stages"),
        ):
            compile_flow(pipeline_path, tmp_path / "flow.yml", workflow=workflow)

    def test_gates_of_skipped_stage_drop_silently(self, tmp_path: Path) -> None:
        """A gate on a skipped stage never reaches the checks — it drops silently with the stage."""
        workflow_text = (
            "stages:\n  review:\n    skip: true\n    gates:\n      - name: tests\n        script: pytest -q\n"
        )
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert "verify" not in text
        assert all("verify" not in stage.fields for stage in flow_doc.stages)

    @pytest.mark.parametrize(
        "step",
        [
            pytest.param(lambda: WorkflowGateStep(name="g"), id="neither"),
            pytest.param(
                lambda: WorkflowGateStep(name="g", script="pytest", agent="codex"),
                id="both",
            ),
        ],
    )
    def test_degenerate_gate_step_rejected_defensively(self, tmp_path: Path, step) -> None:
        """A step carrying both or neither of ``script``/``agent`` fails the compile.

        Authored files hit the parser's own exclusivity check first; a
        PROGRAMMATIC workflow (a tool contribution rides the overlay merge
        without a parse) can reach the compiler with a degenerate step.
        The guard names the authoring site with the parser's message —
        never a wrapper path composed over a ``None`` agent.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_BASE_STAGES)
        workflow = WorkflowDocument(stages={"build": WorkflowStage(gates=[step()])})

        with pytest.raises(
            StructuralError,
            match=re.escape("gates step must carry exactly one of script/agent in workflow.stages.build.gates[0]"),
        ):
            compile_flow(pipeline_path, tmp_path / "flow.yml", workflow=workflow)

    def test_prompt_on_script_gate_step_rejected_defensively(self, tmp_path: Path) -> None:
        """A script step carrying ``prompt`` fails the compile.

        Authored files hit the parser's own prompt binding first; a
        PROGRAMMATIC workflow (a tool contribution rides the overlay merge
        without a parse) can reach the compiler with the degenerate pair —
        the model types allow it (both are ``str | None``). The guard names
        the authoring site with the parser's message instead of emitting a
        ``run``+``prompt`` step the engine rejects at load (``prompt`` is
        valid on AI steps only).
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_BASE_STAGES)
        workflow = WorkflowDocument(
            stages={"build": WorkflowStage(gates=[WorkflowGateStep(name="g", script="pytest", prompt="Why?")])},
        )

        with pytest.raises(
            StructuralError,
            match=re.escape("prompt is forbidden on a script gate step in workflow.stages.build.gates[0]"),
        ):
            compile_flow(pipeline_path, tmp_path / "flow.yml", workflow=workflow)

    def test_attachment_error_precedes_gates_error(self, tmp_path: Path) -> None:
        """A stage failing both 4.10 and 4.11 reports the attachment error — deterministic order.

        The reconstruction tuple evaluates the attachments emission before
        the gates emission, so a script stage carrying both an assistant
        attachment and a gate fails with the attachment message.
        """
        pipeline_text = "name: T\ndescription: T\n---\ns:\n  title: S\n  script: make check\n"
        workflow_text = (
            "stages:\n"
            "  s:\n"
            "    assistants:\n"
            "      helper:\n"
            "        when: checkpoints\n"
            "        prompt: Help.\n"
            "    gates:\n"
            "      - name: g\n"
            "        script: pytest\n"
        )

        with pytest.raises(
            StructuralError,
            match=re.escape("assistant is forbidden on a script stage in workflow.stages.s: helper"),
        ):
            _compile(tmp_path, pipeline_text, workflow_text)


class TestCompileFlowGatesEdge:
    """Edge cases — byte-identity, verbatim values, and the merged extend entry."""

    def test_gate_free_workflow_compiles_byte_identically(self, tmp_path: Path) -> None:
        """A workflow without gates compiles to exactly the pre-feature output (full-string golden)."""
        _pipeline_doc, _flow_doc, text = _compile(tmp_path, _BASE_STAGES_REPEATABLE, _GATE_FREE_WORKFLOW)

        assert text == _GATE_FREE_GOLDEN

    def test_malformed_timeout_passes_verbatim(self, tmp_path: Path) -> None:
        """A malformed gate timeout value passes verbatim — the grammar is engine-owned."""
        workflow_text = (
            "stages:\n  build:\n    gates:\n      - name: compile\n        script: make all\n        timeout: 30x\n"
        )
        _pipeline_doc, _flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert "timeout: 30x" in text

    def test_empty_programmatic_gates_list_equals_absence(self, tmp_path: Path) -> None:
        """An empty gates list from a tool contribution emits nothing — empty equals absence.

        The parser normalizes authored emptiness to ``None``, but the
        overlay merge carries a tool's ``WorkflowStage(gates=[])``
        verbatim (``_is_set`` counts the empty list as authored). The
        emission guard treats the empty list exactly like absence: no
        verify key anywhere, and no spurious body check — a SCRIPT stage
        carrying an empty list is not a forbidden-gates error.
        """
        pipeline_text = (
            "name: demo\n"
            "description: Demo pipeline\n"
            "---\n"
            "build:\n"
            "  title: Build\n"
            "  prompt: Make\n"
            "check:\n"
            "  title: Check\n"
            "  script: make check\n"
        )
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(pipeline_text)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={
                "build": WorkflowStage(gates=[]),
                "check": WorkflowStage(gates=[]),
            },
        )

        _pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)
        text = flow_path.read_text()

        assert "verify" not in text
        assert all("verify" not in stage.fields for stage in flow_doc.stages)

    def test_gates_pipeline_document_body_untouched(self, tmp_path: Path) -> None:
        """The ``PipelineDocument`` mirror keeps the authored body verbatim.

        No ``verify``/``gates`` key appears in the mirror's stage bodies —
        the gate lives only in ``FlowStage.fields`` (output-side only, the
        timeout-translation precedent).
        """
        workflow_text = "stages:\n  build:\n    gates:\n      - name: compile\n        script: make all\n"
        pipeline_doc, flow_doc, _text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        build_step = next(step for step in pipeline_doc.body.steps if step.name == "build")
        build_stage = next(stage for stage in flow_doc.stages if stage.id == "build")

        assert "verify" not in build_step.body
        assert "gates" not in build_step.body
        assert "verify" in build_stage.fields

    def test_extend_plus_stages_entry_keeps_gate(self, tmp_path: Path) -> None:
        """A stage carrying BOTH an extend-entry and a stages-block entry keeps its gate."""
        pipeline_text = (
            "name: demo\n"
            "description: Demo pipeline\n"
            "---\n"
            "a:\n"
            "  title: A\n"
            "  prompt: Do A\n"
            "x:\n"
            "  title: X\n"
            "  prompt: Do X\n"
        )
        workflow_text = (
            "extend:\n"
            "  x:\n"
            "    after:\n"
            "      - a\n"
            "    agent: codex\n"
            "stages:\n"
            "  x:\n"
            "    gates:\n"
            "      - name: g\n"
            "        script: pytest -q\n"
        )
        _pipeline_doc, flow_doc, text = _compile(tmp_path, pipeline_text, workflow_text)

        x_stage = next(stage for stage in flow_doc.stages if stage.id == "x")

        assert "verify:" in text
        assert "command: /home/goga/bin/codex-as-claude.sh" in text
        assert "verify" in x_stage.fields


class TestCompileFlowGatesPlumbing:
    """Direct unit tests of the private step-4.11 helpers (the ``notes_by_id`` precedent)."""

    def test_effective_overrides_merged_branch_passes_gates(self) -> None:
        """A stage named in both ``extend`` and ``stages`` keeps its stages-block gates."""
        workflow = WorkflowDocument(
            stages={"x": WorkflowStage(gates=[WorkflowGateStep(name="g", script="pytest")])},
            extend={"x": WorkflowExtendStage(after=["y"], body={})},
        )

        effective = _effective_overrides(workflow)

        assert effective["x"].gates == [WorkflowGateStep(name="g", script="pytest")]

    def test_effective_overrides_extend_seeded_entry_carries_no_gates(self) -> None:
        """An extend-seeded entry carries the constructor default ``None`` — gates is stages-block-only."""
        workflow = WorkflowDocument(extend={"z": WorkflowExtendStage(after=["y"], body={})})

        effective = _effective_overrides(workflow)

        assert effective["z"].gates is None

    def test_assemble_verify_noop_on_none(self) -> None:
        """``None`` assembles nothing — an ungated stage carries no verify key."""
        source: dict[str, object] = {"prompt": "p"}

        _assemble_verify(source, None)

        assert source == {"prompt": "p"}

    def test_assemble_verify_assigns_the_gate(self) -> None:
        """A gate is assigned into the source — the canonical loop then slots it last."""
        source: dict[str, object] = {"prompt": "p"}
        verify = FlowVerify(steps=[])

        _assemble_verify(source, verify)

        assert source == {"prompt": "p", "verify": verify}
