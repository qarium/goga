"""Cross-entity integration tests for the ``compile_flow`` workflow reconstruction.

The cell-local logic tests in ``test_compile_flow_workflow.py`` exercise the
reconstruction facets (effective overrides, skills-merge, loop-expansion,
extend embedding) in isolation against small in-memory ``WorkflowDocument``
instances. This module layers ON TOP of them the cross-entity scenarios the
design document flags as needing separate verification once every coding task is
done:

- skills-merge x loop-expansion — every expanded copy carries the merged skills
  independently (the deep-copy on the loop-expansion step keeps the copies from
  aliasing), for BOTH body formats (STAGES and PHASES — the design scenarios are
  written mostly for STAGES).
- PHASES parity — inline-extend loop-expansion and skills-merge applied to a
  PHASES-format pipeline-file (the STAGES analogs already exist).
- end-to-end parse→compile — an authored workflow-file is parsed by
  ``parse_workflow`` and the resulting ``WorkflowDocument`` is handed to
  ``compile_flow``; the full round-trip is asserted (skills in stages, inline
  agent→command, loop-expansion, single-``["auto"]`` default, no leak).
- non-leak regression (Trace 6) — inline ``agent``/``loop`` carried by an extend
  entry never survive into the compiled flow-file as stage-level keys; they
  surface only as the composed ``command`` and the expanded ids.

These scenarios exercise the workflow + compiler cells together (and the
parser→compiler handoff for the end-to-end case) rather than any single helper.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from goga.pipeline.compiler import PipelineDocument, compile_flow
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowStage,
    parse_workflow,
)


def _stage_by_id(stages: list[dict[str, object]], stage_id: str) -> dict[str, object]:
    """Return the single deserialized flow stage whose ``id`` equals ``stage_id``.

    Args:
        stages: The deserialized ``stages`` list from a compiled flow-file.
        stage_id: The stage id to match.

    Returns:
        The matching stage dict.

    Raises:
        AssertionError: If no stage or more than one stage matches (an ambiguous
            match would silently mask a miscompile).
    """
    matches = [stage for stage in stages if stage["id"] == stage_id]
    assert len(matches) == 1, f"expected exactly one stage {stage_id!r}, got {len(matches)}"
    return matches[0]


class TestSkillsMergeWithLoopExpansion:
    """skills-merge combined with loop-expansion — every copy carries merged skills.

    The deep-copy performed on each loop-expanded copy (step 4b) keeps the
    copies independent, so the skills-merge applied at step 4a (before the
    expansion) must reach EVERY copy with the same value. Verified for BOTH
    body formats so PHASES/STAGES parity holds.
    """

    def test_skills_merge_with_loop_expansion_stages(self, tmp_path: Path) -> None:
        """STAGES review with pipeline ``skills:[a]`` + workflow ``skills:[b], loop:2``.

        Both expanded copies ``review-1`` and ``review-2`` carry the merged
        ``["a", "b"]`` skills — the merge is applied before expansion and each
        copy is deep-copied so the value is shared, not aliased-and-lost.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\nreview:\n  title: Review\n  skills: [a]\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"review": WorkflowStage(skills=["b"], loop=2)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        review_1 = _stage_by_id(stages, "review-1")
        review_2 = _stage_by_id(stages, "review-2")
        # Pipeline skills keep their position; the workflow skill appends (dedup).
        assert review_1["skills"] == ["a", "b"]
        assert review_2["skills"] == ["a", "b"]

    def test_skills_merge_with_loop_expansion_phases(self, tmp_path: Path) -> None:
        """PHASES review with pipeline ``skills:[a]`` + workflow ``skills:[b], loop:2``.

        The PHASES-format counterpart of the STAGES case above: every expanded
        copy carries the same merged skills. Pins PHASES/STAGES parity for the
        skills x loop interaction.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: review\n  title: Review\n  skills: [a]\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(stages={"review": WorkflowStage(skills=["b"], loop=2)})

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        review_1 = _stage_by_id(stages, "review-1")
        review_2 = _stage_by_id(stages, "review-2")
        assert review_1["skills"] == ["a", "b"]
        assert review_2["skills"] == ["a", "b"]


class TestPhasesParity:
    """PHASES-format parity for scenarios whose STAGES analogs already exist.

    The cell-local STAGES scenarios (``test_compile_flow_skills_merge_dedup``,
    ``test_compile_flow_effective_inline_extend_loop_expansion``) cover skills-merge
    dedup and inline-extend loop-expansion on a STAGES body; these mirror them on
    a PHASES body to confirm the format-agnostic reconstruction applies both
    uniformly.
    """

    def test_skills_merge_dedup_phases_parity(self, tmp_path: Path) -> None:
        """PHASES skills-merge dedups pipeline-first, dropping the workflow duplicate.

        pipeline ``propose.skills:[goga-propose]`` + workflow
        ``stages.propose.skills:[web-search, goga-propose]`` →
        ``["goga-propose", "web-search"]`` (pipeline position preserved, the
        duplicate workflow ``goga-propose`` dropped). The PHASES analog of the
        STAGES ``test_compile_flow_skills_merge_dedup``.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: propose\n  title: Propose\n  skills:\n    - goga-propose\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"propose": WorkflowStage(skills=["web-search", "goga-propose"])},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert stages[0]["skills"] == ["goga-propose", "web-search"]

    def test_inline_extend_loop_expansion_phases_parity(self, tmp_path: Path) -> None:
        """PHASES inline-extend ``loop`` expands in place, chaining the copies.

        PHASES [a, b, c] with ``extend={warmup: after=[b], loop=3}``: warmup is
        inserted after b, then expanded to ``warmup-1..3``; the list-position
        chain makes the successor c depend on the LAST copy ``warmup-3``. The
        PHASES analog of the STAGES inline-extend loop-expansion scenario.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n- name: b\n  title: B\n- name: c\n  title: C\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={"warmup": WorkflowExtendStage(after=["b"], loop=3, body={"title": "Warmup"})},
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert [stage["id"] for stage in stages] == [
            "a",
            "b",
            "warmup-1",
            "warmup-2",
            "warmup-3",
            "c",
        ]
        # Position-derived chain: copies chain to each other; c chains to the LAST.
        assert _stage_by_id(stages, "warmup-1")["depends_on"] == ["b"]
        assert _stage_by_id(stages, "warmup-2")["depends_on"] == ["warmup-1"]
        assert _stage_by_id(stages, "warmup-3")["depends_on"] == ["warmup-2"]
        assert _stage_by_id(stages, "c")["depends_on"] == ["warmup-3"]


class TestEndToEndParseCompile:
    """Full round-trip: an authored workflow-file parsed then compiled.

    Unlike the cell-local tests (which build a ``WorkflowDocument`` in memory),
    this drives the real parser→compiler handoff on authored YAML so the whole
    contract surface is exercised together: skills in stages, inline
    agent→command, inline loop→expansion, the single ``["auto"]`` default, and
    the inline agent/loop non-leak.
    """

    def test_end_to_end_parse_compile_round_trip(self, tmp_path: Path) -> None:
        """``parse_workflow`` → ``compile_flow`` produces the full expected flow-file.

        The workflow carries a top-level prompt, a ``stages.propose`` override
        (agent→command, prompt→description, skills merge) and an ``extend.warmup``
        entry with inline agent (→command) and loop (→expansion). The pipeline
        carries no ``agents`` (so the single ``["auto"]`` default is injected) and
        ``propose.skills:[goga-propose]`` (merged with the workflow's
        ``[web-search]``). Asserts the complete round-trip and the inline
        agent/loop non-leak across both cells.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: propose\n  title: Propose\n  skills:\n    - goga-propose\n",
        )
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "prompt: |\n"
            "  Drive the pipeline end to end\n"
            "\n"
            "stages:\n"
            "  propose:\n"
            "    agent: codex\n"
            "    prompt: |\n"
            "      Propose more\n"
            "    skills:\n"
            "      - web-search\n"
            "\n"
            "extend:\n"
            "  warmup:\n"
            "    before: [propose]\n"
            "    agent: claude\n"
            "    loop: 2\n"
            "    title: Warmup\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        # Top-level workflow prompt carried through and emitted first.
        assert flow_doc.prompt is not None
        assert "Drive the pipeline end to end" in flow_doc.prompt
        text = flow_path.read_text()
        assert text.startswith("prompt: |")

        # warmup (inline loop=2, before propose) expands and precedes propose.
        ids = [stage.id for stage in flow_doc.stages]
        assert ids == ["warmup-1", "warmup-2", "propose"]

        warmup_1 = next(stage for stage in flow_doc.stages if stage.id == "warmup-1")
        warmup_2 = next(stage for stage in flow_doc.stages if stage.id == "warmup-2")
        propose = next(stage for stage in flow_doc.stages if stage.id == "propose")

        # Inline extend agent → composed command (on every expanded copy).
        assert warmup_1.fields["command"] == "/home/goga/bin/claude-as-claude.sh"
        assert warmup_2.fields["command"] == "/home/goga/bin/claude-as-claude.sh"
        # Stages-block agent → command; prompt → description; skills merged.
        assert propose.fields["command"] == "/home/goga/bin/codex-as-claude.sh"
        assert propose.fields["description"] == "Propose more\n"
        assert propose.fields["skills"] == ["goga-propose", "web-search"]

        # Single ``["auto"]`` default — the pipeline carried no usable agents.
        assert propose.fields["agents"] == ["auto"]
        assert warmup_1.fields["agents"] == ["auto"]
        assert warmup_2.fields["agents"] == ["auto"]
        assert "agents: [auto]" in text

        # Non-leak (Trace 6): inline agent/loop never surface as stage fields.
        for stage in flow_doc.stages:
            assert "agent" not in stage.fields
            assert "loop" not in stage.fields

        # The ORIGINAL parsed body is untouched by the reconstruction.
        assert [step.name for step in pipeline_doc.body.steps] == ["propose"]


def _write_stages_chain_four_step(tmp_path: Path) -> Path:
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


def _write_phases_chain_four_step(tmp_path: Path) -> Path:
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


class TestSkipStageRoundTrip:
    """Cross-cell ``skip: true`` integration — the parse → compile → flow-file round-trip.

    Unlike the cell-local skip tests (``test_compile_flow_workflow.py`` build an
    in-memory ``WorkflowDocument``), these drive the real consumer path: an
    authored workflow-file carrying ``skip: true`` is parsed by the workflow
    cell's ``parse_workflow`` (exercising the 5-key per-stage set, the bool
    type-check, and the extend-skip prohibition across the cell boundary) and the
    resulting ``WorkflowDocument`` is handed to the compiler cell's
    ``compile_flow`` (exercising ``4pre`` strict validation, ``4skip`` removal +
    transparent reconnection, the empty-body guard, and the silent ``4a``
    not-found). The compiled flow-file YAML is then asserted via ``yaml.safe_load``.
    """

    def test_stages_round_trip_skip_reconnects_chain(self, tmp_path: Path) -> None:
        """STAGES A→B→C→D + authored ``stages.b.skip: true`` → [a, c, d] reconnected.

        ``parse_workflow`` accepts the ``skip`` key (5-key per-stage set) and
        type-checks it as a bool; ``compile_flow`` removes B at ``4skip`` and
        transparently reconnects C's authored dep on B to B's predecessor A, while
        D's dep on C is unaffected. The flow-file YAML (parsed back) carries the
        expected ids and reconnected ``depends_on``.
        """
        pipeline_path = _write_stages_chain_four_step(tmp_path)
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "stages:\n  b:\n    skip: true\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert [stage["id"] for stage in stages] == ["a", "c", "d"]
        # C's authored dep on B is reconnected to B's predecessor A; D's dep on C stays.
        assert _stage_by_id(stages, "c")["depends_on"] == ["a"]
        assert _stage_by_id(stages, "d")["depends_on"] == ["c"]

    def test_phases_round_trip_skip_collapses_positionally(self, tmp_path: Path) -> None:
        """PHASES [A, B, C, D] + authored ``stages.b.skip: true`` → [a, c, d] by position.

        PHASES has no explicit reconnection — the skipped B drops and downstream
        ``depends_on`` re-derives by list position: C (now second) depends on A;
        D on C.
        """
        pipeline_path = _write_phases_chain_four_step(tmp_path)
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "stages:\n  b:\n    skip: true\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert [stage["id"] for stage in stages] == ["a", "c", "d"]
        # Position-derived: a is first (no dep), c depends on a, d depends on c.
        assert "depends_on" not in _stage_by_id(stages, "a")
        assert _stage_by_id(stages, "c")["depends_on"] == ["a"]
        assert _stage_by_id(stages, "d")["depends_on"] == ["c"]

    def test_skip_plus_extend_stage_removed_via_stages_entry(self, tmp_path: Path) -> None:
        """``extend.warmup`` + authored ``stages.warmup.skip: true`` → warmup removed.

        The extend-embedded ``warmup`` is valid at ``4pre`` (it is in the steps
        after ``4a0`` embedding) and then removed at ``4skip`` via the matching
        ``stages`` entry. The flow-file carries only the original propose stage.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\npropose:\n  title: Propose\n")
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "stages:\n  warmup:\n    skip: true\nextend:\n  warmup:\n    after: [propose]\n    title: Warmup\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert [stage["id"] for stage in stages] == ["propose"]

    def test_skip_runs_before_loop_expansion_authored(self, tmp_path: Path) -> None:
        """STAGES A→B→C, authored ``b.loop: 2`` AND ``c.skip: true`` → [a, b-1, b-2].

        Skip removal runs BEFORE ``4b`` loop-expansion: C is removed first (so no
        stray ``c``/``c-N`` copies appear), then B is expanded in place. A skipped
        stage's own expansion is moot (it is removed first).
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
            "  depends_on: [b]\n",
        )
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "stages:\n  b:\n    loop: 2\n  c:\n    skip: true\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        compile_flow(pipeline_path, flow_path, workflow=workflow)

        stages = yaml.safe_load(flow_path.read_text())["stages"]
        assert [stage["id"] for stage in stages] == ["a", "b-1", "b-2"]
        # No stray c / c-N copies; b-1 inherits b's dep on a; b-2 chains to b-1.
        assert _stage_by_id(stages, "b-1")["depends_on"] == ["a"]
        assert _stage_by_id(stages, "b-2")["depends_on"] == ["b-1"]

    def test_skip_preserves_original_pipeline_body_across_cells(self, tmp_path: Path) -> None:
        """After a skip compile, ``PipelineDocument.body`` still lists every authored stage.

        The deep-copy in ``_reconstruct_body`` isolates the ORIGINAL parsed body:
        the skipped stage and any embedded extend-stage never leak into it. This
        pins the cross-cell invariant — the workflow cell's parsed instructions
        are consumed but the compiler never mutates the parsed pipeline body.
        """
        pipeline_path = _write_stages_chain_four_step(tmp_path)
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "stages:\n"
            "  b:\n"
            "    skip: true\n"
            "  warmup:\n"
            "    skip: true\n"
            "extend:\n"
            "  warmup:\n"
            "    after: [d]\n"
            "    title: Warmup\n",
        )
        flow_path = tmp_path / "flow.yml"

        workflow = parse_workflow(workflow_path)
        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        assert isinstance(pipeline_doc, PipelineDocument)
        # ORIGINAL parsed body keeps the four authored stages — neither the
        # skipped B nor the embedded (then skipped) extend-stage warmup leaks in.
        assert [step.name for step in pipeline_doc.body.steps] == ["a", "b", "c", "d"]
        # The flow-file carries the surviving stages: b and warmup both removed.
        assert [stage.id for stage in flow_doc.stages] == ["a", "c", "d"]


class TestNonLeakRegression:
    """Trace 6 regression — inline extend ``agent``/``loop`` never leak to the flow-file.

    An extend entry carrying inline ``agent`` and ``loop`` must surface in the
    compiled flow-file ONLY as the composed ``command`` (agent) and the expanded
    ids (loop). They must never survive as stage-level ``agent:`` / ``loop:`` keys
    — that would be a parse→compile leak of the override-declaration vocabulary
    into the afm flow-file vocabulary.
    """

    def test_inline_extend_agent_loop_do_not_leak_as_stage_keys(self, tmp_path: Path) -> None:
        """Inline ``agent``/``loop`` on an extend entry compose ``command`` and ids only.

        A STAGES pipeline ``propose`` with ``extend={warmup: before=[propose],
        agent: codex, loop: 3}``: the compiled flow-file carries the composed
        ``command`` on every ``warmup-N`` copy and the expanded ids, but NO
        ``agent:`` or ``loop:`` field on ANY stage (parsed and text level).
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\npropose:\n  title: Propose\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            extend={
                "warmup": WorkflowExtendStage(
                    before=["propose"],
                    agent="codex",
                    loop=3,
                    body={"title": "Warmup"},
                ),
            },
        )

        compile_flow(pipeline_path, flow_path, workflow=workflow)

        text = flow_path.read_text()
        stages = yaml.safe_load(text)["stages"]
        # The override applied: composed command + expanded ids present.
        assert {stage["id"] for stage in stages} == {
            "warmup-1",
            "warmup-2",
            "warmup-3",
            "propose",
        }
        for wid in ("warmup-1", "warmup-2", "warmup-3"):
            assert _stage_by_id(stages, wid)["command"] == "/home/goga/bin/codex-as-claude.sh"

        # Non-leak: no stage carries an ``agent`` or ``loop`` field key.
        for stage in stages:
            assert "agent" not in stage
            assert "loop" not in stage

        # Text-level guard: a 2-space-indented ``agent:`` / ``loop:`` stage field
        # never appears (``agents:`` is a different key and must not match).
        assert "\n  agent:" not in text
        assert "\n  loop:" not in text
