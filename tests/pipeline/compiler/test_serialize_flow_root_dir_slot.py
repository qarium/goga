"""Logic tests for the ``FlowDocument.root_dir`` slot + ``serialize_flow`` emission.

Covers the ``root_dir`` serializer extension: a non-``None`` top-level
``root_dir`` is emitted as a plain scalar in the SECOND top-level slot
(immediately after ``prompt`` when present, before ``name``); a ``None``
``root_dir`` omits the key entirely. The end-to-end compile path (no
``root_dir`` supplied) must produce no top-level ``root_dir:`` key.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from goga.pipeline.compiler import FlowDocument, FlowStage, compile_flow, serialize_flow


class TestSerializeFlowRootDirSlot:
    """Behavioral tests for the top-level root_dir emission rules."""

    def test_serialize_flow_emits_root_dir_before_name_when_set(self) -> None:
        """A non-None root_dir is emitted before ``name`` and after ``prompt`` (when present)."""
        doc = FlowDocument(
            prompt="Top-level workflow prompt",
            root_dir="/workspace",
            name="My flow",
            description="Custom flow",
            stages=[
                FlowStage(id="a", name="A", depends_on=None, fields={}),
            ],
        )

        text = serialize_flow(doc)

        # root_dir is emitted as a plain scalar, not block-literal.
        assert "root_dir: /workspace\n" in text
        # Order: prompt < root_dir < name < description < stages.
        idx_prompt = text.index("prompt: |")
        idx_root_dir = text.index("root_dir: /workspace")
        idx_name = text.index("name: My flow")
        idx_description = text.index("description: Custom flow")
        idx_stages = text.index("stages:")
        assert idx_prompt < idx_root_dir < idx_name < idx_description < idx_stages

    def test_serialize_flow_emits_root_dir_first_when_no_prompt(self) -> None:
        """A non-None root_dir with no prompt is emitted as the FIRST top-level key."""
        doc = FlowDocument(
            root_dir="/workspace",
            name="My flow",
            description="Custom flow",
            stages=[
                FlowStage(id="a", name="A", depends_on=None, fields={}),
            ],
        )

        text = serialize_flow(doc)

        # root_dir is the very first line.
        assert text.startswith("root_dir: /workspace\n")
        # No prompt key.
        assert "prompt:" not in text

    def test_serialize_flow_root_dir_plain_scalar(self) -> None:
        """``root_dir`` is emitted as a plain scalar (not block-literal like ``prompt``)."""
        doc = FlowDocument(
            root_dir="/workspace",
            name="N",
            description="D",
            stages=[],
        )

        text = serialize_flow(doc)

        # Plain scalar style — no block-literal marker.
        assert "root_dir: /workspace\n" in text
        assert "root_dir: |" not in text

    def test_serialize_flow_none_root_dir_omits_key(self) -> None:
        """A ``None`` root_dir produces no top-level ``root_dir:`` key at all."""
        doc = FlowDocument(name="N", description="D", stages=[])

        text = serialize_flow(doc)

        assert "root_dir:" not in text
        # The output still starts at name (the first emitted top-level key).
        assert text.startswith("name: N\n")

    def test_serialize_flow_root_dir_round_trips_through_safe_load(self) -> None:
        """The serialized top-level root_dir parses back to the original string value."""
        doc = FlowDocument(
            root_dir="/workspace",
            name="N",
            description="D",
            stages=[
                FlowStage(id="a", name="A", depends_on=None, fields={"interactive": True}),
            ],
        )

        text = serialize_flow(doc)
        loaded = yaml.safe_load(text)

        assert loaded["root_dir"] == "/workspace"
        assert loaded["name"] == "N"
        assert loaded["stages"][0]["id"] == "a"


class TestCompileFlowRootDir:
    """End-to-end compile path: ``root_dir`` parameter forwarding into the flow-file."""

    def test_compile_flow_without_root_dir_omits_key(self, tmp_path: Path) -> None:
        """``compile_flow`` without ``root_dir`` writes no top-level ``root_dir`` key (back-compat)."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: N\ndescription: D\n---\n\n- name: a\n  title: A\n")
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        text = flow_path.read_text()
        assert "root_dir" not in yaml.safe_load(text)
        assert text.startswith("name: N\n")

    def test_compile_flow_with_root_dir_emits_key(self, tmp_path: Path) -> None:
        """``compile_flow`` with ``root_dir`` emits the top-level ``root_dir`` key before ``name``."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: N\ndescription: D\n---\n\n- name: a\n  title: A\n")
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path, root_dir="/workspace")

        text = flow_path.read_text()
        loaded = yaml.safe_load(text)
        assert loaded["root_dir"] == "/workspace"
        # Order: root_dir < name.
        assert text.index("root_dir: /workspace") < text.index("name: N")

    def test_compile_flow_with_root_dir_and_workflow_emits_both_prompt_and_root_dir(
        self, tmp_path: Path
    ) -> None:
        """When both workflow and root_dir are supplied, prompt precedes root_dir in the output."""
        from goga.pipeline.workflow import WorkflowDocument

        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: N\ndescription: D\n---\n\n- name: a\n  title: A\n")
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(prompt="Top-level workflow prompt")

        compile_flow(pipeline_path, flow_path, workflow=workflow, root_dir="/workspace")

        text = flow_path.read_text()
        # Both keys present, prompt before root_dir before name.
        idx_prompt = text.index("prompt: |")
        idx_root_dir = text.index("root_dir: /workspace")
        idx_name = text.index("name: N")
        assert idx_prompt < idx_root_dir < idx_name
