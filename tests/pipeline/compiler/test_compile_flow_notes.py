"""Contract and logic tests for the ``compile_flow`` workflow notes instruction.

Covers the notes half of step 5 (``_canonical_fields``) plus the
reconstruction plumbing that feeds it: when the workflow stages block carries
notes for a stage (a map of note name → prompt text on ``WorkflowStage``),
the compiler assembles the stage's ``buttons`` field —

- in the canonical slot immediately after ``description`` (and before
  ``agents``), for BOTH body formats (STAGES and PHASES);
- verbatim — keys and values unchanged, one deep copy per ``FlowStage`` so
  the fields never alias ``WorkflowStage.notes``;
- uniformly across every loop-expanded copy (``NAME-1``..``NAME-N`` all carry
  the same buttons — resolution by BASE name);
- for embedded extend-stages by name (the stages block is the single
  authoring source for extend-stages too);
- never for a stage without a non-empty notes instruction (omitempty —
  ``{}`` is normalized to ``None`` upstream, so no ``buttons`` key appears
  and notes-free pipelines compile byte-identically);
- never for a skipped stage (skip removal runs before the notes resolution);
- never through a stage-body ``buttons`` key — an authoring buttons key in a
  pipeline-file stage OR an embedded extend body raises
  ``StructuralError("buttons key is forbidden in stage body; use notes in
  workflow.stages")``;
- output-side only — the ``PipelineDocument`` mirror and the workflow's own
  notes map stay untouched.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from goga.pipeline.compiler import StructuralError, compile_flow
from goga.pipeline.workflow import (
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowStage,
    parse_workflow,
)

_HEADER = "name: Feature\ndescription: Feature implementation\n---\n"


def _write(tmp_path: Path, body: str) -> Path:
    """Write a STAGES pipeline (or a PHASES list body) to a temp file and return its path."""
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(_HEADER + body)

    return pipeline_path


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


class TestNotesButtonsAssembly:
    """Step 5 — notes → buttons assembly across body sources and formats."""

    def test_notes_assemble_buttons_after_description(self, tmp_path: Path) -> None:
        """The assembled ``buttons`` occupies the canonical slot right after ``description``.

        The workflow ``prompt: override`` populates the stage's ``description``
        so the byte-level neighbor assertion has a ``description`` key to sit
        against; ``agents`` (the next canonical key after ``buttons``) is
        injected by default. The canonical slot is the contract's externally
        visible guarantee — this pins the exact neighbors.
        """
        flow_text = _compile(
            tmp_path,
            _HEADER + "s:\n  title: S\n  prompt: do work\n",
            "stages:\n"
            "  s:\n"
            "    prompt: override\n"
            "    notes:\n"
            "      fix: Fix it\n",
        )

        keys = list(yaml.safe_load(flow_text)["stages"][0])

        assert keys.index("description") + 1 == keys.index("buttons")
        assert keys.index("buttons") < keys.index("agents")
        assert "buttons:" in flow_text
        assert "  fix: Fix it" in flow_text

    def test_notes_assemble_buttons_phases_format(self, tmp_path: Path) -> None:
        """The PHASES list body assembles buttons identically — the directive is format-agnostic.

        Pins the PHASES call site of ``_canonical_fields`` with the ``notes=``
        argument: a regression dropping ``notes`` only in the PHASES branch
        silently loses buttons for phases pipelines while every STAGES test
        stays green.
        """
        flow_text = _compile(
            tmp_path,
            _HEADER + "- name: build\n  title: Build\n  prompt: do work\n",
            "stages:\n  build:\n    notes:\n      fix: Fix it\n",
        )

        stage = yaml.safe_load(flow_text)["stages"][0]

        assert stage["buttons"] == {"fix": "Fix it"}
        assert "fix: Fix it" in flow_text
        assert "depends_on" not in stage

    def test_loop_expanded_copies_carry_same_buttons(self, tmp_path: Path) -> None:
        """Every loop-expanded copy ``NAME-i`` carries the same buttons map.

        Resolution is by base name — a copy's final id (``build-i``) never
        appears in ``workflow.stages``, so a naive ``effective.get(step.name)``
        lookup would silently drop the buttons for every copy. The in-memory
        variant also pins the deep-copy discipline: the three maps are equal
        content but independent objects (one deep copy per ``FlowStage``).
        """
        flow_text = _compile(
            tmp_path,
            _HEADER + "build:\n  title: Build\n  prompt: do work\n",
            "stages:\n  build:\n    loop: 3\n    notes:\n      retry: Retry now\n",
        )

        stages = yaml.safe_load(flow_text)["stages"]

        assert [(stage["id"], stage.get("buttons")) for stage in stages] == [
            ("build-1", {"retry": "Retry now"}),
            ("build-2", {"retry": "Retry now"}),
            ("build-3", {"retry": "Retry now"}),
        ]

        _pipeline_doc, flow_doc = compile_flow(
            _write(tmp_path, "build:\n  title: Build\n  prompt: do work\n"),
            tmp_path / "flow2.yml",
            workflow=WorkflowDocument(
                stages={"build": WorkflowStage(loop=3, notes={"retry": "Retry now"})},
            ),
        )
        buttons = [stage.fields["buttons"] for stage in flow_doc.stages]

        assert buttons[0] == buttons[1] == buttons[2] == {"retry": "Retry now"}
        assert buttons[0] is not buttons[1]
        assert buttons[1] is not buttons[2]
        assert buttons[0] is not buttons[2]

    def test_notes_apply_to_extend_stage_by_name(self, tmp_path: Path) -> None:
        """An extend-stage receives its buttons through the stages block by name.

        The single authoring source: ``stages.<new-stage-name>.notes`` — there
        is no separate authoring inside an extend-entry (and ``notes`` there
        is a parse-time structural error).
        """
        flow_text = _compile(
            tmp_path,
            _HEADER + "a:\n  title: A\n  prompt: do a\n",
            "stages:\n"
            "  extra:\n"
            "    notes:\n"
            "      fix: Fix extra\n"
            "extend:\n"
            "  extra:\n"
            "    after: [a]\n"
            "    title: Extra\n"
            "    prompt: extra work\n",
        )

        stages = yaml.safe_load(flow_text)["stages"]
        extra = next(stage for stage in stages if stage["id"] == "extra")
        first = next(stage for stage in stages if stage["id"] == "a")

        assert extra["buttons"] == {"fix": "Fix extra"}
        assert "buttons" not in first


class TestEffectiveNotesResolution:
    """Step 4.5 — the effective override map carries the stages-block notes."""

    def test_effective_overrides_merged_branch_passes_notes(self) -> None:
        """The merged overlay branch passes ``notes=stg.notes`` explicitly.

        ``x`` is extend-seeded (inline defaults) AND overridden by a
        stages-block entry carrying notes — the merged branch must carry the
        notes. ``z`` is extend-only (no stages entry), so its notes can only
        be the constructor default ``None`` — pinning that an extend-only
        name keeps the seed untouched. Omitting the kwarg is the silent-drop
        regression the contract calls out.
        """
        from goga.pipeline.compiler.compile_flow import _effective_overrides

        workflow = WorkflowDocument(
            stages={"x": WorkflowStage(notes={"a": "1"})},
            extend={
                "x": WorkflowExtendStage(after=["y"], body={}),
                "z": WorkflowExtendStage(after=["x"], body={}),
            },
        )

        effective = _effective_overrides(workflow)

        assert effective["x"].notes == {"a": "1"}
        assert effective["z"].notes is None


class TestNotesProhibitions:
    """The single-authoring-source rule — authoring ``buttons`` keys are rejected."""

    def test_authoring_buttons_in_pipeline_body_rejected(self, tmp_path: Path) -> None:
        """An authoring ``buttons`` key in a pipeline-file stage body raises — no workflow needed.

        The prohibition is body-side: it fires with no workflow at all,
        proving buttons are authored ONLY via the workflow stages-block notes
        instruction.
        """
        with pytest.raises(StructuralError) as excinfo:
            _compile(tmp_path, _HEADER + "s:\n  title: S\n  buttons:\n    fix: x\n")

        assert str(excinfo.value) == "buttons key is forbidden in stage body; use notes in workflow.stages"

    def test_authoring_buttons_in_extend_body_rejected(self, tmp_path: Path) -> None:
        """An authoring ``buttons`` key in an embedded extend body raises the same error.

        Extend bodies flow through the same ``_canonical_fields`` pass, so the
        prohibition covers "pipeline-file stage OR embedded extend-stage".
        """
        with pytest.raises(StructuralError) as excinfo:
            _compile(
                tmp_path,
                _HEADER + "a:\n  title: A\n  prompt: do a\n",
                "extend:\n"
                "  extra:\n"
                "    after: [a]\n"
                "    title: Extra\n"
                "    prompt: extra work\n"
                "    buttons:\n"
                "      fix: x\n",
            )

        assert str(excinfo.value) == "buttons key is forbidden in stage body; use notes in workflow.stages"

    def test_notes_on_unknown_stage_name_raises_existing_error(self, tmp_path: Path) -> None:
        """A notes-bearing entry for an unknown name hits the existing strict name validation.

        A notes instruction must not weaken the pre-existing 4pre check — the
        error message is the same as for any other unknown stage name.
        """
        with pytest.raises(StructuralError) as excinfo:
            _compile(
                tmp_path,
                _HEADER + "a:\n  title: A\n  prompt: do a\n",
                "stages:\n  ghost:\n    notes:\n      fix: x\n",
            )

        assert str(excinfo.value) == "unknown stage name in workflow.stages: ghost"


class TestNotesEdges:
    """Omission edges — empty notes, skip precedence, no-mutation, byte-identity."""

    def test_empty_notes_compile_without_buttons_key(self, tmp_path: Path) -> None:
        """The empty-notes workflow (``notes: {}`` → ``None`` upstream) assembles no buttons.

        The omitempty presence rule: ``parse_workflow`` normalizes ``{}`` to
        ``None``, so the compiler never sees an empty-map instruction and the
        word ``buttons`` never appears anywhere in the output.
        """
        flow_text = _compile(
            tmp_path,
            _HEADER + "s:\n  title: S\n  prompt: do work\n",
            "stages:\n  s:\n    notes: {}\n",
        )

        assert "buttons" not in yaml.safe_load(flow_text)["stages"][0]
        assert "buttons" not in flow_text

    def test_notes_on_skipped_stage_not_applied(self, tmp_path: Path) -> None:
        """A skip+notes entry never leaks buttons into the survivors.

        Skip removal (4skip) runs BEFORE the effective-notes resolution and the
        assembly, so the skipped stage's notes are unreachable by design; the
        dependent stage ``t`` is reconnected past ``s``.
        """
        flow_text = _compile(
            tmp_path,
            _HEADER
            + "s:\n"
            + "  title: S\n"
            + "  prompt: do s\n"
            + "t:\n"
            + "  title: T\n"
            + "  prompt: do t\n"
            + "  depends_on: [s]\n",
            "stages:\n  s:\n    skip: true\n    notes:\n      fix: x\n",
        )

        stages = yaml.safe_load(flow_text)["stages"]

        assert [stage["id"] for stage in stages] == ["t"]
        assert "buttons" not in flow_text

    def test_workflow_notes_do_not_mutate_pipeline_document(self, tmp_path: Path) -> None:
        """Output-side only — neither the pipeline mirror nor the workflow's map is touched.

        The notes instruction travels as a function argument into
        ``FlowStage.fields`` (a deep copy): the ``PipelineDocument`` body never
        carries a ``buttons``/``notes`` key, the workflow's own dict keeps its
        content and identity, and the assembled map never aliases it.
        """
        workflow = WorkflowDocument(stages={"s": WorkflowStage(notes={"fix": "F"})})
        notes_object = workflow.stages["s"].notes

        pipeline_doc, flow_doc = compile_flow(
            _write(tmp_path, "s:\n  title: S\n  prompt: do work\n"),
            tmp_path / "flow.yml",
            workflow=workflow,
        )

        for step in pipeline_doc.body.steps:
            assert "buttons" not in step.body
            assert "notes" not in step.body

        assert workflow.stages["s"].notes == {"fix": "F"}
        assert workflow.stages["s"].notes is notes_object
        assert flow_doc.stages[0].fields["buttons"] == {"fix": "F"}
        assert flow_doc.stages[0].fields["buttons"] is not workflow.stages["s"].notes

    def test_pipeline_without_notes_compiles_byte_identical(self, tmp_path: Path) -> None:
        """A directive-rich pipeline compiles byte-identically with a notes-free NO-OP workflow.

        The regression gate for the canonical-order extension: an empty-entry
        workflow (``stages: {build: {}}`` — a real stage name, all fields
        defaulted, a no-op override) changes nothing, so the workflow-less and
        NO-OP-workflow flow-files are equal byte-for-byte and neither carries
        a ``buttons`` key.
        """
        pipeline_text = (
            _HEADER
            + "build:\n"
            + "  title: Build\n"
            + "  communication: true\n"
            + "  before_script: echo prep\n"
            + "  script: make all\n"
            + "  after_script: echo done\n"
            + "  timeout: 30m\n"
            + "check:\n"
            + "  title: Check\n"
            + "  prompt: verify\n"
            + "  roles: [planner, reviewer]\n"
            + "  skills: [goga-review]\n"
            + "  trigger: manual\n"
        )

        text_a = _compile(tmp_path, pipeline_text)
        text_b = _compile(tmp_path, pipeline_text, "stages:\n  build: {}\n")

        assert text_a == text_b
        assert "buttons" not in text_a
