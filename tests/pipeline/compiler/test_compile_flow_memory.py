"""Contract and logic tests for the ``compile_flow`` memory emission (step 4.9).

Covers the memory half of the compiler: when the supplied workflow carries
memory participation, ``compile_flow`` assembles the top-level ``memory`` block
of the flow-file and the per-stage memory keys —

- the block is emitted if and only if at least one stage participates: a
  ``reflect`` instruction under the reflect method (the default), or a true
  ``memory`` instruction under the alignment method; a memory configuration
  alone never turns the block on (silent no-op, cases 3 and 5);
- participation is counted over the WORKING body — after skip removal and loop
  expansion, embedded extend-stages included (a skipped stage's instructions
  never count);
- the emitted path composes the fixed memory root ``.goga/memory`` with the
  authored suffix (the bare root when the suffix is ``None``);
- reflect method — ``mode: r`` and ``memory_use: false`` (read-only project
  memory, no global participation); alignment method — ``mode`` the
  materialized authored value (``rw`` by default) and ``memory_use: false``;
- reflect method — a participating stage carries ``reflect: {file, mode}``
  (file verbatim, mode materialized); alignment method — EVERY stage carries
  ``memory_use`` (explicit ``false`` on every non-participating one, because
  afm's ``UseFor(stage)`` inherits the global default for an unset key);
- both keys occupy the canonical slots immediately after ``script_timeout`` and
  are uniform across every loop-expanded copy;
- the goga-side method selector never reaches the output;
- an authoring ``reflect`` / ``memory_use`` key in a stage body (pipeline-file
  stage OR embedded extend-stage body) is a structural error;
- a workflow without memory participation compiles byte-identically to the
  current output (no block, no stage keys);
- output-side only — the ``PipelineDocument`` mirror stays the faithful mirror
  of the source pipeline-file.
"""

from __future__ import annotations

import dataclasses
import inspect
import re
from pathlib import Path

import pytest
from goga.pipeline.compiler import (
    FlowDocument,
    FlowMemory,
    PipelineDocument,
    StructuralError,
    compile_flow,
)
from goga.pipeline.compiler.compile_flow import (
    _CANONICAL_KEY_ORDER,
    _assemble_memory_keys,
    _canonical_fields,
    _effective_overrides,
    _memory_emission,
    _MemoryEmission,
)
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowMemory,
    WorkflowReflect,
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

# Base PHASES-format pipeline-file — the list body derives ``depends_on`` by
# position, pinning that memory emission never disturbs the position rules.
_BASE_PHASES = (
    "name: demo\n"
    "description: Demo pipeline\n"
    "---\n"
    "- name: brainstorm\n"
    "  title: Brainstorm\n"
    "  prompt: Think\n"
    "- name: build\n"
    "  title: Build\n"
    "  prompt: Make\n"
)


def _compile(
    tmp_path: Path,
    pipeline_text: str,
    workflow_text: str | None = None,
) -> tuple[PipelineDocument, FlowDocument, str]:
    """Write the pipeline (and optional workflow), compile, return documents + text.

    Mirrors the ``_compile`` helper of ``test_compile_flow_timeout.py`` but also
    returns the documents tuple so the memory tests can assert on the assembled
    ``FlowDocument`` and its stages.
    """
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(pipeline_text)
    flow_path = tmp_path / "flow.yml"

    workflow = None

    if workflow_text is not None:
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(workflow_text)
        workflow = parse_workflow(workflow_path)

    pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

    return pipeline_doc, flow_doc, flow_path.read_text()


class TestCompileFlowMemoryContract:
    """Contract tests — the memory surface declared by the compiler CODEMANIFEST."""

    def test_compile_flow_signature_unchanged_no_memory_parameter(self) -> None:
        """``compile_flow`` keeps its five parameters — memory travels inside ``WorkflowDocument``."""
        parameters = list(inspect.signature(compile_flow).parameters)

        assert parameters == ["pipeline_path", "flow_path", "workflow", "root_dir", "project_name"]

    def test_memory_helpers_not_on_facade(self) -> None:
        """``_memory_emission`` & co. are module-internal, not facade names."""
        from goga.pipeline.compiler import __all__ as facade_all

        assert "_memory_emission" not in facade_all
        assert "_MemoryEmission" not in facade_all
        assert "_assemble_memory_keys" not in facade_all
        assert "_MEMORY_ROOT" not in facade_all

    def test_memory_helpers_exist_in_module(self) -> None:
        """The step-4.9 helpers exist with the contract shape."""
        from goga.pipeline.compiler.compile_flow import _MEMORY_ROOT

        assert _MEMORY_ROOT == ".goga/memory"
        assert callable(_memory_emission)
        assert callable(_assemble_memory_keys)
        assert [f.name for f in dataclasses.fields(_MemoryEmission)] == ["block", "keys_by_id"]

    def test_canonical_key_order_ends_with_memory_slots(self) -> None:
        """``reflect`` and ``memory_use`` close the canonical order after ``script_timeout``."""
        assert _CANONICAL_KEY_ORDER[-6:] == [
            "script_before",
            "script",
            "script_after",
            "script_timeout",
            "reflect",
            "memory_use",
        ]
        assert _CANONICAL_KEY_ORDER.index("reflect") == _CANONICAL_KEY_ORDER.index("script_timeout") + 1
        assert _CANONICAL_KEY_ORDER.index("memory_use") == _CANONICAL_KEY_ORDER.index("reflect") + 1

    def test_canonical_fields_accepts_memory_fields(self) -> None:
        """``_canonical_fields`` takes ``(body, stage_name, notes, memory_fields)`` — both optional."""
        parameters = list(inspect.signature(_canonical_fields).parameters)

        assert parameters == ["body", "stage_name", "notes", "memory_fields"]
        assert inspect.signature(_canonical_fields).parameters["notes"].default is None
        assert inspect.signature(_canonical_fields).parameters["memory_fields"].default is None


class TestCompileFlowMemoryEmission:
    """Step 4.9 / 5 / 6 — block emission and stage-key assembly across the six cases."""

    def test_compile_flow_no_block_with_reflect_instructions_emits_block(self, tmp_path: Path) -> None:
        """Emission case 2 — instructions with no authored block emit it from the materialized defaults."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            _BASE_STAGES,
            "stages:\n  brainstorm:\n    reflect:\n      file: shared.md\n",
        )

        assert flow_doc.memory == FlowMemory(
            path=".goga/memory", mode="r", memory_use=False, max_rules=25, commit=False
        )
        assert "memory:" in text
        assert "path: .goga/memory" in text
        assert "mode: r" in text.split("stages:")[0]
        assert "memory_use: false" in text.split("stages:")[0]
        assert "max_rules: 25" in text
        assert "commit: false" in text
        assert "  reflect:" in text
        assert "file: shared.md" in text
        assert flow_doc.stages[0].fields["reflect"] == {"file": "shared.md", "mode": "rw"}
        assert flow_doc.stages[1].fields.get("reflect") is None
        assert flow_doc.stages[2].fields.get("reflect") is None

    def test_compile_flow_reflect_authored_mode_carries_verbatim(self, tmp_path: Path) -> None:
        """An authored reflect ``mode`` reaches the stage key verbatim (materialization is the fallback)."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            _BASE_STAGES,
            "stages:\n  build:\n    reflect:\n      file: a.md\n      mode: r\n",
        )

        assert flow_doc.stages[1].fields["reflect"] == {"file": "a.md", "mode": "r"}
        assert "mode: r" in text

    def test_compile_flow_max_rules_boundary_reaches_block(self, tmp_path: Path) -> None:
        """The inclusive ``max_rules`` lower boundary (1) reaches the emitted block verbatim."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            _BASE_STAGES,
            "memory:\n  max_rules: 1\nstages:\n  build:\n    reflect:\n      file: a.md\n",
        )

        assert flow_doc.memory is not None
        assert flow_doc.memory.max_rules == 1
        assert "max_rules: 1" in text

    def test_compile_flow_alignment_emits_block_and_marks_every_stage(self, tmp_path: Path) -> None:
        """Emission case 4 — alignment marks participating stages and opts the rest out explicitly."""
        workflow_text = (
            "memory:\n"
            "  method: alignment\n"
            "  path: goga-development\n"
            "stages:\n"
            "  brainstorm:\n"
            "    memory: true\n"
            "  build:\n"
            "    memory: true\n"
        )
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert flow_doc.memory == FlowMemory(
            path=".goga/memory/goga-development",
            mode="rw",
            memory_use=False,
            max_rules=25,
            commit=False,
        )
        assert flow_doc.stages[0].fields["memory_use"] is True
        assert flow_doc.stages[1].fields["memory_use"] is True
        assert flow_doc.stages[2].fields["memory_use"] is False
        assert all("reflect" not in stage.fields for stage in flow_doc.stages)
        assert "memory_use: false" in text

    def test_compile_flow_alignment_authored_mode_carries_verbatim(self, tmp_path: Path) -> None:
        """An authored alignment ``mode`` reaches the block verbatim (materialization is the fallback)."""
        workflow_text = (
            "memory:\n"
            "  method: alignment\n"
            "  path: p\n"
            "  mode: r\n"
            "stages:\n"
            "  build:\n"
            "    memory: true\n"
        )
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert flow_doc.memory is not None
        assert flow_doc.memory.mode == "r"
        assert flow_doc.memory.memory_use is False
        assert "mode: r" in text

    def test_compile_flow_reflect_slot_after_script_timeout(self, tmp_path: Path) -> None:
        """The stage ``reflect`` key occupies the canonical slot immediately after ``script_timeout``."""
        pipeline_text = (
            "name: demo\n"
            "description: Demo pipeline\n"
            "---\n"
            "build:\n"
            "  title: Build\n"
            "  script: make build\n"
            "  timeout: 5m\n"
        )
        _pipeline_doc, flow_doc, _text = _compile(
            tmp_path,
            pipeline_text,
            "stages:\n  build:\n    reflect:\n      file: shared.md\n",
        )

        fields = flow_doc.stages[0].fields

        assert list(fields).index("script_timeout") < list(fields).index("reflect")

    def test_compile_flow_reflect_uniform_across_loop_copies(self, tmp_path: Path) -> None:
        """Every loop-expanded copy ``NAME-i`` carries the same reflect instruction as its base."""
        _pipeline_doc, flow_doc, _text = _compile(
            tmp_path,
            _BASE_STAGES,
            "stages:\n  brainstorm:\n    loop: 3\n    reflect:\n      file: shared.md\n",
        )

        copies = [stage for stage in flow_doc.stages if stage.id.startswith("brainstorm")]

        assert len(copies) == 3
        for stage in copies:
            assert stage.fields["reflect"] == {"file": "shared.md", "mode": "rw"}

    def test_compile_flow_alignment_uniform_across_loop_copies(self, tmp_path: Path) -> None:
        """Every loop-expanded copy carries its base's ``memory_use`` — participants and opt-outs alike."""
        workflow_text = (
            "memory:\n"
            "  method: alignment\n"
            "stages:\n"
            "  brainstorm:\n"
            "    loop: 3\n"
            "    memory: true\n"
        )
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        copies = [stage for stage in flow_doc.stages if stage.id.startswith("brainstorm")]
        bystanders = [stage for stage in flow_doc.stages if not stage.id.startswith("brainstorm")]

        assert flow_doc.memory is not None
        assert len(copies) == 3
        for stage in copies:
            assert stage.fields["memory_use"] is True
        for stage in bystanders:
            assert stage.fields["memory_use"] is False
        assert "memory_use: false" in text

    def test_compile_flow_phases_reflect_emits_block_and_stage_keys(self, tmp_path: Path) -> None:
        """The PHASES list body emits the block and the stage keys identically — format-agnostic."""
        workflow_text = "stages:\n  brainstorm:\n    reflect:\n      file: shared.md\n"
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_PHASES, workflow_text)

        assert flow_doc.memory == FlowMemory(
            path=".goga/memory", mode="r", memory_use=False, max_rules=25, commit=False
        )
        assert flow_doc.stages[0].fields["reflect"] == {"file": "shared.md", "mode": "rw"}
        assert flow_doc.stages[0].depends_on is None
        assert flow_doc.stages[1].fields.get("reflect") is None
        assert flow_doc.stages[1].depends_on == ["brainstorm"]
        assert "  reflect:" in text

    def test_compile_flow_reflect_applies_to_extend_stage_by_name(self, tmp_path: Path) -> None:
        """An embedded extend-stage participates through its ``stages``-block entry (by name)."""
        workflow_text = (
            "stages:\n"
            "  extra:\n"
            "    reflect:\n"
            "      file: extra.md\n"
            "extend:\n"
            "  extra:\n"
            "    after:\n"
            "      - build\n"
            "    title: Extra\n"
            "    prompt: extra work\n"
        )
        _pipeline_doc, flow_doc, _text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        extra_stage = next(stage for stage in flow_doc.stages if stage.id == "extra")

        assert extra_stage.fields["reflect"] == {"file": "extra.md", "mode": "rw"}
        assert flow_doc.memory is not None
        others = [stage for stage in flow_doc.stages if stage.id != "extra"]
        assert all("reflect" not in stage.fields for stage in others)

    def test_compile_flow_alignment_applies_to_extend_stage_by_name(self, tmp_path: Path) -> None:
        """An embedded extend-stage participates under alignment through its ``stages`` entry."""
        workflow_text = (
            "memory:\n"
            "  method: alignment\n"
            "stages:\n"
            "  extra:\n"
            "    memory: true\n"
            "extend:\n"
            "  extra:\n"
            "    after:\n"
            "      - build\n"
            "    title: Extra\n"
            "    prompt: extra work\n"
        )
        _pipeline_doc, flow_doc, _text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        extra_stage = next(stage for stage in flow_doc.stages if stage.id == "extra")

        assert flow_doc.memory is not None
        assert extra_stage.fields["memory_use"] is True
        others = [stage for stage in flow_doc.stages if stage.id != "extra"]
        assert all(stage.fields["memory_use"] is False for stage in others)

    def test_compile_flow_block_without_instructions_is_silent_noop(self, tmp_path: Path) -> None:
        """Emission case 3 — a configuration-only block emits nothing at all."""
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, "memory:\n  max_rules: 40\n")

        assert flow_doc.memory is None
        assert "memory:" not in text
        assert all("reflect" not in stage.fields and "memory_use" not in stage.fields for stage in flow_doc.stages)

    def test_compile_flow_alignment_all_false_is_silent_noop(self, tmp_path: Path) -> None:
        """Emission case 5 — alignment with no true instruction is a silent no-op."""
        workflow_text = "memory:\n  method: alignment\nstages:\n  build:\n    memory: false\n"
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert flow_doc.memory is None
        assert "memory:" not in text
        assert all("memory_use" not in stage.fields for stage in flow_doc.stages)

    def test_compile_flow_skip_of_only_participating_stage_emits_no_block(self, tmp_path: Path) -> None:
        """A stage removed by skip never counts — its instructions die with it (design scenario 3)."""
        workflow_text = "stages:\n  brainstorm:\n    reflect:\n      file: a.md\n    skip: true\n"
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert flow_doc.memory is None
        assert "memory:" not in text
        assert all("reflect" not in stage.fields and "memory_use" not in stage.fields for stage in flow_doc.stages)

    def test_compile_flow_alignment_skip_of_only_participating_stage_emits_no_block(
        self, tmp_path: Path
    ) -> None:
        """Under alignment a skipped participant dies with its instruction — no block, no keys."""
        workflow_text = (
            "memory:\n"
            "  method: alignment\n"
            "stages:\n"
            "  build:\n"
            "    memory: true\n"
            "    skip: true\n"
        )
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert flow_doc.memory is None
        assert "memory:" not in text
        assert all("memory_use" not in stage.fields for stage in flow_doc.stages)

    def test_compile_flow_reflect_block_carries_mode_r_and_memory_use_false(self, tmp_path: Path) -> None:
        """Emission case 6 — the reflect-method block carries mode: r and memory_use: false."""
        workflow_text = (
            "memory:\n"
            "  max_rules: 9\n"
            "  commit: true\n"
            "stages:\n"
            "  brainstorm:\n"
            "    reflect:\n"
            "      file: shared.md\n"
        )
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert flow_doc.memory is not None
        assert flow_doc.memory.mode == "r"
        assert flow_doc.memory.memory_use is False

        block_text = text.split("stages:")[0].split("memory:")[1]

        assert "mode: r" in block_text
        assert "memory_use: false" in block_text
        assert "commit: true" in text


class TestCompileFlowMemoryAuthoringProhibition:
    """Step 5 — the authoring-forbidden memory keys in any stage body."""

    @pytest.mark.parametrize(
        ("stage_body", "message"),
        [
            pytest.param(
                "  reflect:\n    file: a.md\n",
                "reflect key is forbidden in stage body; use reflect in workflow.stages",
                id="reflect",
            ),
            pytest.param(
                "  memory_use: false\n",
                "memory_use key is forbidden in stage body; use memory in workflow.stages",
                id="memory-use",
            ),
        ],
    )
    def test_compile_flow_rejects_authoring_memory_keys_in_stage_body(
        self,
        tmp_path: Path,
        stage_body: str,
        message: str,
    ) -> None:
        """A pipeline-file stage body cannot author the output-side memory keys."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: demo\ndescription: Demo pipeline\n---\nbuild:\n  title: Build\n  prompt: Make\n" + stage_body,
        )

        with pytest.raises(StructuralError, match=re.escape(message)):
            compile_flow(pipeline_path, tmp_path / "flow.yml")

    def test_compile_flow_rejects_authoring_reflect_in_extend_body(self, tmp_path: Path) -> None:
        """An embedded extend-stage body hits the same prohibition (same ``_canonical_fields`` pass)."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_BASE_STAGES)
        workflow = WorkflowDocument(
            extend={
                "extra": WorkflowExtendStage(
                    after=["build"],
                    body={"title": "Extra", "reflect": {"file": "a.md"}},
                ),
            },
        )

        with pytest.raises(
            StructuralError,
            match=re.escape("reflect key is forbidden in stage body; use reflect in workflow.stages"),
        ):
            compile_flow(pipeline_path, tmp_path / "flow.yml", workflow=workflow)


class TestCompileFlowMemoryPlumbing:
    """Direct unit tests of the private step-4.9 helpers (the ``notes_by_id`` precedent)."""

    def test_effective_overrides_merged_branch_passes_reflect_and_memory(self) -> None:
        """A stage named in both ``extend`` and ``stages`` keeps its participation instructions."""
        workflow = WorkflowDocument(
            stages={
                "x": WorkflowStage(reflect=WorkflowReflect(file="a.md"), memory=None),
                "y": WorkflowStage(memory=True),
            },
            extend={
                "x": WorkflowExtendStage(after=["y"], body={}),
                "z": WorkflowExtendStage(after=["x"], body={}),
            },
        )

        effective = _effective_overrides(workflow)

        assert effective["x"].reflect == WorkflowReflect(file="a.md", mode="rw")
        assert effective["y"].memory is True
        assert effective["z"].reflect is None
        assert effective["z"].memory is None

    def test_memory_emission_none_workflow_yields_no_block(self) -> None:
        """A ``None`` workflow never participates — no block, no stage keys."""
        emission = _memory_emission(None, {}, {})

        assert emission.block is None
        assert emission.keys_by_id == {}

    def test_memory_emission_default_config_supplies_block_values(self) -> None:
        """Reflect instructions with no authored block source the values from ``WorkflowMemory()``."""
        workflow = WorkflowDocument(stages={"build": WorkflowStage(reflect=WorkflowReflect(file="a.md"))})
        effective = _effective_overrides(workflow)

        emission = _memory_emission(workflow, effective, {"build": ["build"]})

        assert emission.block == FlowMemory(
            path=".goga/memory", mode="r", memory_use=False, max_rules=25, commit=False
        )
        assert emission.keys_by_id == {"build": {"reflect": {"file": "a.md", "mode": "rw"}}}

    def test_memory_emission_alignment_marks_every_final_id(self) -> None:
        """Alignment emits an explicit opt-out on every non-participating final id."""
        alignment = WorkflowDocument(
            memory=WorkflowMemory(method="alignment"),
            stages={"build": WorkflowStage(memory=True), "review": WorkflowStage()},
        )

        emission = _memory_emission(
            alignment,
            _effective_overrides(alignment),
            {"build": ["build"], "review": ["review"]},
        )

        assert emission.keys_by_id == {"build": {"memory_use": True}, "review": {"memory_use": False}}

    def test_memory_emission_no_participation_yields_empty_emission(self) -> None:
        """A configuration over a working body with no participants is a silent no-op (cases 3 and 5)."""
        reflect_config = WorkflowDocument(
            memory=WorkflowMemory(max_rules=40),
            stages={"build": WorkflowStage(), "review": WorkflowStage()},
        )
        alignment_config = WorkflowDocument(
            memory=WorkflowMemory(method="alignment"),
            stages={"build": WorkflowStage(), "review": WorkflowStage()},
        )

        for document in (reflect_config, alignment_config):
            emission = _memory_emission(
                document,
                _effective_overrides(document),
                {"build": ["build"], "review": ["review"]},
            )

            assert emission.block is None
            assert emission.keys_by_id == {}

    def test_assemble_memory_keys_noop_on_none_and_empty(self) -> None:
        """``None`` and an empty map assemble nothing — a non-participating stage carries no key."""
        source: dict[str, object] = {"prompt": "p"}

        _assemble_memory_keys(source, None)
        _assemble_memory_keys(source, {})

        assert source == {"prompt": "p"}

    def test_assemble_memory_keys_assigns_fresh_values(self) -> None:
        """A non-empty map updates the source — the canonical loop then slots the keys."""
        source: dict[str, object] = {"prompt": "p"}

        _assemble_memory_keys(source, {"reflect": {"file": "a.md", "mode": "rw"}})

        assert source == {"prompt": "p", "reflect": {"file": "a.md", "mode": "rw"}}
