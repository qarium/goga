"""Logic tests for the ``FlowDocument.prompt`` slot + ``serialize_flow`` emission.

Covers the Task 5 serializer extension: a non-``None`` top-level ``prompt`` is
emitted as the FIRST top-level key in block-literal scalar style (before
``name``); a ``None`` prompt omits the key entirely. The end-to-end compile
path (no workflow applied) must produce no top-level ``prompt:`` key.

Note: the ``workflow`` parameter of ``compile_flow`` is added in Task 6. In
Task 5 the "no workflow applied" path is exercised by calling ``compile_flow``
without it (the default, no top-level prompt).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from goga.pipeline.compiler import FlowDocument, FlowStage, compile_flow, serialize_flow


class TestSerializeFlowPromptSlot:
    """Behavioral tests for the top-level prompt emission rules."""

    def test_serialize_flow_emits_prompt_first_when_set(self) -> None:
        """A non-None prompt is emitted as the FIRST top-level key, before ``name``."""
        doc = FlowDocument(
            prompt="Top-level workflow prompt",
            name="My flow",
            description="Custom flow",
            stages=[
                FlowStage(id="a", name="A", depends_on=None, fields={}),
            ],
        )

        text = serialize_flow(doc)

        # The prompt key is the very first line, in block-literal scalar style.
        assert text.startswith("prompt: |")
        # The prompt text is indented under the block-literal header.
        assert "  Top-level workflow prompt" in text
        # prompt precedes name, which precedes description, which precedes stages.
        idx_prompt = text.index("prompt: |")
        idx_name = text.index("name: My flow")
        idx_description = text.index("description: Custom flow")
        idx_stages = text.index("stages:")
        assert idx_prompt < idx_name < idx_description < idx_stages

    def test_serialize_flow_prompt_block_literal_multiline(self) -> None:
        """A multi-line prompt is emitted in block-literal style, line-by-line indented."""
        doc = FlowDocument(
            prompt="First line of the prompt.\nSecond line of the prompt.",
            name="N",
            description="D",
            stages=[],
        )

        text = serialize_flow(doc)

        assert text.startswith("prompt: |")
        assert "  First line of the prompt." in text
        assert "  Second line of the prompt." in text

    def test_serialize_flow_none_prompt_omits_key(self) -> None:
        """A ``None`` prompt produces no top-level ``prompt:`` key at all."""
        doc = FlowDocument(name="N", description="D", stages=[])

        text = serialize_flow(doc)

        assert "prompt:" not in text
        # The output still starts at name (the first emitted top-level key).
        assert text.startswith("name: N\n")

    def test_serialize_flow_prompt_round_trips_through_safe_load(self) -> None:
        """The serialized top-level prompt parses back to the original string value."""
        doc = FlowDocument(
            prompt="Round-trip prompt text",
            name="N",
            description="D",
            stages=[
                FlowStage(id="a", name="A", depends_on=None, fields={"interactive": True}),
            ],
        )

        text = serialize_flow(doc)
        loaded = yaml.safe_load(text)

        assert loaded["prompt"] == "Round-trip prompt text"
        assert loaded["name"] == "N"
        assert loaded["stages"][0]["id"] == "a"


class TestCompileFlowNoWorkflowOmitsPrompt:
    """End-to-end compile path: no workflow applied → no top-level prompt."""

    def test_compile_flow_workflow_none_omits_prompt(self, tmp_path: Path) -> None:
        """``compile_flow`` with no workflow applied writes no ``prompt:`` key."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: N\ndescription: D\n---\n\n- name: a\n  description: A\n")
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        text = flow_path.read_text()
        assert "prompt:" not in text
        assert "name: N" in text
        assert "description: D" in text
