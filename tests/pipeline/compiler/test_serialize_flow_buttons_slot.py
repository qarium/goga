"""Logic tests for the per-stage ``buttons`` slot + ``serialize_flow`` emission.

Covers the Task 4 serializer extension: the per-stage ``buttons`` mapping (a map
of note name → prompt text assembled by ``compile_flow`` from the workflow
``notes`` instruction) serializes as a regular block-style mapping —
``default_flow_style=False`` already renders it block-style, so the branch adds
no new dump parameters. Single-line values serialize as plain scalars (quoted as
needed by the ``SafeDumper``), multi-line values are wrapped in the existing
``_BlockLiteralScript`` marker so they serialize in block-literal scalar style;
insertion order is preserved verbatim (never sorted).
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


class TestSerializeFlowButtonsSlot:
    """Behavioral tests for the per-stage ``buttons`` emission rules."""

    def test_serialize_flow_importable(self) -> None:
        """``serialize_flow`` is exported from the compiler facade."""
        from goga.pipeline.compiler import serialize_flow as imported

        assert callable(imported)

    def test_serialize_single_line_button_value_plain(self) -> None:
        """A single-line button value serializes as a plain scalar — unquoted."""
        doc = _doc_with_fields({"buttons": {"fix": "Fix it", "probe": "Line1\nLine2"}})

        text = serialize_flow(doc)

        assert "  fix: Fix it" in text
        # Not block-literal, not quoted.
        assert "  fix: |" not in text
        assert "  fix: 'Fix it'" not in text

    def test_serialize_multiline_button_value_block_literal(self) -> None:
        """A multi-line button value serializes in block-literal scalar style."""
        doc = _doc_with_fields({"buttons": {"fix": "Fix it", "probe": "Line1\nLine2"}})

        text = serialize_flow(doc)

        assert "  probe: |" in text
        assert "  probe: 'Line1" not in text
        # Each line indented under the block-literal header.
        assert "    Line1" in text
        assert "    Line2" in text

    def test_serialize_buttons_map_block_style(self) -> None:
        """The buttons mapping serializes block-style — not as a flow-style map."""
        doc = _doc_with_fields({"buttons": {"fix": "Fix it", "probe": "Line1\nLine2"}})

        text = serialize_flow(doc)

        assert "buttons:" in text
        assert "buttons: {" not in text

    def test_serialize_button_value_quoted_as_needed(self) -> None:
        """YAML-ambiguous single-line values are quoted so afm reads them back as strings."""
        doc = _doc_with_fields({"buttons": {"probe": "L1\nL2", "num": "123", "flag": "yes"}})

        text = serialize_flow(doc)

        assert "num: '123'" in text
        assert "flag: 'yes'" in text

    def test_serialize_buttons_round_trips_through_safe_load(self) -> None:
        """A buttons mapping parses back to the original map with all values ``str``."""
        doc = _doc_with_fields({"buttons": {"probe": "L1\nL2", "num": "123", "flag": "yes"}})

        text = serialize_flow(doc)
        loaded = yaml.safe_load(text)

        assert loaded["stages"][0]["buttons"] == {"probe": "L1\nL2", "num": "123", "flag": "yes"}
        assert all(
            isinstance(value, str) for value in loaded["stages"][0]["buttons"].values()
        )
