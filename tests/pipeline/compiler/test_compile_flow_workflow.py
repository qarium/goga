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

    def test_compile_flow_stages_extend_after_dangling_kept_verbatim(self, tmp_path: Path) -> None:
        """STAGES extend ``after`` with a dangling ref keeps it verbatim (no WARNING).

        Symmetric with step 4c: a dangling after-ref lands in depends_on and is
        left for afm to surface — not dropped or warned about.
        """
        pipeline_path = _write_stages_propose_review(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"x": WorkflowExtendStage(after=["ghost"], body={"title": "X"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        x = next(s for s in stages if s["id"] == "x")
        assert x["depends_on"] == ["ghost"]

    def test_compile_flow_stages_extend_before_dangling_warns(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """STAGES extend ``before`` with a dangling ref warns and skips that ref.

        propose→review with ``extend={x: before=[ghost]}`` (ghost unknown): the
        before-ref names no step, so it is skipped with a WARNING. This pins the
        documented asymmetry with the after-direction — a dangling ``after`` is
        kept verbatim with NO warning (tested above), while a dangling ``before``
        warns. x is still emitted with no depends_on (no after, before skipped).
        """
        pipeline_path = _write_stages_propose_review(tmp_path)
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"x": WorkflowExtendStage(before=["ghost"], body={"title": "X"})},
        )

        with caplog.at_level(logging.WARNING, logger="goga.pipeline.compiler.compile_flow"):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        x = next(s for s in stages if s["id"] == "x")
        assert "depends_on" not in x
        assert any("not found" in record.getMessage() for record in caplog.records)

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

    def test_compile_flow_phases_extend_all_dangling_appends_end(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """PHASES extend with ALL targets dangling appends at the end with a WARNING.

        [a, b] with ``extend={x: after=[ghost]}`` (ghost unknown): x has no
        resolvable position → appended at end → [a, b, x]; x depends on b by
        position; a WARNING is logged.
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

        with caplog.at_level(logging.WARNING, logger="goga.pipeline.compiler.compile_flow"):
            compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert _ids(stages) == ["a", "b", "x"]
        x = next(s for s in stages if s["id"] == "x")
        assert x["depends_on"] == ["b"]
        assert any("no resolvable position" in r.getMessage() for r in caplog.records)

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

