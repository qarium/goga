"""Logic tests for the ``script_before``/``script``/``script_after`` slots + ``serialize_flow`` emission.

Covers the Task 5 serializer extension: multi-line values of the per-stage
``script_before``/``script``/``script_after`` keys must serialize in block-literal
scalar style (``|``), while single-line scripts and the boolean ``auto_approve``
field serialize as plain scalars. The block-literal representer mirrors the existing
``_BlockLiteralPrompt`` machinery: the default ``beautiful_yaml`` parameters render a
multi-line string single-quoted, so a dedicated marker class is mandatory.
"""

from __future__ import annotations

import yaml
from goga.pipeline.compiler import FlowDocument, FlowStage, serialize_flow


def _doc_with_fields(fields: dict[str, object]) -> FlowDocument:
    """Build a minimal ``FlowDocument`` carrying one stage with the given ``fields``."""
    return FlowDocument(
        name="N",
        description="D",
        stages=[FlowStage(id="a", name="A", depends_on=None, fields=fields)],
    )


class TestSerializeFlowScriptSlot:
    """Behavioral tests for the per-stage ``script_*`` and ``auto_approve`` emission rules."""

    def test_serialize_flow_importable(self) -> None:
        """``serialize_flow`` is exported from the compiler facade."""
        from goga.pipeline.compiler import serialize_flow as imported

        assert callable(imported)

    def test_serialize_auto_approve_plain_bool(self) -> None:
        """``auto_approve`` (bool) serializes as a plain scalar — not quoted, not block."""
        doc = _doc_with_fields({"auto_approve": True})

        text = serialize_flow(doc)

        assert "auto_approve: true" in text
        # Not block-literal (no trailing pipe on the key line).
        assert "auto_approve: |" not in text
        # Not single-quoted.
        assert "auto_approve: 'true'" not in text

    def test_serialize_multiline_script_block_literal(self) -> None:
        """A multi-line ``script`` value serializes as a block-literal scalar, indented, unquoted."""
        doc = _doc_with_fields({"script": "set -e\necho hi\nmake build"})

        text = serialize_flow(doc)

        # Block-literal header, not a quoted scalar.
        assert "script: |" in text
        assert "script: 'set" not in text
        # Each line indented under the block-literal header.
        assert "  set -e" in text
        assert "  echo hi" in text
        assert "  make build" in text

    def test_serialize_single_line_script_plain(self) -> None:
        """A single-line ``script`` value serializes as a plain scalar — no block header."""
        doc = _doc_with_fields({"script": "make build"})

        text = serialize_flow(doc)

        assert "script: make build" in text
        # Not block-literal, not quoted.
        assert "script: |" not in text
        assert "script: 'make build'" not in text

    def test_serialize_multiline_script_before_and_after(self) -> None:
        """Multi-line ``script_before``/``script_after`` serialize in block-literal style."""
        doc = _doc_with_fields(
            {
                "script_before": "echo pre1\necho pre2",
                "script_after": "echo post1\necho post2",
            }
        )

        text = serialize_flow(doc)

        assert "script_before: |" in text
        assert "script_after: |" in text
        assert "  echo pre1" in text
        assert "  echo pre2" in text
        assert "  echo post1" in text
        assert "  echo post2" in text

    def test_serialize_script_round_trips_through_safe_load(self) -> None:
        """A multi-line ``script`` block parses back to the original string value."""
        original = "set -e\necho hi\nmake build"
        doc = _doc_with_fields({"script": original})

        text = serialize_flow(doc)
        loaded = yaml.safe_load(text)

        assert loaded["stages"][0]["script"] == original

    def test_serialize_auto_approve_false_plain_bool(self) -> None:
        """``auto_approve: false`` also serializes as a plain scalar."""
        doc = _doc_with_fields({"auto_approve": False})

        text = serialize_flow(doc)

        assert "auto_approve: false" in text
        assert "auto_approve: |" not in text
