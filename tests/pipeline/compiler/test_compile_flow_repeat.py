"""Contract and logic tests for the ``compile_flow`` repeat compilation (steps 4.0 and 6).

Covers the repeat half of the compiler: the pipeline header declares the
``repeatable`` capability and this cell owns the single compilation rule —
a repeatable pipeline ALWAYS produces a repeat key. A workflow repeat block
compiles the authored keys only (this cell materializes no defaults); a
missing block, an absent workflow document, or a workflow-free compilation
compiles the scalar form. A workflow repeat block on a non-repeatable
pipeline is a structural error naming the conflict — the cross-reference
check lives here because only this cell sees both documents, and it fires
BEFORE any reconstruction error. The compiled repeat is emitted immediately
after description, before memory; a non-repeatable pipeline compiles
byte-identically (no repeat key anywhere).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from goga.pipeline.compiler import FlowDocument, FlowRepeat, PipelineDocument, StructuralError, compile_flow
from goga.pipeline.workflow import parse_workflow

# Base STAGES-format pipeline-file for the compiler tests — three stages.
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

# The repeatable twin of the base pipeline — one added header flag.
_REPEATABLE_STAGES = (
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
)


def _compile(
    tmp_path: Path,
    pipeline_text: str,
    workflow_text: str | None = None,
) -> tuple[PipelineDocument, FlowDocument, str]:
    """Write the pipeline (and optional workflow), compile, return documents + text."""
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(pipeline_text)
    flow_path = tmp_path / "flow.yml"

    workflow = None

    if workflow_text is not None:
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(workflow_text)
        workflow = parse_workflow(workflow_path.read_text())

    pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

    return pipeline_doc, flow_doc, flow_path.read_text()


class TestCompileFlowRepeatContract:
    """Contract tests — the repeat surface declared by the compiler CODEMANIFEST."""

    def test_compile_flow_repeatable_pipeline_yields_repeat_directive(self, tmp_path: Path) -> None:
        """Compiling a repeatable pipeline yields a non-None ``doc.repeat``."""
        _pipeline_doc, flow_doc, _text = _compile(tmp_path, _REPEATABLE_STAGES)

        assert flow_doc.repeat is not None

    def test_repeat_helpers_not_on_facade(self) -> None:
        """``_check_repeat_correspondence`` & ``_repeat_emission`` are module-internal names."""
        from goga.pipeline.compiler import __all__ as facade_all

        assert "_check_repeat_correspondence" not in facade_all
        assert "_repeat_emission" not in facade_all

    def test_repeat_helpers_exist_in_module(self) -> None:
        """The step-4.0 / step-6 helpers exist with the contract shape."""
        from goga.pipeline.compiler.compile_flow import _check_repeat_correspondence, _repeat_emission

        assert callable(_check_repeat_correspondence)
        assert callable(_repeat_emission)

    def test_pipeline_document_mirror_carries_repeatable_flag(self, tmp_path: Path) -> None:
        """The parsed header (with ``repeatable``) rides the PipelineDocument mirror 1:1."""
        pipeline_doc, _flow_doc, _text = _compile(tmp_path, _REPEATABLE_STAGES)

        assert pipeline_doc.header.repeatable is True


class TestCompileFlowRepeatEmission:
    """Step 6 — the always-emit rule and the authored-keys-only carry."""

    def test_compile_flow_repeatable_with_block_emits_authored_keys(self, tmp_path: Path) -> None:
        """A repeatable pipeline + a workflow block compiles the authored keys in order."""
        workflow_text = (
            "repeat:\n"
            "  max_cycles: 3\n"
            "  keep_runs: 5\n"
            "memory:\n"
            "  path: p\n"
            "stages:\n"
            "  brainstorm:\n"
            "    reflect:\n"
            "      file: a.md\n"
        )
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _REPEATABLE_STAGES, workflow_text)

        assert flow_doc.repeat is not None
        assert flow_doc.repeat.max_cycles == 3
        assert flow_doc.repeat.keep_runs == 5
        assert "repeat:\n  max_cycles: 3\n  keep_runs: 5\n" in text
        assert text.index("description:") < text.index("repeat:") < text.index("memory:")

    def test_compile_flow_repeatable_block_single_key_compiles_only_that_key(self, tmp_path: Path) -> None:
        """A block authoring one key compiles exactly that key (no default materialization)."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            _REPEATABLE_STAGES,
            "repeat:\n  max_cycles: 4\n",
        )

        assert flow_doc.repeat is not None
        assert flow_doc.repeat.max_cycles == 4
        assert flow_doc.repeat.keep_runs is None
        assert "repeat:\n  max_cycles: 4\n" in text
        assert "keep_runs" not in text

    def test_compile_flow_repeatable_block_zero_is_a_value(self, tmp_path: Path) -> None:
        """An authored ``max_cycles: 0`` compiles as 0 — never normalized away."""
        _pipeline_doc, flow_doc, text = _compile(
            tmp_path,
            _REPEATABLE_STAGES,
            "repeat:\n  max_cycles: 0\n",
        )

        assert flow_doc.repeat is not None
        assert flow_doc.repeat.max_cycles == 0
        assert flow_doc.repeat.max_cycles is not None
        assert "repeat:\n  max_cycles: 0\n" in text

    def test_compile_flow_repeatable_without_block_emits_scalar(self, tmp_path: Path) -> None:
        """A repeatable pipeline with a workflow carrying NO block compiles the scalar form."""
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _REPEATABLE_STAGES, "stages:\n  build:\n    skip: true\n")

        assert flow_doc.repeat is not None
        assert flow_doc.repeat.max_cycles is None
        assert flow_doc.repeat.keep_runs is None
        assert "\nrepeat: true\n" in text

    def test_compile_flow_repeatable_workflow_none_emits_scalar(self, tmp_path: Path) -> None:
        """A repeatable workflow-free compilation (``workflow=None``) compiles the scalar form."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_REPEATABLE_STAGES)
        flow_path = tmp_path / "flow.yml"

        _pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, workflow=None)

        assert flow_doc.repeat is not None
        assert flow_doc.repeat.max_cycles is None
        assert flow_doc.repeat.keep_runs is None
        assert "\nrepeat: true\n" in flow_path.read_text()

    def test_compile_flow_non_repeatable_output_byte_identical(self, tmp_path: Path) -> None:
        """A non-repeatable pipeline without a workflow block carries no repeat key anywhere."""
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES, "stages:\n  build:\n    skip: true\n")

        assert flow_doc.repeat is None
        assert "repeat" not in text

    def test_compile_flow_non_repeatable_workflow_none_byte_identical(self, tmp_path: Path) -> None:
        """A non-repeatable workflow-free compilation carries no repeat key anywhere."""
        _pipeline_doc, flow_doc, text = _compile(tmp_path, _BASE_STAGES)

        assert flow_doc.repeat is None
        assert "repeat" not in text

    def test_compiled_repeat_directive_is_flow_repeat_instance(self, tmp_path: Path) -> None:
        """The compiled directive is a ``FlowRepeat`` built from the authored keys."""
        _pipeline_doc, flow_doc, _text = _compile(tmp_path, _REPEATABLE_STAGES, "repeat:\n  keep_runs: 2\n")

        assert isinstance(flow_doc.repeat, FlowRepeat)
        assert flow_doc.repeat.max_cycles is None
        assert flow_doc.repeat.keep_runs == 2


class TestCompileFlowRepeatCrossCheck:
    """Step 4.0 — the workflow-block/header-flag correspondence check."""

    def test_compile_flow_cross_check_error(self, tmp_path: Path) -> None:
        """A non-repeatable pipeline + a workflow repeat block raises one clean error."""
        with pytest.raises(
            StructuralError,
            match=re.escape(
                "workflow repeat block requires a repeatable pipeline; author repeatable: true in the pipeline header"
            ),
        ):
            _compile(tmp_path, _BASE_STAGES, "repeat:\n  max_cycles: 2\n")

    def test_compile_flow_cross_check_fires_before_reconstruction_errors(self, tmp_path: Path) -> None:
        """The cross-check precedes every reconstruction error (unknown stage name included)."""
        with pytest.raises(
            StructuralError,
            match=re.escape(
                "workflow repeat block requires a repeatable pipeline; author repeatable: true in the pipeline header"
            ),
        ):
            _compile(tmp_path, _BASE_STAGES, "repeat:\n  max_cycles: 2\nstages:\n  nope:\n    skip: true\n")

    def test_compile_flow_cross_check_silent_when_repeatable(self, tmp_path: Path) -> None:
        """A repeatable header + a workflow block passes the cross-check and compiles."""
        _pipeline_doc, flow_doc, _text = _compile(tmp_path, _REPEATABLE_STAGES, "repeat:\n  max_cycles: 2\n")

        assert flow_doc.repeat is not None
        assert flow_doc.repeat.max_cycles == 2

    def test_compile_flow_cross_check_silent_without_block(self, tmp_path: Path) -> None:
        """A non-repeatable header with a block-free workflow raises nothing at 4.0."""
        _pipeline_doc, flow_doc, _text = _compile(tmp_path, _BASE_STAGES, "prompt: x\n")

        assert flow_doc.repeat is None
