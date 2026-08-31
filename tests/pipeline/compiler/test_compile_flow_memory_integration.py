"""Cross-cell integration tests for the workflow-memory surface.

The cell-local memory tests (``test_parse_workflow_memory.py``,
``test_serialize_flow_memory_slot.py``, ``test_compile_flow_memory.py``,
``test_apply_skip_stages.py``) exercise the memory surface of each cell in
isolation. This module layers ON TOP of them the cross-cell scenarios the
design flags as needing separate verification once every coding task is done —
the full chain workflow parse → skip merge → compile → serialize → text:

- byte-identity — a memory-free workflow compiles to the byte-exact current
  output: a golden literal freezes the full flow-file text, so any memory leak
  into the output (a block, a stage key, a key-order shift) changes the string
  and fails the test;
- CLI skip channel — ``apply_skip_stages`` feeding ``compile_flow`` is
  equivalent to the workflow ``skip`` channel (design scenario 3): skipping the
  only participating stage disables the block, while skipping a bystander
  leaves everyone else's participation intact;
- ``PipelineDocument`` mirror — the memory block and the stage memory keys are
  output-side only; the mirror stays the faithful mirror of the source
  pipeline-file;
- method-selector absence — the goga-side ``method`` selector never reaches
  the output under either method.

No new production code is exercised here that the cell-local tests do not
already cover — this module pins that the three cells COMPOSE.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from goga.pipeline import apply_skip_stages
from goga.pipeline.compiler import FlowDocument, PipelineDocument, compile_flow
from goga.pipeline.workflow import WorkflowDocument, parse_workflow

# Base STAGES-format pipeline-file for the integration tests — three stages,
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

# The golden byte-exact output of the memory-free compile: the workflow carries
# only a top-level prompt, so the flow-file carries NO memory block and NO
# reflect / memory_use stage key — exactly the pre-memory output. Frozen from a
# single run of the memory-free compile (the main backward-compatibility
# invariant: a workflow without memory participation compiles byte-identically).
_GOLDEN_MEMORY_FREE = (
    "prompt: |-\n"
    "  P\n"
    "name: demo\n"
    "description: Demo pipeline\n"
    "stages:\n"
    "- id: brainstorm\n"
    "  name: Brainstorm\n"
    "  prompt: Think\n"
    "  agents: [auto]\n"
    "- id: build\n"
    "  name: Build\n"
    "  prompt: Make\n"
    "  agents: [auto]\n"
    "- id: review\n"
    "  name: Review\n"
    "  prompt: Check\n"
    "  agents: [auto]\n"
)

# A reflect-method workflow that participates (emission case 6 — a block with
# a reflect instruction): the block carries path / max_rules / commit only.
_REFLECT_WORKFLOW = (
    "memory:\n"
    "  max_rules: 40\n"
    "stages:\n"
    "  brainstorm:\n"
    "    reflect:\n"
    "      file: shared.md\n"
)

# An alignment-method workflow that participates (emission case 4): the block
# carries the composed path, the materialized mode, and memory_use: true.
_ALIGNMENT_WORKFLOW = (
    "memory:\n"
    "  method: alignment\n"
    "  path: goga-development\n"
    "stages:\n"
    "  brainstorm:\n"
    "    memory: true\n"
)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    """Write ``text`` to ``tmp_path / name`` and return the path.

    Args:
        tmp_path: The pytest temporary directory of the test.
        name: The file name to write under.
        text: The file content.

    Returns:
        The path of the written file.
    """
    path = tmp_path / name
    path.write_text(text)
    return path


def _compile(
    tmp_path: Path,
    pipeline_text: str,
    workflow_text: str | None = None,
) -> tuple[PipelineDocument, FlowDocument, str]:
    """Write the pipeline (and optional workflow), compile, return documents + text.

    Drives the real parser→compiler handoff: the workflow-file is parsed by
    ``parse_workflow`` and the resulting document handed to ``compile_flow``,
    so the assertions cover the composed surface, not a hand-built document.

    Args:
        tmp_path: The pytest temporary directory of the test.
        pipeline_text: The pipeline-file content to compile.
        workflow_text: The optional workflow-file content; ``None`` compiles
            without a workflow.

    Returns:
        The ``(PipelineDocument, FlowDocument, text)`` triple — the documents
        returned by ``compile_flow`` plus the compiled flow-file text.
    """
    workflow: WorkflowDocument | None = None

    if workflow_text is not None:
        workflow = parse_workflow(_write(tmp_path, "workflow.yml", workflow_text))

    pipeline_path = _write(tmp_path, "pipeline.yml", pipeline_text)
    flow_path = tmp_path / "flow.yml"

    pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

    return pipeline_doc, flow_doc, flow_path.read_text()


class TestMemoryFreeByteIdentity:
    """The byte-identity gate — a memory-free workflow compiles byte-identically."""

    def test_compile_flow_memory_free_workflow_compiles_byte_identically(self, tmp_path: Path) -> None:
        """A workflow with only a prompt compiles to the exact pre-memory output.

        The workflow-file carries nothing but ``prompt: "P"`` — no memory block,
        no participation instruction — so ``compile_flow`` must produce the same
        bytes as before the feature existed: the golden literal pins the full
        flow-file text (prompt block-literal first, then name, description, and
        the three stages with their ``agents: [auto]`` lines, and nothing else).
        Any memory leak into the output — a ``memory:`` block, a stage
        ``reflect`` / ``memory_use`` key, or a key-order shift — changes the
        string and fails the test.
        """
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, 'prompt: "P"\n')

        assert text == _GOLDEN_MEMORY_FREE
        assert flow_doc.memory is None
        assert not any("reflect" in stage.fields or "memory_use" in stage.fields for stage in flow_doc.stages)


class TestSkipChannelParity:
    """The CLI skip channel — ``apply_skip_stages`` feeding ``compile_flow``.

    The workflow ``skip`` channel is covered cell-locally
    (``test_compile_flow_memory.py``); these drive the CLI channel — the
    rebuilt ``WorkflowDocument`` from ``apply_skip_stages`` (which must carry
    the memory configuration verbatim) handed to ``compile_flow``.
    """

    @pytest.mark.parametrize(
        ("skip_stages", "expects_block"),
        [
            pytest.param(["brainstorm"], False, id="skip-participating-disables-block"),
            pytest.param(["review"], True, id="skip-bystander-keeps-block"),
        ],
    )
    def test_compile_flow_skip_via_cli_channel_uses_same_path(
        self,
        tmp_path: Path,
        skip_stages: list[str],
        expects_block: bool,
    ) -> None:
        """The CLI skip channel is equivalent to the workflow skip channel.

        The workflow carries a single participating stage (``brainstorm`` with
        a reflect instruction). Skipping it through the CLI channel
        (``apply_skip_stages`` → ``compile_flow``) removes the stage before the
        participation count, so the block is not emitted — design scenario 3.
        Skipping a non-participating bystander (``review``) leaves everyone
        else's participation intact: the block stays, ``brainstorm`` keeps its
        reflect key, and ``review`` disappears from the output.
        """
        workflow_text = "stages:\n  brainstorm:\n    reflect:\n      file: a.md\n"
        workflow = parse_workflow(_write(tmp_path, "workflow.yml", workflow_text))
        merged = apply_skip_stages(workflow, skip_stages)

        pipeline_path = _write(tmp_path, "pipeline.yml", _BASE_STAGES)
        flow_path = tmp_path / "flow.yml"

        _pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=merged)
        text = flow_path.read_text()

        if not expects_block:
            assert flow_doc.memory is None
            assert "memory:" not in text
            assert all("reflect" not in stage.fields for stage in flow_doc.stages)
            assert "brainstorm" not in {stage.id for stage in flow_doc.stages}
        else:
            assert flow_doc.memory is not None
            brainstorm = next(stage for stage in flow_doc.stages if stage.id == "brainstorm")

            assert brainstorm.fields["reflect"] == {"file": "a.md", "mode": "rw"}
            assert "review" not in {stage.id for stage in flow_doc.stages}


class TestPipelineDocumentMirror:
    """Output-side only — the ``PipelineDocument`` mirror ignores memory."""

    @pytest.mark.parametrize(
        "workflow_text",
        [
            pytest.param(_REFLECT_WORKFLOW, id="reflect"),
            pytest.param(_ALIGNMENT_WORKFLOW, id="alignment"),
        ],
    )
    def test_compile_flow_pipeline_document_unaffected_by_memory(
        self,
        tmp_path: Path,
        workflow_text: str,
    ) -> None:
        """The memory block and the stage keys never leak into ``PipelineDocument``.

        A participating memory workflow (both methods) compiles, and the
        returned ``PipelineDocument`` stays the faithful mirror of the source
        pipeline-file: no step body carries the output-side ``reflect`` /
        ``memory_use`` keys, and the body equals the body of the same pipeline
        compiled WITHOUT a workflow.
        """
        pipeline_doc, flow_doc, _text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert flow_doc.memory is not None

        for step in pipeline_doc.body.steps:
            assert "reflect" not in step.body
            assert "memory_use" not in step.body

        bare_path = _write(tmp_path, "bare-pipeline.yml", _BASE_STAGES)
        bare_doc, _bare_flow_doc = compile_flow(bare_path, tmp_path / "bare-flow.yml")

        assert pipeline_doc.body == bare_doc.body


class TestMethodSelectorAbsence:
    """The goga-side ``method`` selector never reaches the output."""

    @pytest.mark.parametrize(
        "workflow_text",
        [
            pytest.param(_REFLECT_WORKFLOW, id="reflect"),
            pytest.param(_ALIGNMENT_WORKFLOW, id="alignment"),
        ],
    )
    def test_compile_flow_method_selector_never_in_output(
        self,
        tmp_path: Path,
        workflow_text: str,
    ) -> None:
        """Neither method name nor the selector vocabulary appears in the text.

        Both participating scenarios (reflect and alignment) emit the memory
        block, yet the emitted surface carries only the afm vocabulary: no
        ``method:`` key, no ``alignment:`` selector value, and no ``reflect``
        or ``memory_use`` at the TOP level (``reflect`` legitimately appears
        nested inside stage bodies — the parsed top-level key set pins that).
        """
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, workflow_text)

        assert flow_doc.memory is not None
        assert "method:" not in text
        assert "alignment:" not in text

        top_level = yaml.safe_load(text)

        assert "reflect" not in top_level
        assert "memory_use" not in top_level
        assert set(top_level) <= {"name", "description", "memory", "stages"}
