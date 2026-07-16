"""Compiler-cell integration tests for the header-level ``agents`` directive.

These tests cover the cross-entity, end-to-end path inside the compiler cell when a
pipeline-file carries an optional ``agents`` block: the file is read, parsed via
``parse_dsl`` (which projects the validated ``agents`` block onto
``PipelineHeader.agents``), compiled by ``compile_flow`` into a written afm
flow-file, and the function returns a ``(PipelineDocument, FlowDocument)`` tuple.

The integration surface is ``compile_flow`` only; it internally drives ``parse_dsl``
and the data models, so a passing suite here means the whole parse → compile →
return path composes correctly. The three scenarios mirror the design document:

- **A** (no ``agents`` block): ``header.agents is None`` and the flow-file is written.
- **B** (partial override — ``agents.planning`` only): the inline text rides on the
  ``PipelineDocument`` but never reaches the flow-file (goga-side artifact).
- **C** (full override — all four keys): all four fields are populated on the
  ``PipelineDocument``; the flow-file still carries none of the inline prompt text.

A shared sentinel (``_OVERRIDE_MARKER``) marks the inline override text so each
leakage assertion is unambiguous — the marker appears in the source pipeline-file
and on the returned ``PipelineDocument`` but must never appear in the flow-file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from goga.pipeline.compiler import (
    FlowDocument,
    PipelineDocument,
    compile_flow,
)

# Distinctive marker injected into every inline override so leakage assertions are
# unambiguous: it must appear on the returned PipelineDocument and never in the
# compiled flow-file (the inline prompt is a goga-side artifact).
_OVERRIDE_MARKER = "OVERRIDE_MARKER"

# The four fixed agent keys, one per afm prompt file.
_AGENT_KEYS = ("planning", "implementation", "review", "summary")


def _phases_body() -> str:
    """A minimal single-step phases body shared by every scenario's pipeline-file."""
    return (
        "\n"
        "- name: propose\n"
        "  description: Propose\n"
    )


def _write_pipeline(tmp_path: Path, *, header_agents: str) -> Path:
    """Write a pipeline-file with the given header ``agents`` block to tmp_path.

    Args:
        tmp_path: pytest's per-test temporary directory.
        header_agents: The raw ``agents:`` block text (including the ``agents:`` key
            line) to insert between the description and the ``---`` separator. Pass an
            empty string for the no-agents scenario.

    Returns:
        The path to the written pipeline-file.
    """
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(
        "name: integration\n"
        "description: Integration scenario\n"
        f"{header_agents}"
        "---\n"
        f"{_phases_body()}",
    )
    return pipeline_path


class TestIntegrationAgentsScenarioA:
    """Scenario A — a pipeline-file without an ``agents`` block."""

    def test_no_agents_returns_tuple_with_none_agents(self, tmp_path: Path) -> None:
        """compile_flow returns a (PipelineDocument, FlowDocument) tuple with agents None.

        The flow-file is written, and — because the source carries no inline prompt
        text — the flow-file naturally contains no agent-prompt text.
        """
        pipeline_path = _write_pipeline(tmp_path, header_agents="")
        flow_path = tmp_path / "flow.yml"

        documents = compile_flow(pipeline_path, flow_path)

        # The contract is a 2-tuple of (PipelineDocument, FlowDocument).
        assert isinstance(documents, tuple)
        assert len(documents) == 2
        pipeline_doc, flow_doc = documents
        assert isinstance(pipeline_doc, PipelineDocument)
        assert isinstance(flow_doc, FlowDocument)

        # No agents block → header.agents is None.
        assert pipeline_doc.header.agents is None

        # The flow-file is written as a side effect.
        assert flow_path.exists()

        # The flow-file is well-formed: exactly name, description, stages at top level.
        loaded = yaml.safe_load(flow_path.read_text())
        assert list(loaded.keys()) == ["name", "description", "stages"]

        # No inline override text in the source → none can leak into the flow-file.
        flow_text = flow_path.read_text()
        assert _OVERRIDE_MARKER not in flow_text


class TestIntegrationAgentsScenarioB:
    """Scenario B — a partial override (``agents.planning`` only)."""

    def _override_block(self, marker_text: str) -> str:
        """Build an ``agents:`` header block with only the planning override set."""
        return (
            "agents:\n"
            f"  planning: {marker_text}\n"
        )

    def test_partial_override_carries_planning_not_implementation(self, tmp_path: Path) -> None:
        """An ``agents.planning`` override surfaces on the PipelineDocument, others stay None.

        The inline text rides on ``pipeline_doc.header.agents.planning``; the three
        unspecified fields are None. The inline text never reaches the flow-file.
        """
        marker_text = f"{_OVERRIDE_MARKER} planning"
        pipeline_path = _write_pipeline(tmp_path, header_agents=self._override_block(marker_text))
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path)

        # The override is visible on the returned PipelineDocument.
        assert pipeline_doc.header.agents is not None
        assert pipeline_doc.header.agents.planning == marker_text

        # The three unspecified fields are None (partial override).
        assert pipeline_doc.header.agents.implementation is None
        assert pipeline_doc.header.agents.review is None
        assert pipeline_doc.header.agents.summary is None

        # FlowDocument never carries agents (goga-side artifact).
        assert not hasattr(flow_doc, "agents")

        # The inline prompt text is a goga-side artifact — it must not leak into
        # the compiled afm flow-file.
        flow_text = flow_path.read_text()
        assert marker_text not in flow_text
        assert _OVERRIDE_MARKER not in flow_text

        # The flow-file remains well-formed despite the header agents block.
        loaded = yaml.safe_load(flow_path.read_text())
        assert list(loaded.keys()) == ["name", "description", "stages"]


class TestIntegrationAgentsScenarioC:
    """Scenario C — a full override (all four fixed keys set)."""

    def _full_override_block(self) -> str:
        """Build an ``agents:`` header block with all four overrides set."""
        lines = ["agents:"]
        for key in _AGENT_KEYS:
            lines.append(f"  {key}: {_OVERRIDE_MARKER} {key}")
        return "\n".join(lines) + "\n"

    def test_full_override_populates_all_four_fields(self, tmp_path: Path) -> None:
        """All four agent overrides are populated; the flow-file carries none of them.

        Every field on ``pipeline_doc.header.agents`` carries its inline text; the
        compiled flow-file still contains no override text (goga-side artifact).
        """
        pipeline_path = _write_pipeline(tmp_path, header_agents=self._full_override_block())
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path)

        # All four fields are populated with their inline override text.
        assert pipeline_doc.header.agents is not None
        for key in _AGENT_KEYS:
            assert getattr(pipeline_doc.header.agents, key) == f"{_OVERRIDE_MARKER} {key}"

        # FlowDocument never carries agents (goga-side artifact).
        assert not hasattr(flow_doc, "agents")

        # Despite every override being set, none leaks into the compiled flow-file.
        flow_text = flow_path.read_text()
        assert _OVERRIDE_MARKER not in flow_text

        # The flow-file remains well-formed with all four overrides present upstream.
        loaded = yaml.safe_load(flow_path.read_text())
        assert list(loaded.keys()) == ["name", "description", "stages"]


@pytest.mark.parametrize(
    "scenario",
    ["no_agents", "partial", "full"],
)
def test_compile_flow_always_returns_two_element_documents_tuple(
    tmp_path: Path,
    scenario: str,
) -> None:
    """Across every agents scenario, compile_flow returns a fixed 2-tuple of documents.

    A regression guard: the return shape (a 2-tuple of PipelineDocument then
    FlowDocument) is invariant of whether/how the agents block is authored.
    """
    if scenario == "no_agents":
        pipeline_path = _write_pipeline(tmp_path, header_agents="")
    elif scenario == "partial":
        pipeline_path = _write_pipeline(
            tmp_path,
            header_agents="agents:\n  planning: x\n",
        )
    else:  # full
        pipeline_path = _write_pipeline(
            tmp_path,
            header_agents=(
                "agents:\n"
                "  planning: a\n"
                "  implementation: b\n"
                "  review: c\n"
                "  summary: d\n"
            ),
        )
    flow_path = tmp_path / "flow.yml"

    documents = compile_flow(pipeline_path, flow_path)

    assert isinstance(documents, tuple)
    assert len(documents) == 2
    pipeline_doc, flow_doc = documents
    assert isinstance(pipeline_doc, PipelineDocument)
    assert isinstance(flow_doc, FlowDocument)
