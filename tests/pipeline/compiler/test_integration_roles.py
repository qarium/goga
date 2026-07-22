"""Compiler-cell integration tests for the header-level ``roles`` directive.

These tests cover the cross-entity, end-to-end path inside the compiler cell when a
pipeline-file carries an optional ``roles`` block: the file is read, parsed via
``parse_dsl`` (which projects the validated ``roles`` block onto
``PipelineHeader.roles``), compiled by ``compile_flow`` into a written afm
flow-file, and the function returns a ``(PipelineDocument, FlowDocument)`` tuple.

The integration surface is ``compile_flow`` only; it internally drives ``parse_dsl``
and the data models, so a passing suite here means the whole parse → compile →
return path composes correctly. The three scenarios mirror the design document:

- **A** (no ``roles`` block): ``header.roles is None`` and the flow-file is written.
- **B** (partial override — ``roles.planner`` only): the inline text rides on the
  ``PipelineDocument`` but never reaches the flow-file (goga-side artifact).
- **C** (full override — all three roles): every field is populated on the
  ``PipelineDocument``; the flow-file still carries none of the inline prompt text.

The three overridable roles are ``planner``/``executor``/``reviewer`` (each
resolved to its afm agent name / prompt-file stem via ``translate_role``);
``summary`` is NOT a role — it is a separate, always-default channel and has no
field on ``PipelineRoles``.

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
    StructuralError,
    compile_flow,
)

# Distinctive marker injected into every inline override so leakage assertions are
# unambiguous: it must appear on the returned PipelineDocument and never in the
# compiled flow-file (the inline prompt is a goga-side artifact).
_OVERRIDE_MARKER = "OVERRIDE_MARKER"

# The three fixed overridable roles (one per afm prompt-file stem, resolved via
# ``translate_role``). ``summary`` is intentionally absent — it is a separate,
# always-default channel, not an overridable role.
_ROLE_KEYS = ("planner", "executor", "reviewer")


def _phases_body() -> str:
    """A minimal single-step phases body shared by every scenario's pipeline-file."""
    return "\n- name: propose\n  title: Propose\n"


def _write_pipeline(tmp_path: Path, *, header_roles: str) -> Path:
    """Write a pipeline-file with the given header ``roles`` block to tmp_path.

    Args:
        tmp_path: pytest's per-test temporary directory.
        header_roles: The raw ``roles:`` block text (including the ``roles:`` key
            line) to insert between the description and the ``---`` separator. Pass an
            empty string for the no-roles scenario.

    Returns:
        The path to the written pipeline-file.
    """
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(
        f"name: integration\ndescription: Integration scenario\n{header_roles}---\n{_phases_body()}",
    )
    return pipeline_path


class TestIntegrationRolesScenarioA:
    """Scenario A — a pipeline-file without a ``roles`` block."""

    def test_no_roles_returns_tuple_with_none_roles(self, tmp_path: Path) -> None:
        """compile_flow returns a (PipelineDocument, FlowDocument) tuple with roles None.

        The flow-file is written, and — because the source carries no inline prompt
        text — the flow-file naturally contains no role-prompt text.
        """
        pipeline_path = _write_pipeline(tmp_path, header_roles="")
        flow_path = tmp_path / "flow.yml"

        documents = compile_flow(pipeline_path, flow_path)

        # The contract is a 2-tuple of (PipelineDocument, FlowDocument).
        assert isinstance(documents, tuple)
        assert len(documents) == 2
        pipeline_doc, flow_doc = documents
        assert isinstance(pipeline_doc, PipelineDocument)
        assert isinstance(flow_doc, FlowDocument)

        # No roles block → header.roles is None.
        assert pipeline_doc.header.roles is None

        # The flow-file is written as a side effect.
        assert flow_path.exists()

        # The flow-file is well-formed: exactly name, description, stages at top level.
        loaded = yaml.safe_load(flow_path.read_text())
        assert list(loaded.keys()) == ["name", "description", "stages"]

        # No inline override text in the source → none can leak into the flow-file.
        flow_text = flow_path.read_text()
        assert _OVERRIDE_MARKER not in flow_text


class TestIntegrationRolesScenarioB:
    """Scenario B — a partial override (``roles.planner`` only)."""

    def _override_block(self, marker_text: str) -> str:
        """Build a ``roles:`` header block with only the planner override set."""
        return f"roles:\n  planner: {marker_text}\n"

    def test_partial_override_carries_planner_not_executor(self, tmp_path: Path) -> None:
        """A ``roles.planner`` override surfaces on the PipelineDocument, others stay None.

        The inline text rides on ``pipeline_doc.header.roles.planner``; the two
        unspecified roles are None and there is no ``summary`` field. The inline
        text never reaches the flow-file.
        """
        marker_text = f"{_OVERRIDE_MARKER} planner"
        pipeline_path = _write_pipeline(tmp_path, header_roles=self._override_block(marker_text))
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path)

        # The override is visible on the returned PipelineDocument.
        assert pipeline_doc.header.roles is not None
        assert pipeline_doc.header.roles.planner == marker_text

        # The two unspecified roles are None (partial override).
        assert pipeline_doc.header.roles.executor is None
        assert pipeline_doc.header.roles.reviewer is None
        # summary is NOT a role — there is no summary field to override.
        assert not hasattr(pipeline_doc.header.roles, "summary")

        # FlowDocument never carries agents (goga-side artifact).
        assert not hasattr(flow_doc, "agents")

        # The inline prompt text is a goga-side artifact — it must not leak into
        # the compiled afm flow-file.
        flow_text = flow_path.read_text()
        assert marker_text not in flow_text
        assert _OVERRIDE_MARKER not in flow_text

        # The flow-file remains well-formed despite the header roles block.
        loaded = yaml.safe_load(flow_path.read_text())
        assert list(loaded.keys()) == ["name", "description", "stages"]


class TestIntegrationRolesScenarioC:
    """Scenario C — a full override (all three fixed roles set)."""

    def _full_override_block(self) -> str:
        """Build a ``roles:`` header block with all three overrides set."""
        lines = ["roles:"]
        for key in _ROLE_KEYS:
            lines.append(f"  {key}: {_OVERRIDE_MARKER} {key}")
        return "\n".join(lines) + "\n"

    def test_full_override_populates_all_three_fields(self, tmp_path: Path) -> None:
        """All three role overrides are populated; the flow-file carries none of them.

        Every field on ``pipeline_doc.header.roles`` carries its inline text; the
        compiled flow-file still contains no override text (goga-side artifact).
        """
        pipeline_path = _write_pipeline(tmp_path, header_roles=self._full_override_block())
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path)

        # All three roles are populated with their inline override text.
        assert pipeline_doc.header.roles is not None
        for key in _ROLE_KEYS:
            assert getattr(pipeline_doc.header.roles, key) == f"{_OVERRIDE_MARKER} {key}"
        # summary is NOT a role — there is no summary field.
        assert not hasattr(pipeline_doc.header.roles, "summary")

        # FlowDocument never carries agents (goga-side artifact).
        assert not hasattr(flow_doc, "agents")

        # Despite every override being set, none leaks into the compiled flow-file.
        flow_text = flow_path.read_text()
        assert _OVERRIDE_MARKER not in flow_text

        # The flow-file remains well-formed with all three overrides present upstream.
        loaded = yaml.safe_load(flow_path.read_text())
        assert list(loaded.keys()) == ["name", "description", "stages"]


@pytest.mark.parametrize(
    "scenario",
    ["no_roles", "partial", "full"],
)
def test_compile_flow_always_returns_two_element_documents_tuple(
    tmp_path: Path,
    scenario: str,
) -> None:
    """Across every roles scenario, compile_flow returns a fixed 2-tuple of documents.

    A regression guard: the return shape (a 2-tuple of PipelineDocument then
    FlowDocument) is invariant of whether/how the roles block is authored.
    """
    if scenario == "no_roles":
        pipeline_path = _write_pipeline(tmp_path, header_roles="")
    elif scenario == "partial":
        pipeline_path = _write_pipeline(
            tmp_path,
            header_roles="roles:\n  planner: x\n",
        )
    else:  # full
        pipeline_path = _write_pipeline(
            tmp_path,
            header_roles=("roles:\n  planner: a\n  executor: b\n  reviewer: c\n"),
        )
    flow_path = tmp_path / "flow.yml"

    documents = compile_flow(pipeline_path, flow_path)

    assert isinstance(documents, tuple)
    assert len(documents) == 2
    pipeline_doc, flow_doc = documents
    assert isinstance(pipeline_doc, PipelineDocument)
    assert isinstance(flow_doc, FlowDocument)


class TestStageBodyRolesFlowBIntegration:
    """Flow B — stage-body ``roles`` → output ``agents`` through ``compile_flow`` + ``serialize_flow``.

    Cross-entity within the compiler cell: a multi-stage pipeline carries ``roles``
    lists on its stage bodies. ``compile_flow`` runs ``_canonical_fields`` →
    ``_inject_defaults`` which translates each role element to its afm agent name via
    the single ``translate_role`` source of truth; ``serialize_flow`` then writes the
    output ``agents`` field to the flow-file. The header ``roles`` override and the
    stage-body ``roles`` lists compose in one pipeline — a header override rides the
    PipelineDocument (goga-side), while stage-body roles become output afm agents.
    """

    def test_stage_body_roles_translate_to_output_agents_and_header_roles_compose(self, tmp_path: Path) -> None:
        """Stage-body ``roles`` compile to output ``agents``; the header override stays goga-side.

        A two-stage pipeline: stage ``conventions`` carries ``roles: [planner, executor]``
        (known aliases → translated to ``[planning, implementation]``) and stage
        ``lint`` carries ``roles: [planning, custom-thing]`` (verbatim passthrough —
        already-afm names and arbitrary names are untranslated). The header also
        carries a ``roles.planner`` override. The header override rides the
        PipelineDocument and never reaches the flow-file; each stage's output
        ``agents`` reflects the element-wise ``translate_role`` mapping.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: review\n"
            "description: Review pipeline\n"
            "roles:\n"
            "  planner: HEADER_PLANNER_OVERRIDE\n"
            "---\n"
            "\n"
            "conventions:\n"
            "  title: Conventions\n"
            "  roles:\n"
            "    - planner\n"
            "    - executor\n"
            "lint:\n"
            "  title: Lint\n"
            "  roles:\n"
            "    - planning\n"
            "    - custom-thing\n",
        )
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path)

        # The header ``roles.planner`` override rides the PipelineDocument (goga-side).
        assert pipeline_doc.header.roles is not None
        assert pipeline_doc.header.roles.planner == "HEADER_PLANNER_OVERRIDE"

        # Stages are keyed by their stage id (the STAGES map key).
        stages_by_id = {stage.id: stage for stage in flow_doc.stages}
        conventions = stages_by_id["conventions"]
        lint = stages_by_id["lint"]

        # Known aliases translated element-wise via translate_role.
        assert conventions.fields["agents"] == ["planning", "implementation"]
        # Verbatim passthrough — already-afm names and arbitrary names untranslated.
        assert lint.fields["agents"] == ["planning", "custom-thing"]
        # The input-only ``roles`` key never reaches the output fields.
        assert "roles" not in conventions.fields
        assert "roles" not in lint.fields

        # serialize_flow wrote the translated output agents to the flow-file.
        flow_text = flow_path.read_text()
        assert "agents: [planning, implementation]" in flow_text
        assert "agents: [planning, custom-thing]" in flow_text
        # The input-only ``roles`` key never appears in the compiled flow-file.
        assert "roles:" not in flow_text
        # The header override never reaches the compiled flow-file.
        assert "HEADER_PLANNER_OVERRIDE" not in flow_text


class TestLegacyAgentsHardFailIntegration:
    """Legacy ``agents`` hard-fails end-to-end through ``compile_flow``.

    The authoring-side directive is ``roles`` (header block) and ``roles`` (stage-body
    field); ``agents`` is the output-only afm name and is forbidden on the input side.
    A user copying the legacy shape is caught by ``parse_dsl`` (header) or by
    ``_canonical_fields`` (stage body) and the structural error surfaces through
    ``compile_flow`` unchanged.
    """

    def test_legacy_header_agents_hard_fails(self, tmp_path: Path) -> None:
        """A legacy ``agents:`` header key raises a structural error through compile_flow."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: legacy\n"
            "description: Legacy header\n"
            "agents:\n"
            "  planning: x\n"
            "---\n"
            "\n"
            "- name: propose\n"
            "  title: Propose\n",
        )
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(StructuralError, match="agents key is forbidden in header; use roles"):
            compile_flow(pipeline_path, flow_path)

    def test_legacy_stage_body_agents_hard_fails(self, tmp_path: Path) -> None:
        """A legacy ``agents:`` stage-body key raises a structural error through compile_flow."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: legacy\n"
            "description: Legacy stage body\n"
            "---\n"
            "\n"
            "propose:\n"
            "  title: Propose\n"
            "  agents:\n"
            "    - planning\n",
        )
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(StructuralError, match="agents key is forbidden in stage body; use roles"):
            compile_flow(pipeline_path, flow_path)
