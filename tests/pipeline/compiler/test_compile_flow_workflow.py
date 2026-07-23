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
    BodyFormat,
    FlowDocument,
    PhaseStep,
    PipelineDocument,
    StageStep,
    StructuralError,
    compile_flow,
)
from goga.pipeline.workflow import WorkflowDocument, WorkflowExtendStage, WorkflowStage

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
    """Return the ``id`` of every stage in order."""
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

    def test_compile_flow_workflow_unknown_stage_raises_structural_error(
        self,
        tmp_path: Path,
    ) -> None:
        """An unknown workflow stage name now raises StructuralError (4pre strict validation).

        The PHASES input carries a ``stages={"missing-stage": ...}`` entry whose
        name matches no pipeline step → ``StructuralError("unknown stage name in
        workflow.stages: missing-stage")`` BEFORE reconstruction. The STAGES
        variant is covered by ``test_compile_flow_rejects_unknown_workflow_stages_name``.
        """
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

        with pytest.raises(
            StructuralError,
            match=r"unknown stage name in workflow\.stages: missing-stage",
        ):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

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
            "  roles: [claude]\n"
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


def _write_stages_propose_review(tmp_path: Path) -> Path:
    """Write a 2-step STAGES pipeline (propose→review) and return its path."""
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
    return pipeline_path


def _write_stages_two_step(tmp_path: Path) -> Path:
    """Write a 2-step STAGES pipeline (a→b) and return its path."""
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(
        "name: T\ndescription: T\n---\n\na:\n  title: A\nb:\n  title: B\n  depends_on: [a]\n",
    )
    return pipeline_path


def _write_stages_single(tmp_path: Path, name: str = "propose") -> Path:
    """Write a 1-step STAGES pipeline and return its path."""
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(
        f"name: T\ndescription: T\n---\n\n{name}:\n  title: {name.capitalize()}\n",
    )
    return pipeline_path


class TestCompileFlowExtendStages:
    """Step 4a0 — ``workflow.extend`` embedding in STAGES-format bodies.

    STAGES derives ``depends_on`` from ``before``/``after`` (two passes). The new
    stage's ``after``-refs become its own ``depends_on`` (verbatim, including
    dangling ones — afm surfaces them); its ``before``-refs cause the new stage's
    name to be appended to each target's ``depends_on`` (existing refs preserved).
    """

    def test_compile_flow_stages_extend_after_sets_depends_on(self, tmp_path: Path) -> None:
        """STAGES extend ``after`` sets the new stage's depends_on to the named stage.

        propose→review with ``extend={extra: after=[review]}`` yields
        [propose, review, extra]; extra depends on review; review's authored dep
        on propose is preserved; propose keeps no depends_on.
        """
        pipeline_path = _write_stages_propose_review(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"extra": WorkflowExtendStage(after=["review"], body={"title": "Extra"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["propose", "review", "extra"]
        propose = next(s for s in stages if s["id"] == "propose")
        review = next(s for s in stages if s["id"] == "review")
        extra = next(s for s in stages if s["id"] == "extra")
        assert extra["depends_on"] == ["review"]
        assert review["depends_on"] == ["propose"]
        assert "depends_on" not in propose

    def test_compile_flow_stages_extend_before_appends_to_target(self, tmp_path: Path) -> None:
        """STAGES extend ``before`` appends the new stage to each target's depends_on.

        propose→review with ``extend={warmup: before=[propose]}`` makes propose
        depend on warmup; warmup itself has no depends_on (no ``after``).
        """
        pipeline_path = _write_stages_propose_review(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"warmup": WorkflowExtendStage(before=["propose"], body={"title": "Warmup"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        propose = next(s for s in stages if s["id"] == "propose")
        warmup = next(s for s in stages if s["id"] == "warmup")
        assert propose["depends_on"] == ["warmup"]
        assert "depends_on" not in warmup

    def test_compile_flow_stages_extend_after_dangling_raises(self, tmp_path: Path) -> None:
        """STAGES extend ``after`` with a dangling ref raises StructuralError (4a0-pre).

        A dangling after-ref naming no stage in the body (and no extend-stage)
        is rejected up front by strict validation — it no longer reaches the
        flow-file verbatim. Mirrors the workflow.stages strict-validation error.
        """
        pipeline_path = _write_stages_propose_review(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"x": WorkflowExtendStage(after=["ghost"], body={"title": "X"})},
        )

        with pytest.raises(
            StructuralError,
            match=r"unknown stage name in workflow\.extend\.x\.after: ghost",
        ):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

    def test_compile_flow_stages_extend_before_dangling_raises(self, tmp_path: Path) -> None:
        """STAGES extend ``before`` with a dangling ref raises StructuralError (4a0-pre).

        propose→review with ``extend={x: before=[ghost]}`` (ghost unknown): the
        before-ref names no stage, so strict validation rejects it — it is no
        longer skipped with a WARNING. Symmetric with the after-direction (both
        dangling directions now error).
        """
        pipeline_path = _write_stages_propose_review(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"x": WorkflowExtendStage(before=["ghost"], body={"title": "X"})},
        )

        with pytest.raises(
            StructuralError,
            match=r"unknown stage name in workflow\.extend\.x\.before: ghost",
        ):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

    def test_compile_flow_stages_extend_cross_reference_resolved(self, tmp_path: Path) -> None:
        """STAGES cross-references between extend-stages resolve (4a0-pre allows them).

        propose→review with ``extend={first: after=[review], second: after=[first]}``:
        ``second``'s after-ref names the extend-stage ``first`` — a valid target
        (extend names are in the valid-name set). Compiles to
        [propose, review, first, second]; first depends on review; second on first.
        """
        pipeline_path = _write_stages_propose_review(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={
                "first": WorkflowExtendStage(after=["review"], body={"title": "First"}),
                "second": WorkflowExtendStage(after=["first"], body={"title": "Second"}),
            },
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        first = next(s for s in stages if s["id"] == "first")
        second = next(s for s in stages if s["id"] == "second")
        assert first["depends_on"] == ["review"]
        assert second["depends_on"] == ["first"]

    def test_compile_flow_stages_extend_before_after_to_skipped_stage_valid(
        self,
        tmp_path: Path,
    ) -> None:
        """A before/after ref to a skip:true stage is valid (it exists at 4a0-pre).

        propose→review with ``stages={review: skip=True}`` and
        ``extend={x: after=[review]}``: review still exists at validation time
        (removed later at 4skip), so the after-ref is NOT flagged as dangling —
        x compiles, then 4skip reconnects x to review's predecessors.
        """
        pipeline_path = _write_stages_propose_review(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"review": WorkflowStage(skip=True)},
            extend={"x": WorkflowExtendStage(after=["review"], body={"title": "X"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["propose", "x"]
        x = next(s for s in stages if s["id"] == "x")
        assert x["depends_on"] == ["propose"]

    def test_compile_flow_stages_extend_preserves_existing_depends_on(self, tmp_path: Path) -> None:
        """STAGES extend ``before`` appends without clobbering an existing depends_on.

        a→b→c with ``extend={x: before=[b, c]}``: b keeps its authored [a] and
        gains x ([a, x]); c keeps its authored [b] and gains x ([b, x]).
        """
        pipeline_path = _write_stages_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"x": WorkflowExtendStage(before=["b", "c"], body={"title": "X"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        b = next(s for s in stages if s["id"] == "b")
        c = next(s for s in stages if s["id"] == "c")
        assert b["depends_on"] == ["a", "x"]
        assert c["depends_on"] == ["b", "x"]

    def test_compile_flow_extend_loop_expansion_rewrites_after_ref(self, tmp_path: Path) -> None:
        """A loop-expanded after-target rewrites the extend after-ref to LAST id.

        a→b with ``stages={b: loop=2}`` and ``extend={x: after=[b]}`` yields
        [a, b-1, b-2, x]; x's after-ref to b is rewritten to b-2 by step 4c.
        """
        pipeline_path = _write_stages_two_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"b": WorkflowStage(loop=2)},
            extend={"x": WorkflowExtendStage(after=["b"], body={"title": "X"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b-1", "b-2", "x"]
        x = next(s for s in stages if s["id"] == "x")
        assert x["depends_on"] == ["b-2"]

    def test_compile_flow_extend_loop_expansion_rewrites_before_ref(self, tmp_path: Path) -> None:
        """A loop-expanded before-ref rewrites the target's appended dep to LAST id.

        a→b with ``stages={x: loop=2}`` and ``extend={x: before=[a]}``: step 4a0
        appends ``x`` to ``a.depends_on``; step 4c rewrites that ref to the LAST
        expanded id ``x-2`` — the symmetric counterpart of the after-direction
        rewrite. Yields [a, b, x-1, x-2] with a depending on x-2.
        """
        pipeline_path = _write_stages_two_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"x": WorkflowStage(loop=2)},
            extend={"x": WorkflowExtendStage(before=["a"], body={"title": "X"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b", "x-1", "x-2"]
        a = next(s for s in stages if s["id"] == "a")
        assert a["depends_on"] == ["x-2"]

    def test_compile_flow_extend_cross_reference_resolved(self, tmp_path: Path) -> None:
        """Two extend-stages cross-referencing each other resolve by name.

        propose with ``extend={first: after=[propose], second: after=[first]}``:
        first depends on propose; second depends on first (cross-ref between
        extend-stages, name-based — pass 2 finds both after pass 1).
        """
        pipeline_path = _write_stages_single(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={
                "first": WorkflowExtendStage(after=["propose"], body={"title": "First"}),
                "second": WorkflowExtendStage(after=["first"], body={"title": "Second"}),
            },
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        first = next(s for s in stages if s["id"] == "first")
        second = next(s for s in stages if s["id"] == "second")
        assert first["depends_on"] == ["propose"]
        assert second["depends_on"] == ["first"]

    def test_compile_flow_extend_title_fallback_to_name(self, tmp_path: Path) -> None:
        """An extend-stage with no ``title`` falls back to its name as display label.

        The display label (``name`` field) is the extend-stage name when the body
        carries no ``title`` — no error, the stage is emitted with that label.
        """
        pipeline_path = _write_stages_single(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={
                "warmup": WorkflowExtendStage(before=["propose"], body={"prompt": "Bootstrap"}),
            },
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        warmup = next(s for s in stages if s["id"] == "warmup")
        assert warmup["name"] == "warmup"
        # The body's prompt lands in the step body (canonical fields inject
        # defaults around it) without raising.
        assert "prompt" in warmup

    def test_compile_flow_extend_override_applies_to_extend_stage(self, tmp_path: Path) -> None:
        """A per-stage override applies to a same-named extend-stage (4a after 4a0).

        propose with ``stages={extra: agent=codex, prompt=...}`` and
        ``extend={extra: ...}``: the extend-stage extra receives both override
        slots — the composed ``command`` (agent) and the ``description`` (prompt).
        """
        pipeline_path = _write_stages_single(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"extra": WorkflowStage(agent="codex", prompt="Extra instructions")},
            extend={"extra": WorkflowExtendStage(after=["propose"], body={"title": "Extra"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        extra = next(s for s in stages if s["id"] == "extra")
        assert extra["command"] == "/home/goga/bin/codex-as-claude.sh"
        assert extra["description"] == "Extra instructions"

    def test_compile_flow_stages_extend_body_reserved_keys_do_not_corrupt(self, tmp_path: Path) -> None:
        """Serializer-reserved ``id``/``name`` in an extend body never corrupt output.

        An extend entry may carry authored ``id``/``name`` keys (e.g. copied from an
        afm stage definition). They must NOT survive into ``FlowStage.fields``: the
        serializer seeds ``id`` from the extend map key and ``name`` from the
        resolved title, so an authored value would otherwise overwrite them and
        silently break the flow-file's identity/dependency chain. Mirrors
        ``parse_dsl`` dropping ``name``/``id`` for original stages.
        """
        pipeline_path = _write_stages_propose_review(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={
                "x": WorkflowExtendStage(
                    after=["review"],
                    body={"title": "X", "id": "evil", "name": "EVIL"},
                ),
            },
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["propose", "review", "x"]
        x = next(s for s in stages if s["id"] == "x")
        assert x["id"] == "x"
        assert x["name"] == "X"
        assert x["depends_on"] == ["review"]


class TestCompileFlowExtendPhases:
    """Step 4a0 — ``workflow.extend`` embedding in PHASES-format bodies.

    PHASES inserts each extend-stage positionally (no explicit ``depends_on`` —
    list position derives it later). A deferred-resolution loop places each stage
    immediately after its LAST resolvable ``after``-target and/or immediately
    before its FIRST resolvable ``before``-target.
    """

    def test_compile_flow_phases_extend_after_inserts_positionally(self, tmp_path: Path) -> None:
        """PHASES extend ``after`` inserts the stage right after the target.

        [a, b, c] with ``extend={x: after=[b]}`` yields [a, b, x, c]; by position
        x depends on b and c depends on x.
        """
        pipeline_path = _write_phases_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"x": WorkflowExtendStage(after=["b"], body={"title": "X"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b", "x", "c"]
        x = next(s for s in stages if s["id"] == "x")
        c = next(s for s in stages if s["id"] == "c")
        assert x["depends_on"] == ["b"]
        assert c["depends_on"] == ["x"]

    def test_compile_flow_phases_extend_before_inserts_positionally(self, tmp_path: Path) -> None:
        """PHASES extend ``before`` inserts the stage right before the target.

        [a, b, c] with ``extend={x: before=[c]}`` yields [a, b, x, c]; by position
        x depends on b and c depends on x.
        """
        pipeline_path = _write_phases_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"x": WorkflowExtendStage(before=["c"], body={"title": "X"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b", "x", "c"]
        x = next(s for s in stages if s["id"] == "x")
        c = next(s for s in stages if s["id"] == "c")
        assert x["depends_on"] == ["b"]
        assert c["depends_on"] == ["x"]

    def test_compile_flow_phases_extend_multi_target_after(self, tmp_path: Path) -> None:
        """PHASES multi-target ``after`` inserts after the LAST (max-index) target.

        [a, b, c] with ``extend={x: after=[a, b]}``: b is the later target, so x
        lands right after b → [a, b, x, c]; x depends on b.
        """
        pipeline_path = _write_phases_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"x": WorkflowExtendStage(after=["a", "b"], body={"title": "X"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b", "x", "c"]
        x = next(s for s in stages if s["id"] == "x")
        assert x["depends_on"] == ["b"]

    def test_compile_flow_phases_extend_same_anchor_preserves_author_order(self, tmp_path: Path) -> None:
        """PHASES stages anchored on the same target stack in authored order.

        [a, b] with ``extend={x: after=[a], y: after=[a]}``: both anchor on
        ``a`` and would otherwise reverse (each ``insert`` shifts the prior
        sibling right while ``a`` stays put). Authored order wins →
        [a, x, y, b]; x depends on a, y on x, b on y. Symmetric with
        ``before=[b]`` (which already advanced naturally) and with the append
        fallback.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n- name: b\n  title: B\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={
                "x": WorkflowExtendStage(after=["a"], body={"title": "X"}),
                "y": WorkflowExtendStage(after=["a"], body={"title": "Y"}),
            },
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "x", "y", "b"]
        x = next(s for s in stages if s["id"] == "x")
        y = next(s for s in stages if s["id"] == "y")
        b = next(s for s in stages if s["id"] == "b")
        assert x["depends_on"] == ["a"]
        assert y["depends_on"] == ["x"]
        assert b["depends_on"] == ["y"]

    def test_compile_flow_phases_extend_after_before_both_consistent(self, tmp_path: Path) -> None:
        """PHASES after+before consistent inserts between the two targets.

        [a, b, c] with ``extend={x: after=[a], before=[c]}``: after-index (1) ≤
        before-index (2), so x lands at the after-index → [a, x, b, c].
        """
        pipeline_path = _write_phases_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"x": WorkflowExtendStage(after=["a"], before=["c"], body={"title": "X"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "x", "b", "c"]
        x = next(s for s in stages if s["id"] == "x")
        b = next(s for s in stages if s["id"] == "b")
        assert x["depends_on"] == ["a"]
        assert b["depends_on"] == ["x"]

    def test_compile_flow_phases_extend_after_before_inconsistent_warns(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """PHASES after+before inconsistent falls back to after-index with a WARNING.

        [a, b, c] with ``extend={x: after=[c], before=[a]}``: after-index (3) >
        before-index (0) — inconsistent; the after-index wins and a WARNING is
        logged → [a, b, c, x]; x depends on c.
        """
        pipeline_path = _write_phases_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"x": WorkflowExtendStage(after=["c"], before=["a"], body={"title": "X"})},
        )

        with caplog.at_level(logging.WARNING, logger="goga.pipeline.compiler.compile_flow"):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b", "c", "x"]
        x = next(s for s in stages if s["id"] == "x")
        assert x["depends_on"] == ["c"]
        assert any("inconsistent" in r.getMessage() for r in caplog.records)

    def test_compile_flow_phases_extend_all_dangling_raises(self, tmp_path: Path) -> None:
        """PHASES extend with a dangling target raises StructuralError (4a0-pre).

        [a, b] with ``extend={x: after=[ghost]}`` (ghost unknown): strict
        validation rejects the dangling after-ref up front — x is no longer
        appended at the end with a WARNING. The direction (before/after) is
        reported in the message.
        """
        pipeline_path = _write_phases_three_step(tmp_path)
        # Use a two-step pipeline by overwriting with [a, b].
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n- name: b\n  title: B\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"x": WorkflowExtendStage(after=["ghost"], body={"title": "X"})},
        )

        with pytest.raises(
            StructuralError,
            match=r"unknown stage name in workflow\.extend\.x\.after: ghost",
        ):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

    def test_compile_flow_phases_extend_loop_expansion_chains_copies(self, tmp_path: Path) -> None:
        """PHASES extend combined with loop-expansion chains copies in place.

        [a, b, c] with ``stages={x: loop=2}`` and ``extend={x: after=[b]}``: step
        4a0 inserts x positionally after b ([a, b, x, c]); step 4b expands x in
        place to x-1, x-2; list position then derives the chain so the successor
        c depends on the LAST copy x-2. Yields [a, b, x-1, x-2, c].
        """
        pipeline_path = _write_phases_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"x": WorkflowStage(loop=2)},
            extend={"x": WorkflowExtendStage(after=["b"], body={"title": "X"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b", "x-1", "x-2", "c"]
        c = next(s for s in stages if s["id"] == "c")
        assert c["depends_on"] == ["x-2"]

    def test_compile_flow_phases_extend_cross_reference_resolved(self, tmp_path: Path) -> None:
        """PHASES cross-references between extend-stages resolve across iterations.

        [a, b] with ``extend={first: after=[a], second: after=[first]}``: first
        places after a in iteration 1; second (whose after-target first is not yet
        placed) defers, then places after first in iteration 2 — the deferred-
        resolution loop's happy path, distinct from the unresolved-cycle fallback.
        Yields [a, first, second, b]; by position second depends on first, b on
        second.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n- name: b\n  title: B\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={
                "first": WorkflowExtendStage(after=["a"], body={"title": "First"}),
                "second": WorkflowExtendStage(after=["first"], body={"title": "Second"}),
            },
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "first", "second", "b"]
        second = next(s for s in stages if s["id"] == "second")
        b = next(s for s in stages if s["id"] == "b")
        assert second["depends_on"] == ["first"]
        assert b["depends_on"] == ["second"]

    def test_compile_flow_phases_extend_cycle_appends_end(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """PHASES mutual before/after between extend-stages appends at end + WARNING.

        [a, b] with ``extend={p: after=[q], q: after=[p]}``: p and q can never
        both resolve → unresolved cycle; both appended at the end with a WARNING
        → [a, b, p, q].
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n- name: b\n  title: B\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={
                "p": WorkflowExtendStage(after=["q"], body={"title": "P"}),
                "q": WorkflowExtendStage(after=["p"], body={"title": "Q"}),
            },
        )

        with caplog.at_level(logging.WARNING, logger="goga.pipeline.compiler.compile_flow"):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b", "p", "q"]
        assert any("unresolved cycle" in r.getMessage() for r in caplog.records)

    def test_compile_flow_phases_extend_body_reserved_keys_do_not_corrupt(self, tmp_path: Path) -> None:
        """Serializer-reserved ``id``/``name`` in a PHASES extend body never corrupt.

        Same guard as the STAGES case: an authored ``id``/``name`` in the extend
        body is dropped so the serializer seeds identity from the extend key and
        the resolved title. PHASES uses the shared ``_extend_step_title_and_body``
        helper, so this pins the guard for the positional-insertion branch too.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n- name: b\n  title: B\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={
                "x": WorkflowExtendStage(
                    after=["a"],
                    body={"title": "X", "id": "evil", "name": "EVIL"},
                ),
            },
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "x", "b"]
        x = next(s for s in stages if s["id"] == "x")
        assert x["id"] == "x"
        assert x["name"] == "X"


class TestCompileFlowExtendRegression:
    """Step 4a0 regressions — no-workflow / empty-extend / original-body preservation."""

    def test_compile_flow_extend_workflow_none_regression(self, tmp_path: Path) -> None:
        """``compile_flow`` with workflow=None never runs 4a0 (no extend in output).

        The flow-file carries the authored stages verbatim; no extend key is
        synthesized and the step sequence is unchanged.
        """
        pipeline_path = _write_stages_two_step(tmp_path)
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b"]
        assert all("extend" not in stage for stage in stages)

    def test_compile_flow_extend_empty_extend_map_noop(self, tmp_path: Path) -> None:
        """An empty ``extend`` map is a no-op (early-exit), equivalent to no extend.

        a→b with ``extend={}`` yields the same [a, b] sequence and authored
        depends_on as a workflow without extend.
        """
        pipeline_path = _write_stages_two_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(extend={})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b"]
        b = next(s for s in stages if s["id"] == "b")
        assert b["depends_on"] == ["a"]

    def test_compile_flow_extend_preserves_original_body(self, tmp_path: Path) -> None:
        """Extend-stages land only in ``FlowDocument.stages``; ``PipelineDocument.body`` stays original.

        The ``PipelineDocument.body`` carries the ORIGINAL parsed steps (no
        extend-stage), while the ``FlowDocument.stages`` carry the embedded
        extend-stage — the reconstruction never leaks into the parsed body.
        """
        pipeline_path = _write_stages_propose_review(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"extra": WorkflowExtendStage(after=["review"], body={"title": "Extra"})},
        )

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        # ORIGINAL body — only the authored propose/review steps.
        assert [step.name for step in pipeline_doc.body.steps] == ["propose", "review"]
        # FlowDocument carries the embedded extend-stage.
        assert [stage.id for stage in flow_doc.stages] == ["propose", "review", "extra"]


class TestCompileFlowSkillsMerge:
    """Trace 4 — skills-merge (pipeline-file skills + workflow-stage skills).

    The compiler merges the stage's pipeline-file ``skills`` (first, position
    preserved) with the workflow-stage ``skills`` override, deduplicating by
    value. An explicit stages-block is the only source of a skills override —
    inline-extend body skills are verbatim, never merged.
    """

    def test_compile_flow_skills_merge_dedup(self, tmp_path: Path) -> None:
        """Pipeline skills keep their position; workflow skills append, dups dropped.

        pipeline ``skills:[goga-propose]`` + workflow ``stages.propose.skills:[web-search, goga-propose]``
        → ``fields["skills"] == ["goga-propose", "web-search"]`` (the duplicate
        ``goga-propose`` from the workflow side is dropped, pipeline position wins).
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: propose\n  title: Propose\n  skills:\n    - goga-propose\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"propose": WorkflowStage(skills=["web-search", "goga-propose"])})

        _, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        fields = flow_doc.stages[0].fields
        assert fields["skills"] == ["goga-propose", "web-search"]

    def test_compile_flow_skills_merge_both_empty_no_key(self, tmp_path: Path) -> None:
        """Both pipeline and workflow skills empty → no ``skills`` key at all.

        pipeline carries no ``skills``; workflow ``stages.x.skills: []``. The merge
        is empty → ``None`` → the slot is left untouched, so the field is absent
        (NOT ``skills: null``) in the assembled fields.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\n- name: x\n  title: X\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"x": WorkflowStage(skills=[])})

        _, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        assert "skills" not in flow_doc.stages[0].fields

    def test_compile_flow_extend_skills_not_merged_verbatim(self, tmp_path: Path) -> None:
        """An extend-stage body carries ``skills`` verbatim (no pipeline side, no merge).

        The extend entry ``extra`` has ``skills:[audit]`` in its body and no matching
        stages-block, so the effective override has ``skills=None`` and the merge
        branch never runs. The body skills survive untouched → ``["audit"]``.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\npropose:\n  title: Propose\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={
                "extra": WorkflowExtendStage(after=["propose"], body={"title": "Extra", "skills": ["audit"]}),
            },
        )

        _, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        extra = next(stage for stage in flow_doc.stages if stage.id == "extra")
        assert extra.fields["skills"] == ["audit"]

    def test_compile_flow_extend_body_skills_merged_with_stages_block(self, tmp_path: Path) -> None:
        """Extend-body skills merge with a matching stages-block ``skills`` override.

        When an extend entry's name ALSO appears in ``stages`` with a ``skills``
        override, the extend body's own ``skills`` participate in the merge — the
        only path where extend-body skills merge rather than pass verbatim:
        extend-body skills first, then the stages-block skills, deduplicated.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\npropose:\n  title: Propose\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"extra": WorkflowStage(skills=["web-search"])},
            extend={
                "extra": WorkflowExtendStage(after=["propose"], body={"title": "Extra", "skills": ["audit"]}),
            },
        )

        _, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        extra = next(stage for stage in flow_doc.stages if stage.id == "extra")
        # Extend-body skills first, stages-block skills appended, deduplicated.
        assert extra.fields["skills"] == ["audit", "web-search"]


class TestCompileFlowEffectiveOverrides:
    """Trace 4/5 — effective override (inline extend → stages overlay) + effective loop.

    Inline-extend ``agent``/``loop`` seed the DEFAULT override; an explicit
    stages-block entry overlays per-field and WINS whenever its field is not
    ``None``. Loop-expansion reads the effective ``loop`` (stages OR inline).
    """

    def test_compile_flow_effective_agent_inline_fallback(self, tmp_path: Path) -> None:
        """An inline-extend ``agent`` applies with no matching stages-block.

        extend ``warmup`` inline ``agent: codex``, no ``stages.warmup``: the
        effective override carries the inline agent, composing the wrapper command.
        The inline ``agent``/``loop`` never leak as separate flow-file keys.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\npropose:\n  title: Propose\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"warmup": WorkflowExtendStage(after=["propose"], agent="codex", body={"title": "Warmup"})},
        )

        _, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        warmup = next(stage for stage in flow_doc.stages if stage.id == "warmup")
        assert warmup.fields["command"] == "/home/goga/bin/codex-as-claude.sh"
        # Inline agent/loop must not leak as separate keys (Trace 6 non-leak).
        assert "agent" not in warmup.fields
        assert "loop" not in warmup.fields

    def test_compile_flow_stages_block_wins_per_field_over_inline(self, tmp_path: Path) -> None:
        """Stages-block agent wins per-field while inline loop still applies.

        extend ``warmup`` inline ``agent: codex, loop: 3``; explicit ``stages.warmup.agent: claude``
        (no loop). Effective = agent claude (stages wins), loop 3 (stages loop is
        None → inline fallback). So the command composes ``claude`` (NOT codex) and
        the stage expands to ``warmup-1..3``.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\npropose:\n  title: Propose\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"warmup": WorkflowStage(agent="claude")},
            extend={
                "warmup": WorkflowExtendStage(after=["propose"], agent="codex", loop=3, body={"title": "Warmup"}),
            },
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert [stage["id"] for stage in stages] == ["propose", "warmup-1", "warmup-2", "warmup-3"]
        # Every warmup copy composes the stages-block agent (claude), not the inline codex.
        for stage in stages[1:]:
            assert stage["command"] == "/home/goga/bin/claude-as-claude.sh"

    def test_compile_flow_effective_inline_extend_loop_expansion(self, tmp_path: Path) -> None:
        """An inline-extend ``loop`` expands the stage with no matching stages-block.

        extend ``warmup`` inline ``loop: 3`` (no stages-block): the effective
        override carries the inline loop → expansion to ``warmup-1..3``. Symmetric
        with the stages-``loop`` expansion path.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\npropose:\n  title: Propose\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"warmup": WorkflowExtendStage(after=["propose"], loop=3, body={"title": "Warmup"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert [stage["id"] for stage in stages] == ["propose", "warmup-1", "warmup-2", "warmup-3"]

    def test_compile_flow_explicit_stages_loop_wins_over_inline_extend_loop(self, tmp_path: Path) -> None:
        """An explicit stages-``loop`` wins per-field over an inline-extend ``loop``.

        extend ``warmup`` inline ``loop: 3``; explicit ``stages.warmup.loop: 2``.
        Effective loop = 2 (stages wins) → expansion to ``warmup-1..2`` only, NOT
        the inline 3.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\npropose:\n  title: Propose\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"warmup": WorkflowStage(loop=2)},
            extend={"warmup": WorkflowExtendStage(after=["propose"], loop=3, body={"title": "Warmup"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert [stage["id"] for stage in stages] == ["propose", "warmup-1", "warmup-2"]


class TestCompileFlowReconstructionHelpers:
    """Direct unit tests for the private reconstruction helpers.

    ``_merge_skills`` and ``_effective_overrides`` are internal implementation
    helpers (not on the facade); they are exercised directly via import to pin
    their pure, deterministic behavior independently of the full compile pipeline.
    """

    def test_merge_skills_dedup_pipeline_first(self) -> None:
        """Pipeline skills precede workflow skills; duplicates drop by first occurrence."""
        from goga.pipeline.compiler.compile_flow import _merge_skills

        assert _merge_skills(["a", "b"], ["b", "c"]) == ["a", "b", "c"]
        # Pipeline position is preserved even when a workflow skill would reorder.
        assert _merge_skills(["goga-propose"], ["web-search", "goga-propose"]) == ["goga-propose", "web-search"]

    def test_merge_skills_both_empty_returns_none(self) -> None:
        """All empty/None combinations return ``None`` (the no-key marker)."""
        from goga.pipeline.compiler.compile_flow import _merge_skills

        assert _merge_skills(None, None) is None
        assert _merge_skills([], []) is None
        assert _merge_skills(None, []) is None
        assert _merge_skills([], None) is None

    def test_merge_skills_one_side_only(self) -> None:
        """A single non-empty side yields that side's skills (deduplicated)."""
        from goga.pipeline.compiler.compile_flow import _merge_skills

        assert _merge_skills(None, ["a"]) == ["a"]
        assert _merge_skills(["a"], None) == ["a"]
        assert _merge_skills(["a", "a"], None) == ["a"]

    def test_merge_skills_non_list_pipeline_does_not_crash(self) -> None:
        """A non-list pipeline ``skills`` (verbatim, unvalidated) is coerced to empty.

        ``parse_dsl`` passes pipeline body fields through verbatim, so a malformed
        ``skills: just-a-string`` reaches the merge. The merge must not raise — it
        treats the non-list value as empty and applies the workflow skills alone.
        """
        from goga.pipeline.compiler.compile_flow import _merge_skills

        # A truthy non-list value would crash ``value + []`` without the guard.
        assert _merge_skills("web-search", ["audit"]) == ["audit"]
        assert _merge_skills(42, ["audit"]) == ["audit"]
        # Non-list pipeline + no workflow override → empty → None (no key).
        assert _merge_skills({"a": 1}, None) is None

    def test_merge_skills_unhashable_or_non_str_pipeline_does_not_crash(self) -> None:
        """A pipeline ``skills`` list with unhashable/non-str elements is filtered.

        ``parse_dsl`` passes pipeline body fields through verbatim, so a malformed
        ``skills`` list may carry dicts, nested lists, or non-str scalars. The merge
        must not raise ``TypeError: unhashable type`` on ``skill not in seen``, and
        must keep only ``str`` skills so the merged result stays a ``list[str]``.
        """
        from goga.pipeline.compiler.compile_flow import _merge_skills

        # Unhashable element (dict) would crash ``skill not in seen`` without the guard.
        assert _merge_skills([{"name": "web-search"}], ["audit"]) == ["audit"]
        # Nested list element (also unhashable).
        assert _merge_skills([["web-search"]], ["audit"]) == ["audit"]
        # Hashable non-str element dropped (keeps the ``list[str]`` contract).
        assert _merge_skills([1, 2], ["audit"]) == ["audit"]
        # Mix of valid str and malformed elements → only valid str kept.
        assert _merge_skills(["web-search", {"x": 1}, 3], ["audit"]) == ["web-search", "audit"]

    def test_effective_overrides_inline_seed_only(self) -> None:
        """An extend-only entry seeds an effective stage carrying agent/loop only."""
        from goga.pipeline.compiler.compile_flow import _effective_overrides

        workflow = WorkflowDocument(
            extend={"warmup": WorkflowExtendStage(after=["propose"], agent="codex", loop=3, body={"title": "W"})},
        )

        effective = _effective_overrides(workflow)

        assert set(effective.keys()) == {"warmup"}
        assert effective["warmup"].agent == "codex"
        assert effective["warmup"].loop == 3
        # Inline extend carries no prompt/skills override.
        assert effective["warmup"].prompt is None
        assert effective["warmup"].skills is None

    def test_effective_overrides_stages_block_only(self) -> None:
        """A stages-only entry passes through verbatim (no inline fallback involved)."""
        from goga.pipeline.compiler.compile_flow import _effective_overrides

        workflow = WorkflowDocument(stages={"propose": WorkflowStage(agent="claude", prompt="P", skills=["s"])})

        effective = _effective_overrides(workflow)

        assert set(effective.keys()) == {"propose"}
        assert effective["propose"].agent == "claude"
        assert effective["propose"].prompt == "P"
        assert effective["propose"].loop is None
        assert effective["propose"].skills == ["s"]

    def test_effective_overrides_per_field_overlay(self) -> None:
        """A stages-block overlays an inline seed per-field, winning when not None."""
        from goga.pipeline.compiler.compile_flow import _effective_overrides

        workflow = WorkflowDocument(
            stages={"warmup": WorkflowStage(agent="claude")},
            extend={"warmup": WorkflowExtendStage(after=["propose"], agent="codex", loop=3, body={"title": "W"})},
        )

        effective = _effective_overrides(workflow)

        # Stages agent wins (not None); inline loop falls back (stages loop is None).
        assert effective["warmup"].agent == "claude"
        assert effective["warmup"].loop == 3
        # Prompt/skills come from the stages-block (None here — no inline equivalent).
        assert effective["warmup"].prompt is None
        assert effective["warmup"].skills is None

    def test_effective_overrides_overlay_passes_through_prompt_and_skills(self) -> None:
        """The overlay branch passes stages-block prompt/skills straight through.

        A name present in BOTH ``extend`` (inline seed) and ``stages`` (block)
        takes the overlay branch (not the verbatim ``effective[name] = stg``
        branch). Its ``prompt`` and ``skills`` must come from the stages-block
        entry even though the inline seed has no equivalent — pinning
        ``prompt=stg.prompt`` / ``skills=stg.skills`` against a regression to
        ``None``.
        """
        from goga.pipeline.compiler.compile_flow import _effective_overrides

        workflow = WorkflowDocument(
            stages={"warmup": WorkflowStage(prompt="P", skills=["web-search"])},
            extend={"warmup": WorkflowExtendStage(after=["propose"], agent="codex", loop=3, body={"title": "W"})},
        )

        effective = _effective_overrides(workflow)

        # Inline agent/loop fall back (stages agent/loop are None).
        assert effective["warmup"].agent == "codex"
        assert effective["warmup"].loop == 3
        # The stages-block prompt/skills pass through (NOT None).
        assert effective["warmup"].prompt == "P"
        assert effective["warmup"].skills == ["web-search"]

    def test_effective_overrides_empty_workflow(self) -> None:
        """A workflow with only a top-level prompt yields an empty effective map."""
        from goga.pipeline.compiler.compile_flow import _effective_overrides

        assert _effective_overrides(WorkflowDocument(prompt="P")) == {}


class TestCompileFlowStrictValidateStageNames:
    """Step 4pre — strict validation of ``workflow.stages`` names.

    Every ``workflow.stages`` name must exist in the full name set (original
    plus embedded extend) before any skip removal; an unknown name is a
    ``StructuralError`` (replacing the former silent WARNING+skip). Format-
    agnostic — ``step.name`` is the identity key for both ``StageStep`` and
    ``PhaseStep``.
    """

    def test_strict_validate_known_name_passes(self) -> None:
        """A name present in ``steps`` raises nothing (no-op for valid input)."""
        from goga.pipeline.compiler.compile_flow import _strict_validate_stage_names

        steps = [StageStep(name="a", title="A", depends_on=None, body={})]
        workflow = WorkflowDocument(stages={"a": WorkflowStage()})

        _strict_validate_stage_names(steps, workflow)  # no raise

    def test_strict_validate_unknown_name_raises_with_exact_message(self) -> None:
        """A name absent from ``steps`` raises StructuralError with the exact message."""
        from goga.pipeline.compiler.compile_flow import _strict_validate_stage_names

        steps = [StageStep(name="a", title="A", depends_on=None, body={})]
        workflow = WorkflowDocument(stages={"ghost": WorkflowStage()})

        with pytest.raises(
            StructuralError,
            match=r"unknown stage name in workflow\.stages: ghost",
        ):
            _strict_validate_stage_names(steps, workflow)

    def test_strict_validate_unknown_name_raises_for_phase_step(self) -> None:
        """4pre is format-agnostic: an unknown name raises for a ``PhaseStep`` body too."""
        from goga.pipeline.compiler.compile_flow import _strict_validate_stage_names

        steps = [PhaseStep(name="a", title="A", body={})]
        workflow = WorkflowDocument(stages={"ghost": WorkflowStage()})

        with pytest.raises(
            StructuralError,
            match=r"unknown stage name in workflow\.stages: ghost",
        ):
            _strict_validate_stage_names(steps, workflow)

    def test_strict_validate_skipped_existing_name_not_flagged(self) -> None:
        """A name that exists (and is skipped) is NOT flagged — it is in valid_names.

        4pre runs BEFORE skip removal; a genuinely-existing skipped stage stays
        valid here and is removed later at 4skip.
        """
        from goga.pipeline.compiler.compile_flow import _strict_validate_stage_names

        steps = [StageStep(name="a", title="A", depends_on=None, body={})]
        workflow = WorkflowDocument(stages={"a": WorkflowStage(skip=True)})

        _strict_validate_stage_names(steps, workflow)  # no raise

    def test_strict_validate_empty_stages_is_noop(self) -> None:
        """An empty ``workflow.stages`` map validates nothing (no raise)."""
        from goga.pipeline.compiler.compile_flow import _strict_validate_stage_names

        steps = [StageStep(name="a", title="A", depends_on=None, body={})]
        workflow = WorkflowDocument(prompt="P")  # no stages

        _strict_validate_stage_names(steps, workflow)  # no raise

    def test_strict_validate_extend_embedded_name_passes(self) -> None:
        """A name embedded by 4a0 extend is valid — it is in ``steps`` after embed.

        Mirrors the contract: 4pre runs AFTER 4a0, so an extend-embedded name is
        a valid ``workflow.stages`` target (the caller passes the post-embed steps).
        """
        from goga.pipeline.compiler.compile_flow import _strict_validate_stage_names

        steps = [
            StageStep(name="propose", title="Propose", depends_on=None, body={}),
            StageStep(name="warmup", title="Warmup", depends_on=None, body={}),
        ]
        workflow = WorkflowDocument(stages={"warmup": WorkflowStage()})

        _strict_validate_stage_names(steps, workflow)  # no raise


class TestCompileFlowStrictValidateEndToEnd:
    """End-to-end ``compile_flow`` coverage for the 4pre strict-validation pass."""

    def test_compile_flow_rejects_unknown_workflow_stages_name(self, tmp_path: Path) -> None:
        """STAGES: an unknown ``workflow.stages`` name raises StructuralError.

        The single-step STAGES pipeline names only ``propose``; the workflow
        targets ``ghost`` (no such step) → ``StructuralError`` before
        reconstruction, and no flow-file is written.
        """
        pipeline_path = _write_stages_single(tmp_path, "propose")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"ghost": WorkflowStage(skip=False)})

        with pytest.raises(
            StructuralError,
            match=r"unknown stage name in workflow\.stages: ghost",
        ):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

        assert not flow_path.exists()

    def test_compile_flow_rejects_unknown_workflow_stages_name_phases(self, tmp_path: Path) -> None:
        """PHASES: 4pre is format-agnostic — an unknown name raises StructuralError."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\n- name: a\n  title: A\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"ghost": WorkflowStage(skip=False)})

        with pytest.raises(
            StructuralError,
            match=r"unknown stage name in workflow\.stages: ghost",
        ):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

    def test_compile_flow_unknown_name_with_extend_set_valid(self, tmp_path: Path) -> None:
        """STAGES: an extend-embedded name is valid at 4pre — NOT flagged — and its override applies.

        ``propose`` pipeline + ``extend.warmup`` + ``stages.warmup: {agent: codex}``:
        the extend-embedded ``warmup`` is in ``steps`` after 4a0, so 4pre does NOT
        flag it, and the per-stage override still applies (the composed command).
        """
        pipeline_path = _write_stages_single(tmp_path, "propose")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"warmup": WorkflowStage(agent="codex")},
            extend={"warmup": WorkflowExtendStage(after=["propose"], body={"title": "Warmup"})},
        )

        _, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        warmup = next(stage for stage in flow_doc.stages if stage.id == "warmup")
        assert warmup.fields["command"] == "/home/goga/bin/codex-as-claude.sh"


def _write_stages_four_step(tmp_path: Path) -> Path:
    """Write a 4-step STAGES pipeline (A→B→C→D authored depends_on) and return its path."""
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
        "  depends_on: [b]\n"
        "d:\n"
        "  title: D\n"
        "  depends_on: [c]\n",
    )
    return pipeline_path


def _write_phases_four_step(tmp_path: Path) -> Path:
    """Write a 4-step PHASES pipeline (A, B, C, D) and return its path."""
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(
        "name: T\ndescription: T\n---\n\n"
        "- name: a\n  title: A\n"
        "- name: b\n  title: B\n"
        "- name: c\n  title: C\n"
        "- name: d\n  title: D\n",
    )
    return pipeline_path


class TestCompileFlowResolveSkipHelper:
    """Direct unit tests for the private ``_resolve_skip`` transitive resolver.

    ``_resolve_skip`` walks a skipped stage's ``depends_on`` to its transitive
    non-skipped predecessors. It is pure and deterministic, so it is pinned here
    independently of the full compile pipeline (mirrors
    ``TestCompileFlowReconstructionHelpers``).
    """

    def test_resolve_skip_linear_chain(self) -> None:
        """resolve(S) returns S's single non-skipped predecessor."""
        from goga.pipeline.compiler.compile_flow import _resolve_skip

        steps_by_name = {
            "a": StageStep(name="a", title="A", depends_on=None, body={}),
            "b": StageStep(name="b", title="B", depends_on=["a"], body={}),
        }

        # b skipped; resolving b yields its non-skipped predecessor a.
        assert _resolve_skip("b", steps_by_name, {"b"}) == ["a"]

    def test_resolve_skip_transitive_chain(self) -> None:
        """resolve walks through consecutive skipped stages transitively."""
        from goga.pipeline.compiler.compile_flow import _resolve_skip

        steps_by_name = {
            "a": StageStep(name="a", title="A", depends_on=None, body={}),
            "b": StageStep(name="b", title="B", depends_on=["a"], body={}),
            "c": StageStep(name="c", title="C", depends_on=["b"], body={}),
        }

        # b and c both skipped; resolving c walks c→b→a (the non-skipped leaf).
        assert _resolve_skip("c", steps_by_name, {"b", "c"}) == ["a"]

    def test_resolve_skip_cycle_terminates_via_seen(self) -> None:
        """A depends_on cycle among skipped stages terminates (no infinite loop)."""
        from goga.pipeline.compiler.compile_flow import _resolve_skip

        steps_by_name = {
            "a": StageStep(name="a", title="A", depends_on=["b"], body={}),
            "b": StageStep(name="b", title="B", depends_on=["a"], body={}),
        }

        # a↔b cycle, both skipped → no non-skipped predecessor resolves → [].
        assert _resolve_skip("a", steps_by_name, {"a", "b"}) == []

    def test_resolve_skip_dangling_ref_preserved(self) -> None:
        """A non-skipped (possibly dangling) ref is kept verbatim."""
        from goga.pipeline.compiler.compile_flow import _resolve_skip

        steps_by_name = {
            "b": StageStep(name="b", title="B", depends_on=["ghost"], body={}),
        }

        # b skipped; ghost is non-skipped (and absent from the map) → preserved.
        assert _resolve_skip("b", steps_by_name, {"b"}) == ["ghost"]

    def test_resolve_skip_none_or_empty_depends_on_yields_empty(self) -> None:
        """A skipped stage with no (or empty) depends_on resolves to []."""
        from goga.pipeline.compiler.compile_flow import _resolve_skip

        steps_by_name = {
            "b": StageStep(name="b", title="B", depends_on=None, body={}),
            "c": StageStep(name="c", title="C", depends_on=[], body={}),
        }

        assert _resolve_skip("b", steps_by_name, {"b"}) == []
        assert _resolve_skip("c", steps_by_name, {"c"}) == []

    def test_resolve_skip_missing_step_yields_empty(self) -> None:
        """Resolving a name with no step in the map yields [] (no crash)."""
        from goga.pipeline.compiler.compile_flow import _resolve_skip

        assert _resolve_skip("absent", {}, {"absent"}) == []


class TestCompileFlowRemoveSkippedStagesHelper:
    """Direct unit tests for the private ``_remove_skipped_stages`` dispatcher.

    Pins the STAGES reconnect / PHASES positional-drop semantics, the explicit
    ``[]`` collapse, and first-occurrence dedup directly on the helper.
    """

    def test_fast_path_noop_when_nothing_skipped(self) -> None:
        """No skipped stages → steps unchanged (no mutation)."""
        from goga.pipeline.compiler.compile_flow import _remove_skipped_stages

        steps = [
            StageStep(name="a", title="A", depends_on=None, body={}),
            StageStep(name="b", title="B", depends_on=["a"], body={}),
        ]
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=False)})

        _remove_skipped_stages(steps, workflow, BodyFormat.STAGES)

        assert [step.name for step in steps] == ["a", "b"]
        assert steps[1].depends_on == ["a"]

    def test_stages_reconnect_and_remove(self) -> None:
        """STAGES: a dependent's depends_on is reconnected, then the skipped step removed."""
        from goga.pipeline.compiler.compile_flow import _remove_skipped_stages

        steps = [
            StageStep(name="a", title="A", depends_on=None, body={}),
            StageStep(name="b", title="B", depends_on=["a"], body={}),
            StageStep(name="c", title="C", depends_on=["b"], body={}),
        ]
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=True)})

        _remove_skipped_stages(steps, workflow, BodyFormat.STAGES)

        assert [step.name for step in steps] == ["a", "c"]
        # c's authored ref to b is reconnected to b's predecessor a.
        assert steps[1].depends_on == ["a"]

    def test_phases_positional_remove(self) -> None:
        """PHASES: skipped steps drop; depends_on re-derives by position downstream."""
        from goga.pipeline.compiler.compile_flow import _remove_skipped_stages

        steps = [
            PhaseStep(name="a", title="A", body={}),
            PhaseStep(name="b", title="B", body={}),
            PhaseStep(name="c", title="C", body={}),
        ]
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=True)})

        _remove_skipped_stages(steps, workflow, BodyFormat.PHASES)

        assert [step.name for step in steps] == ["a", "c"]

    def test_explicit_empty_on_collapse(self) -> None:
        """A dependent that loses its only dep to a skipped root writes [] (not None)."""
        from goga.pipeline.compiler.compile_flow import _remove_skipped_stages

        steps = [
            # b is a root with no ancestors.
            StageStep(name="b", title="B", depends_on=None, body={}),
            StageStep(name="c", title="C", depends_on=["b"], body={}),
        ]
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=True)})

        _remove_skipped_stages(steps, workflow, BodyFormat.STAGES)

        assert [step.name for step in steps] == ["c"]
        # Explicit empty list (→ ``depends_on: []``), NOT None (→ no key).
        assert steps[0].depends_on == []

    def test_dedup_preserves_first_occurrence_order(self) -> None:
        """Two refs resolving to the same predecessor collapse to one (first occurrence)."""
        from goga.pipeline.compiler.compile_flow import _remove_skipped_stages

        steps = [
            StageStep(name="a", title="A", depends_on=None, body={}),
            StageStep(name="b", title="B", depends_on=["a"], body={}),
            StageStep(name="c", title="C", depends_on=["a"], body={}),
            # d depends on b and c, both of which depend on a.
            StageStep(name="d", title="D", depends_on=["b", "c"], body={}),
        ]
        workflow = WorkflowDocument(
            stages={"b": WorkflowStage(skip=True), "c": WorkflowStage(skip=True)},
        )

        _remove_skipped_stages(steps, workflow, BodyFormat.STAGES)

        assert [step.name for step in steps] == ["a", "d"]
        # b→a and c→a both collapse to a single a (no duplicate).
        assert steps[1].depends_on == ["a"]


class TestCompileFlowSkipRemovalStages:
    """Step 4skip end-to-end — STAGES skip removal + transparent reconnection."""

    def test_compile_flow_stages_skip_middle_reconnects_chain(self, tmp_path: Path) -> None:
        """STAGES A→B→C→D, skip B → [a, c, d]; C reconnects to [a]; D unchanged [c]."""
        pipeline_path = _write_stages_four_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=True)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "c", "d"]
        c = next(s for s in stages if s["id"] == "c")
        d = next(s for s in stages if s["id"] == "d")
        # C's authored dep on B is reconnected to B's predecessor A.
        assert c["depends_on"] == ["a"]
        # D's authored dep on C is unaffected.
        assert d["depends_on"] == ["c"]

    def test_compile_flow_stages_skip_two_consecutive_reconnects_transitively(
        self,
        tmp_path: Path,
    ) -> None:
        """STAGES A→B→C→D, skip B and C → D reconnects to the transitive [a]."""
        pipeline_path = _write_stages_four_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"b": WorkflowStage(skip=True), "c": WorkflowStage(skip=True)},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "d"]
        d = next(s for s in stages if s["id"] == "d")
        # D's dep on C resolves transitively C→B→A to the single non-skipped [a].
        assert d["depends_on"] == ["a"]

    def test_compile_flow_stages_skip_diamond_reconnects_to_common_pred(
        self,
        tmp_path: Path,
    ) -> None:
        """Skip B in a diamond → D reconnects to [a, c], order preserved, no dup.

        A is a common predecessor of both B and C; D depends on B and C. Skipping
        B rewrites D's B-ref to A, while the C-ref stays — yielding [a, c] in
        source order, with no duplicate even though A is also C's predecessor.
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
            "  depends_on: [a]\n"
            "d:\n"
            "  title: D\n"
            "  depends_on: [b, c]\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=True)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "c", "d"]
        d = next(s for s in stages if s["id"] == "d")
        # B-ref → A (reconnected); C-ref stays; A appears once even though it is
        # the predecessor of both B and C.
        assert d["depends_on"] == ["a", "c"]

    def test_compile_flow_stages_skip_collapses_to_explicit_empty_depends_on(
        self,
        tmp_path: Path,
    ) -> None:
        """C depends only on skipped B (a root) → ``depends_on: []`` (explicit empty ≠ None)."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "b:\n"
            "  title: B\n"
            "c:\n"
            "  title: C\n"
            "  depends_on: [b]\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=True)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["c"]
        c = next(s for s in stages if s["id"] == "c")
        # B had no ancestors, so C's dep on B collapses to an explicit empty list
        # (serialized as ``depends_on: []``), NOT omitted.
        assert c["depends_on"] == []

    def test_compile_flow_stages_skip_first_step_reconnects_to_empty(
        self,
        tmp_path: Path,
    ) -> None:
        """STAGES A→B, skip A (the first step) → B reconnects to []."""
        pipeline_path = _write_stages_two_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"a": WorkflowStage(skip=True)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["b"]
        b = next(s for s in stages if s["id"] == "b")
        # A had no predecessors → B's dep collapses to an explicit empty list.
        assert b["depends_on"] == []

    def test_compile_flow_stages_skip_last_step_has_no_dependents(
        self,
        tmp_path: Path,
    ) -> None:
        """STAGES A→B, skip B (the last step) → [a]; A untouched (no reconnection)."""
        pipeline_path = _write_stages_two_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=True)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a"]
        # A had no authored depends_on (first step) and nothing depended on B.
        assert "depends_on" not in stages[0]

    def test_compile_flow_stages_skip_cycle_among_skipped_terminates(
        self,
        tmp_path: Path,
    ) -> None:
        """Cycle a↔b (both skipped) + c depends on a → [c] with c.depends_on == [].

        The ``_seen`` visited set terminates the cycle among skipped stages: no
        crash, c survives, and its dep on the cyclic a collapses to [].
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "a:\n"
            "  title: A\n"
            "  depends_on: [b]\n"
            "b:\n"
            "  title: B\n"
            "  depends_on: [a]\n"
            "c:\n"
            "  title: C\n"
            "  depends_on: [a]\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"a": WorkflowStage(skip=True), "b": WorkflowStage(skip=True)},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["c"]
        c = next(s for s in stages if s["id"] == "c")
        assert c["depends_on"] == []

    def test_compile_flow_stages_skip_drops_self_reference_from_cyclic_input(
        self,
        tmp_path: Path,
    ) -> None:
        """A skipped stage that 2-cycles with a survivor yields no self-dependency.

        s→x and x→s is already-cyclic input (afm rejects it regardless). Skipping
        x reconnects s's x-ref through x back to s itself — the reconnection must
        DROP that self-reference (a surviving stage never legitimately depends on
        itself) rather than write a ``depends_on: [s]`` self-loop.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "s:\n"
            "  title: S\n"
            "  depends_on: [x]\n"
            "x:\n"
            "  title: X\n"
            "  depends_on: [s]\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"x": WorkflowStage(skip=True)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["s"]
        s = next(st for st in stages if st["id"] == "s")
        # The self-reference (reconnecting s's x-ref through x back to s) is
        # dropped → explicit empty, not a self-loop.
        assert s["depends_on"] == []

    def test_compile_flow_stages_dangling_after_ref_after_skip_preserved(
        self,
        tmp_path: Path,
    ) -> None:
        """D ``depends_on: [b, ghost]``, skip B → [a, ghost] (dangling ghost preserved)."""
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
            "d:\n"
            "  title: D\n"
            "  depends_on: [b, ghost]\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=True)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "d"]
        d = next(s for s in stages if s["id"] == "d")
        # b-ref → a (reconnected); the non-skipped dangling ghost survives unchanged.
        assert d["depends_on"] == ["a", "ghost"]


class TestCompileFlowSkipRemovalPhases:
    """Step 4skip end-to-end — PHASES positional skip removal."""

    def test_compile_flow_phases_skip_collapses_positionally(self, tmp_path: Path) -> None:
        """PHASES [A, B, C, D], skip B → [a, c, d] with position-derived depends_on."""
        pipeline_path = _write_phases_four_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=True)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "c", "d"]
        # Position-derived: c (now second) depends on a; d on c.
        assert "depends_on" not in stages[0]
        assert stages[1]["depends_on"] == ["a"]
        assert stages[2]["depends_on"] == ["c"]

    def test_compile_flow_phases_skip_first_step(self, tmp_path: Path) -> None:
        """PHASES [A, B], skip A → [b] with no depends_on (first position)."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n- name: b\n  title: B\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"a": WorkflowStage(skip=True)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["b"]
        assert "depends_on" not in stages[0]

    def test_compile_flow_phases_skip_last_step(self, tmp_path: Path) -> None:
        """PHASES [A, B, C], skip C → [a, b] with b depending on a."""
        pipeline_path = _write_phases_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"c": WorkflowStage(skip=True)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b"]
        assert stages[1]["depends_on"] == ["a"]


class TestCompileFlowSkipSemantics:
    """Skip-vs-overrides priority, ORIGINAL-body isolation, empty-body guard, extend."""

    def test_compile_flow_skip_existing_stage_not_flagged_unknown(
        self,
        tmp_path: Path,
    ) -> None:
        """STAGES skip existing B → removed, NO StructuralError (valid at 4pre)."""
        pipeline_path = _write_stages_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=True)})

        # No raise: b exists, so 4pre accepts it; 4skip removes it.
        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "c"]

    def test_compile_flow_skip_wins_over_overrides(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """STAGES [A, B], skip B (with agent+prompt overrides) → [a], no WARNING.

        ``skip`` wins over ``agent``/``prompt``/``loop``/``skills`` overrides:
        B is removed at 4skip before the 4a override pass, so B's effective entry
        is a silent not-found (no WARNING) and the stage never appears.
        """
        pipeline_path = _write_stages_two_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"b": WorkflowStage(skip=True, agent="codex", prompt="x")},
        )

        with caplog.at_level(logging.WARNING, logger="goga.pipeline.compiler.compile_flow"):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a"]
        # The skipped stage's overrides never apply; the not-found is silent.
        assert not any(
            "not found" in record.getMessage() for record in caplog.records
        )

    def test_compile_flow_skip_does_not_leak_into_pipeline_document_body(
        self,
        tmp_path: Path,
    ) -> None:
        """STAGES [A, B], skip B → ORIGINAL body keeps [a, b]; flow-file ids [a]."""
        pipeline_path = _write_stages_two_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"b": WorkflowStage(skip=True)})

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        # ORIGINAL parsed body is untouched (deep-copied before reconstruction).
        assert [step.name for step in pipeline_doc.body.steps] == ["a", "b"]
        # FlowDocument carries only the surviving stage.
        assert [stage.id for stage in flow_doc.stages] == ["a"]

    def test_compile_flow_skip_extend_stage_via_stages_entry(self, tmp_path: Path) -> None:
        """STAGES [propose] + extend.warmup + stages.warmup.skip → warmup removed."""
        pipeline_path = _write_stages_single(tmp_path, "propose")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"warmup": WorkflowStage(skip=True)},
            extend={"warmup": WorkflowExtendStage(after=["propose"], body={"title": "Warmup"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        # warmup is valid at 4pre (embedded at 4a0) then removed at 4skip.
        assert _ids(stages) == ["propose"]

    def test_compile_flow_rejects_empty_body_after_skip_all(self, tmp_path: Path) -> None:
        """STAGES [A, B], skip BOTH → StructuralError("empty body") from the guard."""
        pipeline_path = _write_stages_two_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={
                "a": WorkflowStage(skip=True),
                "b": WorkflowStage(skip=True),
            },
        )

        with pytest.raises(StructuralError, match="empty body"):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

        assert not flow_path.exists()

    def test_compile_flow_phases_rejects_empty_body_after_skip_all(
        self,
        tmp_path: Path,
    ) -> None:
        """PHASES [A, B, C, D], skip ALL → StructuralError("empty body") from the guard.

        The post-4skip empty-body guard is format-agnostic: it must also fire on
        the PHASES branch (positional drop), not only the STAGES reconnect branch.
        """
        pipeline_path = _write_phases_four_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={
                "a": WorkflowStage(skip=True),
                "b": WorkflowStage(skip=True),
                "c": WorkflowStage(skip=True),
                "d": WorkflowStage(skip=True),
            },
        )

        with pytest.raises(StructuralError, match="empty body"):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

        assert not flow_path.exists()


class TestCompileFlowSkipLoopExpansionInteraction:
    """Skip removal runs BEFORE 4b loop-expansion — no stray copies of a skipped stage."""

    def test_skip_runs_before_loop_expansion(self, tmp_path: Path) -> None:
        """STAGES A→B→C, ``stages.b.loop: 2`` AND ``stages.c.skip: true`` → [a, b-1, b-2].

        c is removed at 4skip (before 4b), so no c copies appear; b is then
        loop-expanded in place. A skipped stage's own loop is moot (removed first).
        """
        pipeline_path = _write_stages_three_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={
                "b": WorkflowStage(loop=2),
                "c": WorkflowStage(skip=True),
            },
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b-1", "b-2"]
        # No stray c / c-N copies; b-1 inherits b's dep on a; b-2 chains to b-1.
        assert stages[1]["depends_on"] == ["a"]
        assert stages[2]["depends_on"] == ["b-1"]

    def test_skip_reconnects_through_skipped_to_loop_expanded_target(
        self,
        tmp_path: Path,
    ) -> None:
        """STAGES A→B→C→D, skip C + ``b.loop: 2`` → [a, b-1, b-2, d], d→[b-2].

        A SURVIVING stage (D) reconnects THROUGH a skipped stage (C) to a target
        (B) that is then loop-expanded: 4skip rewrites D's C-ref to B, then 4b
        expands B into b-1/b-2, then 4c rewrites the reconnected B-ref to the
        last expanded id b-2. Covers the cross-feature interaction the leaf-skip
        test above does not (C there is a leaf nothing depends on).
        """
        pipeline_path = _write_stages_four_step(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={
                "b": WorkflowStage(loop=2),
                "c": WorkflowStage(skip=True),
            },
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b-1", "b-2", "d"]
        assert stages[1]["depends_on"] == ["a"]
        assert stages[2]["depends_on"] == ["b-1"]
        d = next(s for s in stages if s["id"] == "d")
        # D's authored dep on C reconnects to B (4skip), then 4c rewrites it to
        # the last loop-expanded copy b-2.
        assert d["depends_on"] == ["b-2"]
