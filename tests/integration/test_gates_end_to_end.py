"""End-to-end integration tests: the gates lifecycle across the four cells.

The per-cell suites pin each carriage in isolation (parser, compiler
emission, overlay merge, skip rebuild); these scenarios stitch the cells
into the two composed paths of the design's data-flow diagram plus the
loop-uniformity edge:

- the amendment path — a gates-vocabulary tool contribution delivered
  through the real ``PipelineHooks.amend_workflow`` checkpoint (the fake
  tool package boundary) commits, merges via ``merge_workflow_overlay``,
  and the rebuilt ``WorkflowDocument`` compiles: the pipeline stage gated
  by the contribution's stage entry carries the engine ``verify`` block
  with the contributed settings (the container form — the settings block
  authored a key);
- the skip path — a parsed workflow with a settings block and two gated
  stages rides ``apply_skip_stages`` and compiles: the surviving gated
  stage keeps the settings, the skipped stage is absent from the flow and
  its gate drops silently (no error);
- the full chain — a gated ``loop: 2`` stage parsed, skip-merged with
  nothing skipped, amended with a settings block, then compiled: both
  expanded ids carry the SAME ``verify`` (the uniformity invariant — one
  gate per stage name, shared across the loop copies).
"""

from __future__ import annotations

from pathlib import Path

from goga.pipeline import apply_skip_stages
from goga.pipeline.compiler import compile_flow
from goga.pipeline.hooks import (
    PipelineHooks,
    PipelineIdentity,
    ToolContribution,
    WorkflowDecision,
    WorkIdentity,
    merge_workflow_overlay,
)
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowGates,
    WorkflowGateStep,
    WorkflowStage,
    parse_workflow,
)

# The STAGES-format pipeline-file of every scenario — three prompt stages;
# ``build`` is the gated survivor, ``review`` the loop/skip subject.
_PIPELINE_YML = (
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

# The amendment facts of a demo pipeline on a plain branch (the hooks
# suite's ``_facts`` shape).
_PIPELINE_FACT = PipelineIdentity(name="demo", description="Demo pipeline", source="project")
_DECISION_FACT = WorkflowDecision(kind="auto-match", workflow_name="demo")
_WORK_FACT = WorkIdentity(branch="b")


def _write_pipeline(tmp_path: Path) -> Path:
    """Write the STAGES pipeline-file into ``tmp_path`` and return its path."""
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(_PIPELINE_YML)

    return pipeline_path


class TestGatesEndToEnd:
    def test_amendment_chain_compiles_contributed_gates(
        self,
        tmp_path: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A gates-only tool contribution rides the real delivery into the compiled flow.

        The chain: the fake tool's hook contributes a settings block plus a
        stage entry gating ``build`` → ``PipelineHooks.amend_workflow``
        commits it (the emptiness rule counts gates) →
        ``merge_workflow_overlay`` rebuilds the document over ``None`` →
        ``compile_flow``. The flow must carry the engine ``verify`` block on
        ``build`` only, in the container form (the settings block authored
        ``max_iterations``) with the ``1h`` shell timeout default — the
        ungated stages stay untouched.
        """
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register_gates(hooks: object) -> None:
            def gating(self: object, context: object) -> None:
                context.contribute(
                    WorkflowDocument(
                        gates=WorkflowGates(max_iterations=2),
                        stages={
                            "build": WorkflowStage(gates=[WorkflowGateStep(name="Unit tests", script="pytest -q")]),
                        },
                    ),
                )

            hooks.subscribe("pipeline", "amend_workflow", "gating", gating)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register_gates)

        overlay = PipelineHooks().amend_workflow(
            pipeline=_PIPELINE_FACT,
            decision=_DECISION_FACT,
            workflow=None,
            work=_WORK_FACT,
        )

        # The contribution committed (not discarded as empty) and merged.
        assert overlay.workflow is not None
        assert overlay.provenance == ["demo"]
        assert overlay.workflow.gates is not None
        assert overlay.workflow.gates.max_iterations == 2

        pipeline_path = _write_pipeline(tmp_path)
        _pipeline_doc, flow_doc = compile_flow(pipeline_path, tmp_path / "flow.yml", workflow=overlay.workflow)
        text = (tmp_path / "flow.yml").read_text()

        # The gated stage carries the verify block in the CONTAINER form
        # (the settings block authored a key) — steps first, then settings.
        assert text.count("verify:\n") == 1
        assert "  verify:\n    steps:\n" in text
        assert "- name: Unit tests\n" in text
        assert "      run: pytest -q\n" in text
        assert "      timeout: 1h\n" in text
        assert "    max_failures: 2\n" in text

        # The gate landed on build only, at the canonical slot after prompt.
        build_stage = next(stage for stage in flow_doc.stages if stage.id == "build")
        verify = build_stage.fields["verify"]

        assert verify.steps[0].name == "Unit tests"
        assert verify.steps[0].run == "pytest -q"
        assert verify.steps[0].timeout == "1h"
        assert verify.max_failures == 2
        assert all("verify" not in stage.fields for stage in flow_doc.stages if stage.id != "build")

    def test_skip_driven_run_keeps_settings_for_remaining_gated_stages(self, tmp_path: Path) -> None:
        """A skip-merged run compiles the settings onto the surviving gated stage only.

        The chain: ``parse_workflow`` (settings block plus two gated stages)
        → ``apply_skip_stages(["review"])`` (the CLI skip merge — the
        settings block rides the rebuild verbatim, the replacement stage
        carries no gates) → ``compile_flow``. The flow must carry the
        container-form verify on ``build`` with the authored
        ``max_iterations``, the skipped stage must be absent from the flow
        (its gate dropping silently — no error fires).
        """
        workflow = parse_workflow(
            "gates:\n"
            "  max_iterations: 4\n"
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: Unit tests\n"
            "        script: pytest -q\n"
            "  review:\n"
            "    gates:\n"
            "      - name: Lint\n"
            "        script: ruff check .\n",
        )
        merged = apply_skip_stages(workflow, ["review"])

        # The rebuild carried the settings block verbatim; the replacement drops the gate.
        assert merged is not None
        assert merged.gates is workflow.gates
        assert merged.stages["review"].gates is None

        pipeline_path = _write_pipeline(tmp_path)
        _pipeline_doc, flow_doc = compile_flow(pipeline_path, tmp_path / "flow.yml", workflow=merged)
        text = (tmp_path / "flow.yml").read_text()

        # The skipped stage never reached the composition; the survivor kept its gate.
        assert [stage.id for stage in flow_doc.stages] == ["brainstorm", "build"]
        assert "- id: review" not in text
        assert "Lint" not in text

        # The remaining gated stage carries the settings — container form.
        assert text.count("verify:\n") == 1
        assert "  verify:\n    steps:\n" in text
        assert "- name: Unit tests\n" in text
        assert "    max_failures: 4\n" in text

    def test_loop_copies_through_the_full_chain_carry_the_same_gate(self, tmp_path: Path) -> None:
        """A gated loop stage rides every rebuild and gates both expanded ids uniformly.

        The chain: ``parse_workflow`` (a gated ``loop: 2`` stage, no
        settings block) → ``apply_skip_stages([])`` (nothing skipped — the
        no-op identity) → ``merge_workflow_overlay`` (a tool contributes
        the settings block) → ``compile_flow``. Both expanded ids must
        carry the SAME verify object (the design's uniformity invariant —
        one gate per stage name, shared across the loop copies) with the
        amended settings in the container form.
        """
        workflow = parse_workflow(
            "stages:\n  review:\n    loop: 2\n    gates:\n      - name: tests\n        script: pytest -q\n",
        )

        # Nothing skipped — the empty directive is the identity no-op.
        skip_merged = apply_skip_stages(workflow, [])

        assert skip_merged is workflow

        overlay = merge_workflow_overlay(
            skip_merged,
            [ToolContribution(tool="t", document=WorkflowDocument(gates=WorkflowGates(patience=1)))],
        )

        assert overlay.workflow is not None

        pipeline_path = _write_pipeline(tmp_path)
        _pipeline_doc, flow_doc = compile_flow(pipeline_path, tmp_path / "flow.yml", workflow=overlay.workflow)
        text = (tmp_path / "flow.yml").read_text()

        copies = [stage for stage in flow_doc.stages if stage.id.startswith("review")]

        # Both expanded ids exist and carry the same gate — the shared object.
        assert [stage.id for stage in copies] == ["review-1", "review-2"]
        assert text.count("verify:\n") == 2
        assert copies[0].fields["verify"] == copies[1].fields["verify"]
        assert copies[0].fields["verify"].steps[0].run == "pytest -q"

        # The amended settings reached both copies — the container form.
        assert "    review_patience: 1\n" in text
        assert text.count("review_patience: 1\n") == 2
        assert "max_failures" not in text
