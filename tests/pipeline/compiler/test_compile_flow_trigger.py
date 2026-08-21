"""Logic tests for the ``compile_flow`` trigger / auto_run / manual domain.

Covers the stage trigger directive (step 5 of ``compile_flow``) and the
workflow manual instruction (step 4a) — one functional domain spanning both
the non-workflow and the workflow path:

- the authoring-side ``trigger`` stage-body key (``on_success`` | ``manual``)
  is validated, CONSUMED, and translated into the output ``auto_run`` slot:
  a body whose effective trigger is ``manual`` assembles ``auto_run: false``
  (canonical slot immediately after ``auto_approve``); a body with
  ``trigger: on_success`` or no trigger assembles NO ``auto_run`` key;
- an authoring ``auto_run`` key in a stage body (pipeline-file stage OR
  embedded extend-stage) is a structural error — the runtime key is authored
  as ``trigger: manual``;
- the workflow ``stages.<name>.manual`` tri-state instruction forces
  (``True``), cancels (``False``), or leaves alone (``None``) the stage's
  effective trigger on the WORKING body copy only — the ``PipelineDocument``
  mirror stays untouched.

``serialize_flow`` renders ``auto_run`` as a plain bool scalar via the
generic path (same render as ``auto_approve: true``), so a pipeline without
trigger/manual compiles byte-identically to before.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from goga.pipeline.compiler import (
    FlowDocument,
    FlowStage,
    StructuralError,
    compile_flow,
    serialize_flow,
)
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowStage,
    parse_workflow,
)

_TRIGGER_PIPELINE = """\
name: Feature
description: Feature implementation
---
- name: build
  title: Build
  trigger: manual
  prompt: make it
"""


def _compile(tmp_path: Path, pipeline_text: str, workflow_text: str | None = None) -> str:
    """Write the pipeline (and optional workflow), compile, return the flow-file text."""
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(pipeline_text)
    flow_path = tmp_path / "flow.yml"

    workflow = None

    if workflow_text is not None:
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(workflow_text)
        workflow = parse_workflow(workflow_path)

    compile_flow(pipeline_path, flow_path, workflow=workflow)

    return flow_path.read_text()


class TestCompileFlowTriggerContract:
    """Contract tests — the trigger translation surface declared by the CODEMANIFEST."""

    def test_compile_flow_trigger_manual_emits_auto_run_false(self, tmp_path: Path) -> None:
        """``trigger: manual`` in a stage body assembles ``auto_run: false``.

        The authoring key is consumed (never an output unknown key), the value
        lands in the canonical slot right after ``auto_approve`` — with neither
        ``interactive``/``auto_approve``/``command`` present it is the FIRST
        field — and the ``PipelineDocument`` mirror keeps the authored body.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_TRIGGER_PIPELINE)
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path)

        flow_text = flow_path.read_text()

        assert "auto_run: false" in flow_text
        assert list(flow_doc.stages[0].fields.keys()) == ["auto_run", "prompt", "agents"]
        # The authoring key is consumed by the translation.
        assert "trigger" not in flow_text
        assert flow_doc.stages[0].fields["auto_run"] is False
        # The mirror keeps the authored body verbatim.
        assert pipeline_doc.body.steps[0].body["trigger"] == "manual"

    def test_serialize_flow_auto_run_plain_bool_scalar(self) -> None:
        """``auto_run`` serializes as a plain bool scalar (generic path)."""
        doc = FlowDocument(
            name="N",
            description="D",
            stages=[FlowStage(id="s", name="S", depends_on=None, fields={"auto_run": False})],
        )

        text = serialize_flow(doc)

        assert "auto_run: false" in text
        assert "auto_run: 'false'" not in text

    def test_compile_flow_workflow_manual_true_forces_over_body_trigger(self, tmp_path: Path) -> None:
        """``manual: true`` forces the manual state over any authored trigger.

        The workflow instruction rewrites the working body's ``trigger`` to
        ``manual`` regardless of the authored value, so step 5 assembles
        ``auto_run: false`` for the stage.
        """
        flow_text = _compile(
            tmp_path,
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: deploy\n  title: Deploy\n  trigger: on_success\n  prompt: ship it\n",
            "stages:\n  deploy:\n    manual: true\n",
        )

        deploy_block = flow_text[flow_text.index("- id: deploy") :]

        assert "auto_run: false" in deploy_block

    def test_effective_overrides_merged_entry_carries_manual(self) -> None:
        """The merged overlay branch must carry ``manual`` explicitly.

        The extend seed cannot carry ``manual`` (``parse_workflow`` forbids it
        in an extend-entry), so the effective ``manual`` is always the
        stages-block value — but the merged-branch constructor defaults
        ``manual`` to ``None``, so an overlay that forgets ``manual=stg.manual``
        silently loses the instruction (Design Applied Fix #2).
        """
        from goga.pipeline.compiler.compile_flow import _effective_overrides

        workflow = WorkflowDocument(
            stages={"extra": WorkflowStage(manual=True)},
            extend={"extra": WorkflowExtendStage(after=["deploy"], body={"title": "E"})},
        )

        effective = _effective_overrides(workflow)

        assert effective["extra"].manual is True

        extend_only = _effective_overrides(
            WorkflowDocument(extend={"x": WorkflowExtendStage(after=["deploy"], body={"title": "X"})}),
        )

        assert extend_only["x"].manual is None


class TestCompileFlowTriggerTranslation:
    """Step 5 — trigger validation and ``auto_run`` translation across body sources."""

    def test_compile_flow_trigger_manual_stages_format(self, tmp_path: Path) -> None:
        """``trigger: manual`` translates identically in the STAGES body format.

        ``_canonical_fields`` is the single translation site: the stage gains
        ``auto_run: false`` before its ``agents``, a dependent stage without a
        trigger gains nothing.
        """
        flow_text = _compile(
            tmp_path,
            "name: Feature\n"
            "description: Feature implementation\n"
            "---\n"
            "build:\n"
            "  title: Build\n"
            "  trigger: manual\n"
            "  roles: [planner]\n"
            "review:\n"
            "  title: Review\n"
            "  depends_on: [build]\n",
        )

        build_block = flow_text[: flow_text.index("- id: review")]
        review_block = flow_text[flow_text.index("- id: review") :]

        assert "auto_run: false" in build_block
        assert "auto_run" not in review_block
        assert build_block.index("auto_run: false") < build_block.index("agents:")

    def test_compile_flow_trigger_on_success_explicit_no_auto_run(self, tmp_path: Path) -> None:
        """An explicit ``trigger: on_success`` behaves like no trigger at all.

        afm's omit contract: the absence of the key is the norm, so neither
        ``auto_run`` nor the consumed ``trigger`` reaches the output.
        """
        flow_text = _compile(
            tmp_path,
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: build\n  title: Build\n  trigger: on_success\n  prompt: make it\n",
        )

        assert "auto_run" not in flow_text
        assert "trigger" not in flow_text

    def test_compile_flow_extend_body_trigger_manual_emits_auto_run(self, tmp_path: Path) -> None:
        """An extend-stage authors its launch mode through its own body.

        The extend body carries ``trigger`` verbatim through the embed; step 5
        translates it exactly like a pipeline-file body.
        """
        flow_text = _compile(
            tmp_path,
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: deploy\n  title: Deploy\n  prompt: ship it\n",
            "extend:\n  extra:\n    after: [deploy]\n    trigger: manual\n    title: Extra\n    prompt: do extra\n",
        )

        extra_block = flow_text[flow_text.index("- id: extra") :]

        assert "auto_run: false" in extra_block
        assert "trigger" not in flow_text

    def test_compile_flow_trigger_invalid_value_rejected(self, tmp_path: Path) -> None:
        """A ``trigger`` value outside the closed set is a structural error."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: build\n  title: Build\n  trigger: on_failure\n  prompt: make it\n",
        )

        with pytest.raises(StructuralError, match="trigger must be one of: on_success, manual"):
            compile_flow(pipeline_path, tmp_path / "flow.yml")

    def test_compile_flow_trigger_non_str_value_rejected(self, tmp_path: Path) -> None:
        """A non-str ``trigger`` value fails the same closed-set check.

        A bool is never a member of ``("on_success", "manual")``, so the
        authoring mistake surfaces as the same structural error rather than
        slipping through a comparison silently.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: build\n  title: Build\n  trigger: true\n  prompt: make it\n",
        )

        with pytest.raises(StructuralError, match="trigger must be one of: on_success, manual"):
            compile_flow(pipeline_path, tmp_path / "flow.yml")

    def test_compile_flow_extend_body_trigger_invalid_value_rejected(self, tmp_path: Path) -> None:
        """A ``trigger`` value outside the closed set is rejected on the extend path too.

        The extend body passes through the embed's body filtering
        (``_extend_step_title_and_body`` strips ``title``/``name``/``id``) —
        this pins that ``trigger`` survives it and still reaches
        ``_validate_trigger`` in step 5, exactly like a pipeline-file body. A
        typo'd trigger on the extend path must not silently compile as
        ``on_success`` and auto-run instead of pausing.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: deploy\n  title: Deploy\n  prompt: ship it\n",
        )
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "extend:\n  extra:\n    after: [deploy]\n    trigger: on_failure\n    prompt: do extra\n",
        )

        with pytest.raises(StructuralError, match="trigger must be one of: on_success, manual"):
            compile_flow(pipeline_path, tmp_path / "flow.yml", workflow=parse_workflow(workflow_path))

    def test_compile_flow_authoring_auto_run_forbidden(self, tmp_path: Path) -> None:
        """An authoring ``auto_run`` key in a pipeline-file body is rejected."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: build\n  title: Build\n  auto_run: false\n  prompt: make it\n",
        )

        with pytest.raises(StructuralError, match="auto_run key is forbidden in stage body; use trigger: manual"):
            compile_flow(pipeline_path, tmp_path / "flow.yml")

    def test_compile_flow_authoring_auto_run_forbidden_in_extend_body(self, tmp_path: Path) -> None:
        """The authoring ``auto_run`` prohibition covers extend bodies too."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: deploy\n  title: Deploy\n  prompt: ship it\n",
        )
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "extend:\n  extra:\n    after: [deploy]\n    auto_run: true\n    title: Extra\n",
        )

        with pytest.raises(StructuralError, match="auto_run key is forbidden in stage body"):
            compile_flow(
                pipeline_path,
                tmp_path / "flow.yml",
                workflow=parse_workflow(workflow_path),
            )

    def test_compile_flow_no_trigger_no_manual_byte_identical(self, tmp_path: Path) -> None:
        """A pipeline without trigger/manual compiles byte-identically to before.

        Neither new branch fires, so the field set and its order are exactly
        the pre-change baseline — the regression anchor for afm's omit
        contract.
        """
        expected = (
            "name: Feature\n"
            "description: Feature implementation\n"
            "stages:\n"
            "- id: build\n"
            "  name: Build\n"
            "  prompt: make it\n"
            "  agents: [auto]\n"
            "- id: review\n"
            "  name: Review\n"
            "  prompt: check it\n"
            "  agents: [auto]\n"
            "  depends_on:\n"
            "  - build\n"
        )

        flow_text = _compile(
            tmp_path,
            "name: Feature\n"
            "description: Feature implementation\n"
            "---\n"
            "- name: build\n"
            "  title: Build\n"
            "  prompt: make it\n"
            "- name: review\n"
            "  title: Review\n"
            "  prompt: check it\n",
        )

        assert flow_text == expected
        assert "auto_run" not in flow_text

    def test_compile_flow_auto_run_slot_immediately_after_auto_approve(self, tmp_path: Path) -> None:
        """``auto_run`` occupies the canonical slot immediately after ``auto_approve``."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: build\n  title: Build\n  trigger: manual\n  roles: [planner]\n",
        )
        workflow = WorkflowDocument(stages={"build": WorkflowStage(approve="dialog")})

        _, flow_doc = compile_flow(pipeline_path, tmp_path / "flow.yml", workflow=workflow)

        flow_text = (tmp_path / "flow.yml").read_text()

        keys = list(flow_doc.stages[0].fields.keys())

        assert keys.index("auto_approve") + 1 == keys.index("auto_run")
        assert flow_text.index("auto_approve: true") < flow_text.index("auto_run: false")
        assert "auto_approve: true\n  auto_run: false" in flow_text

    def test_compile_flow_trigger_null_value_treated_as_absent(self, tmp_path: Path) -> None:
        """``trigger:`` with no value is treated as absent (null == absent).

        Validation gates on the VALUE (symmetrically to ``roles: null``), not
        on key presence, and the key is still consumed so it never reaches the
        output as an unknown key.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: build\n  title: Build\n  trigger:\n  prompt: make it\n",
        )

        _, flow_doc = compile_flow(pipeline_path, tmp_path / "flow.yml")

        flow_text = (tmp_path / "flow.yml").read_text()

        assert "auto_run" not in flow_text
        assert "trigger" not in flow_text
        assert list(flow_doc.stages[0].fields.keys()) == ["prompt", "agents"]


class TestCompileFlowWorkflowManual:
    """Step 4a — the tri-state workflow ``manual`` instruction application."""

    def test_compile_flow_workflow_manual_true_idempotent_on_manual_stage(self, tmp_path: Path) -> None:
        """Forcing an already-manual stage is an idempotent no-op (no error)."""
        flow_text = _compile(
            tmp_path,
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: deploy\n  title: Deploy\n  trigger: manual\n  prompt: ship it\n",
            "stages:\n  deploy:\n    manual: true\n",
        )

        deploy_block = flow_text[flow_text.index("- id: deploy") :]

        assert deploy_block.count("auto_run: false") == 1

    def test_compile_flow_workflow_manual_false_cancels_body_trigger(self, tmp_path: Path) -> None:
        """``manual: false`` cancels an authored ``trigger: manual``.

        The cancel rewrites the working body's trigger to ``on_success``, so
        step 5 assembles NO ``auto_run`` key and the consumed authoring key
        never reaches the output.
        """
        flow_text = _compile(
            tmp_path,
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: deploy\n  title: Deploy\n  trigger: manual\n  prompt: ship it\n",
            "stages:\n  deploy:\n    manual: false\n",
        )

        assert "auto_run" not in flow_text
        assert "trigger" not in flow_text

    def test_compile_flow_workflow_manual_false_cancels_extend_body_trigger(self, tmp_path: Path) -> None:
        """``manual: false`` cancels a manual state sourced from an extend body.

        The cancel contract is "regardless of which side authored it" — the
        extend body's ``trigger: manual`` is rewritten to ``on_success`` the
        same way a pipeline-file body's is.
        """
        flow_text = _compile(
            tmp_path,
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: deploy\n  title: Deploy\n  prompt: ship it\n",
            "stages:\n"
            "  extra:\n"
            "    manual: false\n"
            "extend:\n"
            "  extra:\n"
            "    after: [deploy]\n"
            "    trigger: manual\n"
            "    title: Extra\n",
        )

        assert "auto_run" not in flow_text

    def test_compile_flow_manual_stage_loop_expansion_all_copies_auto_run(self, tmp_path: Path) -> None:
        """Every loop-expanded copy of a manual stage carries ``auto_run: false``.

        The authored ``trigger`` sits in the body that 4b deep-copies, so each
        copy NAME-1..NAME-N lands in step 5 with the same effective trigger.
        """
        flow_text = _compile(
            tmp_path,
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: review\n  title: Review\n  trigger: manual\n  prompt: check it\n",
            "stages:\n  review:\n    loop: 2\n",
        )

        review_1 = flow_text[flow_text.index("- id: review-1") : flow_text.index("- id: review-2")]
        review_2 = flow_text[flow_text.index("- id: review-2") :]

        assert "auto_run: false" in review_1
        assert "auto_run: false" in review_2

    def test_compile_flow_manual_true_with_loop_expansion(self, tmp_path: Path) -> None:
        """Force + loop: the 4a rewrite lands on the working body BEFORE 4b.

        The expansion deep-copies the already-rewritten body, so both copies
        carry the effective manual trigger.
        """
        flow_text = _compile(
            tmp_path,
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: review\n  title: Review\n  prompt: check it\n",
            "stages:\n  review:\n    manual: true\n    loop: 2\n",
        )

        review_1 = flow_text[flow_text.index("- id: review-1") : flow_text.index("- id: review-2")]
        review_2 = flow_text[flow_text.index("- id: review-2") :]

        assert "auto_run: false" in review_1
        assert "auto_run: false" in review_2

    def test_compile_flow_workflow_manual_false_on_non_manual_stage(self, tmp_path: Path) -> None:
        """Cancelling a stage with no manual state is a structural error."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: deploy\n  title: Deploy\n  prompt: ship it\n",
        )
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text("stages:\n  deploy:\n    manual: false\n")

        with pytest.raises(StructuralError, match="manual: false on non-manual stage deploy"):
            compile_flow(
                pipeline_path,
                tmp_path / "flow.yml",
                workflow=parse_workflow(workflow_path),
            )

    def test_compile_flow_workflow_manual_false_on_explicit_on_success_stage(self, tmp_path: Path) -> None:
        """An explicit ``trigger: on_success`` is not a manual state either.

        The cancel gates on the RESULTING state (the body's effective trigger),
        not on the mere presence of an authored trigger key.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: deploy\n  title: Deploy\n  trigger: on_success\n  prompt: ship it\n",
        )
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text("stages:\n  deploy:\n    manual: false\n")

        with pytest.raises(StructuralError, match="manual: false on non-manual stage deploy"):
            compile_flow(
                pipeline_path,
                tmp_path / "flow.yml",
                workflow=parse_workflow(workflow_path),
            )

    def test_compile_flow_skip_wins_over_manual(self, tmp_path: Path) -> None:
        """``skip: true`` removes the stage before the manual instruction applies.

        Any trigger/manual combination on a skipped entry never reaches 4a, so
        a would-be "manual: false on non-manual" conflict never fires and the
        surviving stages compile normally.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\n"
            "description: Feature implementation\n"
            "---\n"
            "- name: build\n"
            "  title: Build\n"
            "  prompt: make it\n"
            "- name: deploy\n"
            "  title: Deploy\n"
            "  trigger: manual\n"
            "  prompt: ship it\n",
        )
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text("stages:\n  deploy:\n    manual: false\n    skip: true\n")

        _, flow_doc = compile_flow(
            pipeline_path,
            tmp_path / "flow.yml",
            workflow=parse_workflow(workflow_path),
        )

        flow_text = (tmp_path / "flow.yml").read_text()

        assert len(flow_doc.stages) == 1
        assert flow_doc.stages[0].id == "build"
        assert "deploy" not in flow_text
        assert "auto_run" not in flow_text

    def test_compile_flow_pipeline_document_not_mutated_by_manual_rewrite(self, tmp_path: Path) -> None:
        """The manual rewrite lives on the working copy only.

        ``PipelineDocument`` mirrors the authored source verbatim — the cancel
        rewrites the copy, never the original parsed body.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: deploy\n  title: Deploy\n  trigger: manual\n  prompt: ship it\n",
        )
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text("stages:\n  deploy:\n    manual: false\n")

        pipeline_doc, flow_doc = compile_flow(
            pipeline_path,
            tmp_path / "flow.yml",
            workflow=parse_workflow(workflow_path),
        )

        assert pipeline_doc.body.steps[0].body["trigger"] == "manual"
        assert "auto_run" not in flow_doc.stages[0].fields

    def test_compile_flow_manual_true_overrides_invalid_trigger_value(self, tmp_path: Path) -> None:
        """Force rewrites even an invalid authored trigger value.

        4a runs before step 5's value validation, so after the rewrite the
        effective value is ``manual`` — in the closed set — and the compile
        succeeds (the deterministic 4a → 5 ordering).
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\ndescription: Feature implementation\n---\n"
            "- name: deploy\n  title: Deploy\n  trigger: on_failure\n  prompt: ship it\n",
        )
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text("stages:\n  deploy:\n    manual: true\n")

        compile_flow(
            pipeline_path,
            tmp_path / "flow.yml",
            workflow=parse_workflow(workflow_path),
        )

        flow_text = (tmp_path / "flow.yml").read_text()
        deploy_block = flow_text[flow_text.index("- id: deploy") :]

        assert "auto_run: false" in deploy_block

    def test_compile_flow_workflow_manual_true_forces_extend_stage(self, tmp_path: Path) -> None:
        """Force over extend body: the instruction CREATES the manual state.

        The extend body carries no trigger at all; the stages-block ``manual:
        true`` (merged over the extend seed) installs it. Exercises the merged
        branch of ``_effective_overrides`` end-to-end — a regression that drops
        ``manual=stg.manual`` there degrades this into "no auto_run for extra".
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: Feature\n"
            "description: Feature implementation\n"
            "---\n"
            "build:\n"
            "  title: Build\n"
            "  prompt: make it\n"
            "review:\n"
            "  title: Review\n"
            "  depends_on: [build]\n"
            "  prompt: check it\n",
        )
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "stages:\n"
            "  extra:\n"
            "    manual: true\n"
            "extend:\n"
            "  extra:\n"
            "    after: [build]\n"
            "    title: Extra\n"
            "    prompt: do extra\n",
        )

        _, flow_doc = compile_flow(
            pipeline_path,
            tmp_path / "flow.yml",
            workflow=parse_workflow(workflow_path),
        )

        flow_text = (tmp_path / "flow.yml").read_text()
        extra_stage = next(stage for stage in flow_doc.stages if stage.id == "extra")

        assert extra_stage.fields["auto_run"] is False
        assert list(extra_stage.fields.keys()).index("auto_run") < list(extra_stage.fields.keys()).index("prompt")
        assert "auto_run: false" in flow_text
        assert "trigger" not in flow_text
        by_id = {stage.id: stage for stage in flow_doc.stages}
        assert "auto_run" not in by_id["build"].fields
        assert "auto_run" not in by_id["review"].fields
