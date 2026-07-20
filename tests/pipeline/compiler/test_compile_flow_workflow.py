"""Logic tests for the ``compile_flow`` workflow reconstruction branch.

Covers the Task 6 extension: when ``compile_flow`` is called with a non-``None``
``workflow`` ``WorkflowDocument``, the parsed body is reconstructed on a deep
copy BEFORE ``FlowStage`` assembly. The reconstruction has four facets:
(5a) per-stage agent/prompt overrides injected into the step body's ``command``
and ``description`` slots; (5b) loop-expansion producing ``NAME-1``..``NAME-N``
copies with chain-style internal ``depends_on``; (5c) external ``depends_on``
rewritten to the LAST expanded id (STAGES only — PHASES is handled by position);
and the top-level ``workflow.prompt`` emitted as the first flow-file key.

The ``PipelineDocument`` returned alongside always carries the ORIGINAL parsed
body — workflow reconstruction lives only in ``FlowDocument.stages``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml
from goga.pipeline.compiler import (
    FlowDocument,
    PipelineDocument,
    compile_flow,
)
from goga.pipeline.workflow import WorkflowDocument, WorkflowStage

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "workflow"
_FEATURE_PHASES = _FIXTURES / "phases.yml"
_FEATURE_WORKFLOW = _FIXTURES / "workflow.yml"


def _write_phases_three_step(tmp_path: Path) -> Path:
    """Write a 3-step phases pipeline (A, B, C) and return its path."""
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(
        "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n- name: b\n  title: B\n- name: c\n  title: C\n",
    )
    return pipeline_path


def _write_stages_three_step(tmp_path: Path) -> Path:
    """Write a 3-step stages pipeline (A→B→C authored depends_on) and return its path."""
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(
        "name: T\n"
        "description: T\n"
        "---\n"
        "\n"
        "a:\n"
        "  title: A\n"
        "b:\n"
        "  title: B\n"
        "  depends_on: [a]\n"
        "c:\n"
        "  title: C\n"
        "  depends_on: [b]\n",
    )
    return pipeline_path


def _ids(stages: list) -> list[str]:
    return [stage["id"] for stage in stages]


class TestCompileFlowPerStageOverrides:
    """Sub-step 5a — per-stage agent/prompt overrides."""

    def test_compile_flow_with_workflow_per_stage_overrides(self, tmp_path: Path) -> None:
        """A workflow applies agent+prompt to the matching PHASES stage.

        The matching stage gains ``command`` and ``description`` slots in its
        ``fields``; the ORIGINAL pipeline body keeps neither slot; no top-level
        prompt is emitted (the workflow has none).
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: propose\n  title: Propose\n- name: other\n  title: Other\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"propose": WorkflowStage(agent="codex", prompt="Additional prompt")},
        )

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        assert isinstance(pipeline_doc, PipelineDocument)
        assert isinstance(flow_doc, FlowDocument)
        # The matching stage carries the composed wrapper path and the prompt text.
        assert flow_doc.stages[0].fields["command"] == "/home/goga/bin/codex-as-claude.sh"
        assert flow_doc.stages[0].fields["description"] == "Additional prompt"
        # The non-matching stage is untouched (no command/description slots).
        assert "command" not in flow_doc.stages[1].fields
        assert "description" not in flow_doc.stages[1].fields
        # The ORIGINAL pipeline body has neither slot — reconstruction is isolated.
        assert "command" not in pipeline_doc.body.steps[0].body
        assert "description" not in pipeline_doc.body.steps[0].body
        # The workflow supplied no top-level prompt — the flow-file must not
        # carry a top-level ``prompt:`` key. Use a YAML round-trip rather than a
        # substring check because per-stage ``supervisor_prompt:`` legitimately
        # contains the substring ``prompt:``.
        assert flow_doc.prompt is None
        assert "prompt" not in yaml.safe_load(flow_path.read_text())


class TestCompileFlowLoopExpansion:
    """Sub-steps 5b/5c — loop-expansion and external depends_on rewrite."""

    def test_compile_flow_with_workflow_loop_expansion_stages(self, tmp_path: Path) -> None:
        """STAGES A→B→C with B loop=2 yields [A, B-1, B-2, C] with chained deps.

        B-1 inherits B's external dep (A); B-2 chains to B-1; C's authored dep
        on B is rewritten to the LAST expanded id B-2.
        """
        pipeline_path = _write_stages_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(loop=2)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        assert _ids(stages) == ["a", "b-1", "b-2", "c"]
        assert "depends_on" not in stages[0]
        assert stages[1]["depends_on"] == ["a"]
        assert stages[2]["depends_on"] == ["b-1"]
        # C's authored `depends_on: [b]` is rewritten to the LAST expanded id.
        assert stages[3]["depends_on"] == ["b-2"]

    def test_compile_flow_with_workflow_loop_expansion_phases(self, tmp_path: Path) -> None:
        """PHASES A→B→C with B loop=2 yields [A, B-1, B-2, C] chained by position.

        PHASES uses no explicit external rewrite — list position derives the
        chain: A has none, B-1 depends on A, B-2 on B-1, C (the next original
        step) on the LAST copy B-2.
        """
        pipeline_path = _write_phases_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(loop=2)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        assert _ids(stages) == ["a", "b-1", "b-2", "c"]
        assert "depends_on" not in stages[0]
        assert stages[1]["depends_on"] == ["a"]
        assert stages[2]["depends_on"] == ["b-1"]
        assert stages[3]["depends_on"] == ["b-2"]

    def test_compile_flow_loop_expansion_three_copies(self, tmp_path: Path) -> None:
        """loop=3 produces three copies and rewrites external refs to the LAST (NAME-3)."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "a:\n"
            "  title: A\n"
            "b:\n"
            "  title: B\n"
            "  depends_on: [a]\n"
            "c:\n"
            "  title: C\n"
            "  depends_on: [b]\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(loop=3)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        assert _ids(stages) == ["a", "b-1", "b-2", "b-3", "c"]
        assert stages[1]["depends_on"] == ["a"]
        assert stages[2]["depends_on"] == ["b-1"]
        assert stages[3]["depends_on"] == ["b-2"]
        assert stages[4]["depends_on"] == ["b-3"]

    def test_compile_flow_loop_expansion_preserves_original_body(self, tmp_path: Path) -> None:
        """Loop-expansion never mutates the ORIGINAL parsed body in PipelineDocument."""
        pipeline_path = _write_stages_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(loop=2)})

        pipeline_doc, _flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        # The original body still has exactly three steps with original ids/names.
        assert [step.name for step in pipeline_doc.body.steps] == ["a", "b", "c"]
        assert pipeline_doc.body.steps[1].depends_on == ["a"]


class TestCompileFlowWorkflowEdgeCases:
    """Edge cases — no workflow, unknown stages, top-level prompt."""

    def test_compile_flow_workflow_none_omits_prompt(self, tmp_path: Path) -> None:
        """``compile_flow`` without a workflow writes no top-level ``prompt`` key.

        Per-stage ``supervisor_prompt:`` legitimately contains the substring
        ``prompt:`` — use a YAML round-trip to assert top-level key absence.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: N\ndescription: D\n---\n\n- name: a\n  title: A\n")
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        text = flow_path.read_text()
        assert "prompt" not in yaml.safe_load(text)
        assert "name: N" in text
        assert "description: D" in text

    def test_compile_flow_workflow_unknown_stage_warns_and_skips(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An unknown workflow stage name warns and is skipped; known stages still apply."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: propose\n  title: Propose\n- name: other\n  title: Other\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={
                "missing-stage": WorkflowStage(agent="codex"),
                "propose": WorkflowStage(agent="claude"),
            },
        )

        with caplog.at_level(logging.WARNING, logger="goga.pipeline.compiler.compile_flow"):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

        # The unknown name appears in a WARNING record.
        assert any("missing-stage" in record.getMessage() for record in caplog.records)
        # The known stage still receives the override.
        flow_doc_stages = yaml.safe_load(flow_path.read_text())["stages"]
        propose = next(stage for stage in flow_doc_stages if stage["id"] == "propose")
        assert propose["command"] == "/home/goga/bin/claude-as-claude.sh"
        # The unknown stage leaves no command slot on any output stage.
        assert all("command" not in stage for stage in flow_doc_stages if stage["id"] != "propose")

    def test_compile_flow_workflow_top_level_prompt_emitted(self, tmp_path: Path) -> None:
        """A workflow with a top-level prompt emits it as the first flow-file key."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: N\ndescription: D\n---\n\n- name: a\n  title: A\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(prompt="Global workflow prompt")

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        assert flow_doc.prompt == "Global workflow prompt"
        text = flow_path.read_text()
        assert text.startswith("prompt: |")
        # PipelineDocument body is untouched by the prompt-only workflow.
        assert [step.name for step in pipeline_doc.body.steps] == ["a"]

    def test_compile_flow_workflow_overrides_applied_to_all_loop_copies(self, tmp_path: Path) -> None:
        """Per-stage overrides apply to every expanded copy, not just the first."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: b\n  title: B\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"b": WorkflowStage(agent="codex", prompt="P", loop=2)},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["b-1", "b-2"]
        for stage in stages:
            assert stage["command"] == "/home/goga/bin/codex-as-claude.sh"
            assert stage["description"] == "P"


class TestCompileFlowWorkflowReferenceFixture:
    """The reference ``feature-phases`` fixture compiled with its workflow."""

    def test_feature_phases_fixture_with_workflow_compiles(self, tmp_path: Path) -> None:
        """The reference pipeline + workflow compile without error and apply overrides."""
        from goga.pipeline.workflow import parse_workflow

        pipeline_path = tmp_path / "feature-phases.yml"
        pipeline_path.write_text(_FEATURE_PHASES.read_text())
        flow_path = tmp_path / "flow.yml"
        workflow = parse_workflow(_FEATURE_WORKFLOW)

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        # Top-level workflow prompt is carried through.
        assert flow_doc.prompt is not None
        assert "Example prompt" in flow_doc.prompt
        # Per-stage override on `propose` (agent codex → command slot).
        propose = next(stage for stage in flow_doc.stages if stage.id == "propose")
        assert propose.fields["command"] == "/home/goga/bin/codex-as-claude.sh"
        assert propose.fields["description"] == "Additional prompt\n"
        # Loop-expansion of `propose-review` (loop=2) → propose-review-1, propose-review-2.
        ids = [stage.id for stage in flow_doc.stages]
        assert "propose-review-1" in ids
        assert "propose-review-2" in ids
        # ORIGINAL body still has the un-expanded step names.
        original_names = [step.name for step in pipeline_doc.body.steps]
        assert "propose-review" in original_names
        assert "propose-review-1" not in original_names


def _stage_field_keys_in_text_order(text: str, stage_id: str) -> list[str]:
    """Return one stage's field keys (excluding id/name/depends_on) in textual order.

    Walks the serialized YAML text line by line, isolating the block for
    ``stage_id`` (from ``- id: <stage_id>`` up to the next ``- id:`` or
    end-of-file), and collects the field keys in the order they appear. Mirrors
    the helper in ``test_integration.py``; used to assert canonical key ordering
    of the workflow-injected ``command``/``description`` slots.
    """
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line == f"- id: {stage_id}")
    keys: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("- id: "):
            break
        stripped = line[2:]
        if line.startswith("  ") and not line.startswith("   ") and not stripped.startswith("-") and ":" in stripped:
            key = stripped.split(":", 1)[0]
            if key not in ("id", "name", "depends_on"):
                keys.append(key)
    return keys


class TestCompileFlowWorkflowCanonicalOrder:
    """The workflow-injected ``command``/``description`` slots land in canonical order.

    ``serialize_flow`` emits ``FlowStage.fields`` verbatim, so canonical ordering
    is entirely the compiler's responsibility at assembly time. The pre-existing
    canonical-order test compiles WITHOUT a workflow, so ``command``/``description``
    never appear; this class pins their positions relative to the other known keys.
    """

    def test_workflow_overrides_preserve_canonical_field_order(self, tmp_path: Path) -> None:
        """A stage carrying all known keys + workflow command/description serializes in order.

        The expected serialized field order is ``interactive, command, prompt,
        description, agents, skills`` — ``command``/``description`` (workflow-injected)
        sit in their canonical positions, not wherever the override happened to set them.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        # Body keys deliberately scrambled so the test catches any pass-through
        # of authored order; only canonical order should win.
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "s:\n"
            "  title: S\n"
            "  skills: [goga-propose]\n"
            "  agents: [claude]\n"
            "  prompt: body-prompt\n"
            "  interactive: true\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"s": WorkflowStage(agent="codex", prompt="ov")})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        text = flow_path.read_text()
        assert _stage_field_keys_in_text_order(text, "s") == [
            "interactive",
            "command",
            "prompt",
            "description",
            "agents",
            "skills",
        ]
        # Sanity: the override values landed in the right slots.
        stage = yaml.safe_load(text)["stages"][0]
        assert stage["command"] == "/home/goga/bin/codex-as-claude.sh"
        assert stage["description"] == "ov"


class TestCompileFlowWorkflowStagesOverrideAndDeps:
    """STAGES-format override + external ``depends_on`` rewrite edge cases."""

    def test_workflow_per_stage_override_on_stages_body(self, tmp_path: Path) -> None:
        """Per-stage agent/prompt overrides apply to a STAGES (mapping) body too.

        The existing override test uses a PHASES body; this pins the same
        injection on a ``StageStep`` body (distinct type from ``PhaseStep``).
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "propose:\n"
            "  title: Propose\n"
            "review:\n"
            "  title: Review\n"
            "  depends_on: [propose]\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"propose": WorkflowStage(agent="codex", prompt="P")})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        propose = next(s for s in stages if s["id"] == "propose")
        assert propose["command"] == "/home/goga/bin/codex-as-claude.sh"
        assert propose["description"] == "P"

    def test_workflow_unmatched_depends_on_ref_kept_as_is(self, tmp_path: Path) -> None:
        """An external depends_on ref matching no expanded base-name is kept verbatim (5c).

        STAGES rewrite replaces refs to EXPANDED base-names with the LAST id; a
        ref that matches nothing (a dangling author ref) is left for afm to
        surface — not dropped or rewritten.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "a:\n"
            "  title: A\n"
            "b:\n"
            "  title: B\n"
            "  depends_on: [a]\n"
            "c:\n"
            "  title: C\n"
            "  depends_on: [b, ghost]\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(loop=2)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        c = next(s for s in stages if s["id"] == "c")
        # `b` rewritten to its LAST expanded id; `ghost` survives unchanged.
        assert c["depends_on"] == ["b-2", "ghost"]

    def test_workflow_stages_first_step_no_depends_on_expands_cleanly(self, tmp_path: Path) -> None:
        """Expanding a STAGES step with no authored depends_on keeps copy 1 dep-free.

        The first copy inherits the original (``None``) depends_on — so it must
        serialize WITHOUT a ``depends_on`` key, not an empty/self-referential list.
        Copy 2 chains to copy 1; downstream refs rewrite to the LAST id.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\nb:\n  title: B\n  depends_on: [a]\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"a": WorkflowStage(loop=2)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a-1", "a-2", "b"]
        assert "depends_on" not in stages[0]
        assert stages[1]["depends_on"] == ["a-1"]
        # Downstream authored ref to `a` rewrites to the LAST expanded id.
        assert stages[2]["depends_on"] == ["a-2"]


class TestCompileFlowWorkflowOverrideMatrix:
    """Per-stage override presence/absence — each field injects only its own slot."""

    def test_workflow_agent_only_leaves_no_description_slot(self, tmp_path: Path) -> None:
        """An ``agent``-only override sets ``command`` but NOT ``description``."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\n- name: propose\n  title: Propose\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"propose": WorkflowStage(agent="codex")})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        fields = yaml.safe_load(flow_path.read_text())["stages"][0]
        assert fields["command"] == "/home/goga/bin/codex-as-claude.sh"
        assert "description" not in fields

    def test_workflow_prompt_only_leaves_no_command_slot(self, tmp_path: Path) -> None:
        """A ``prompt``-only override sets ``description`` but NOT ``command``."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\n- name: propose\n  title: Propose\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"propose": WorkflowStage(prompt="only-prompt")})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        fields = yaml.safe_load(flow_path.read_text())["stages"][0]
        assert fields["description"] == "only-prompt"
        assert "command" not in fields
