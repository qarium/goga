"""Contract and logic tests for the ``compile_flow`` entry point.

Covers the entry-point half of the compiler cell: reading a goga DSL pipeline-file
via ``parse_dsl``, applying per-format ``depends_on`` rules (PHASES:
position-derived; STAGES: pass-through), reordering step bodies into canonical
key order via the internal ``_canonical_fields`` helper, and writing the canonical
afm flow-file. I/O and structural errors propagate unchanged; an empty body is
rejected here with ``StructuralError("empty body")``.
"""

from __future__ import annotations

import inspect
from itertools import pairwise
from pathlib import Path

import pytest
import yaml
from goga.pipeline.compiler import (
    FlowDocument,
    PipelineDocument,
    StructuralError,
    compile_flow,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "compile_flow"
_FEATURE_PHASES = _FIXTURES / "phases.yml"
_FEATURE_STAGES = _FIXTURES / "stages.yml"


class TestCompileFlowContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_compile_flow_importable_from_facade(self) -> None:
        """``compile_flow`` must be importable from the facade."""
        assert compile_flow is not None

    def test_compile_flow_signature(self) -> None:
        """``compile_flow`` takes three parameters: ``pipeline_path``, ``flow_path``, ``workflow``."""
        parameters = list(inspect.signature(compile_flow).parameters)

        assert parameters == ["pipeline_path", "flow_path", "workflow"]

    def test_compile_flow_workflow_kwarg_defaults_to_none(self) -> None:
        """The optional ``workflow`` parameter defaults to ``None``."""
        workflow_param = inspect.signature(compile_flow).parameters["workflow"]

        assert workflow_param.default is None

    def test_compile_flow_returns_documents_tuple_on_minimal_valid_input(self, tmp_path: Path) -> None:
        """A minimal valid phases input compiles and returns the documents tuple."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: N\ndescription: D\n---\n\n- name: a\n  title: A\n")
        flow_path = tmp_path / "flow.yml"

        result = compile_flow(pipeline_path, flow_path)

        # The contract is a 2-tuple of (PipelineDocument, FlowDocument).
        assert isinstance(result, tuple)
        assert len(result) == 2
        pipeline_doc, flow_doc = result
        assert isinstance(pipeline_doc, PipelineDocument)
        assert isinstance(flow_doc, FlowDocument)
        # FlowDocument never carries agents (goga-side artifact).
        assert not hasattr(flow_doc, "agents")
        # No roles block → header.roles is None.
        assert pipeline_doc.header.roles is None
        assert flow_path.exists()

    def test_compile_flow_returns_documents_tuple_with_roles(self, tmp_path: Path) -> None:
        """A pipeline-file with a ``roles.planner`` override surfaces it on the returned PipelineDocument."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "roles:\n"
            "  planner: |\n"
            "    Custom planning prompt.\n"
            "---\n"
            "\n"
            "- name: a\n"
            "  title: A\n",
        )
        flow_path = tmp_path / "flow.yml"

        documents = compile_flow(pipeline_path, flow_path)

        assert isinstance(documents, tuple)
        assert len(documents) == 2
        pipeline_doc, flow_doc = documents
        assert isinstance(pipeline_doc, PipelineDocument)
        assert isinstance(flow_doc, FlowDocument)
        assert pipeline_doc.header.roles is not None
        assert pipeline_doc.header.roles.planner == "Custom planning prompt.\n"
        # FlowDocument does not carry agents (goga-side artifact).
        assert not hasattr(flow_doc, "agents")
        # The flow-file is still written as a side effect.
        assert flow_path.exists()

    def test_compile_flow_returns_pipeline_document_with_none_roles_when_absent(self, tmp_path: Path) -> None:
        """A pipeline-file without a ``roles`` block yields a PipelineDocument whose roles is None."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n",
        )
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, _flow_doc = compile_flow(pipeline_path, flow_path)

        assert pipeline_doc.header.roles is None

    def test_pipeline_doc_roles_does_not_leak_into_flow_file_text(self, tmp_path: Path) -> None:
        """Inline role prompts ride on PipelineDocument but never reach the compiled flow-file."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\nroles:\n  planner: Custom\n---\n\n- name: a\n  title: A\n",
        )
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, _flow_doc = compile_flow(pipeline_path, flow_path)

        # The override is visible on the returned PipelineDocument ...
        assert pipeline_doc.header.roles is not None
        assert pipeline_doc.header.roles.planner == "Custom"
        # ... but never serialized into the afm flow-file.
        assert "Custom" not in flow_path.read_text()

    def test_private_helpers_not_on_facade(self) -> None:
        """``_canonical_fields`` and ``_CANONICAL_KEY_ORDER`` are module-internal, not facade names."""
        from goga.pipeline.compiler import __all__ as facade_all

        assert "_canonical_fields" not in facade_all
        assert "_CANONICAL_KEY_ORDER" not in facade_all


class TestCompileFlowLogic:
    """Behavioral tests against the documented algorithm and edge cases."""

    def test_compile_flow_phases_to_flow_document(self, tmp_path: Path) -> None:
        """A 2-step phases input yields a flow-file with position-derived depends_on."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "- name: a\n"
            "  title: A\n"
            "  prompt: Do A\n"
            "- name: b\n"
            "  title: B\n"
            "  prompt: Do B\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        loaded = yaml.safe_load(flow_path.read_text())

        assert loaded["name"] == "T"
        assert loaded["description"] == "T"
        assert [stage["id"] for stage in loaded["stages"]] == ["a", "b"]
        # First step has no depends_on (position 0); second depends on the first.
        assert "depends_on" not in loaded["stages"][0]
        assert loaded["stages"][1]["depends_on"] == ["a"]

    def test_compile_flow_stages_passes_through_depends_on(self, tmp_path: Path) -> None:
        """A 3-step stages input preserves the null / empty / list tristate verbatim."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "a:\n"
            "  title: A\n"
            "  depends_on:\n"
            "b:\n"
            "  title: B\n"
            "  depends_on: []\n"
            "c:\n"
            "  title: C\n"
            "  depends_on: [a]\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        # None (absent in source) → no depends_on key; [] → explicit empty; [a] → list.
        assert stages[0]["id"] == "a"
        assert "depends_on" not in stages[0]
        assert stages[1]["depends_on"] == []
        assert stages[2]["depends_on"] == ["a"]

    def test_compile_flow_idempotent(self, tmp_path: Path) -> None:
        """Compiling the same input twice produces byte-identical output."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_FEATURE_PHASES.read_text())
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)
        first = flow_path.read_text()

        compile_flow(pipeline_path, flow_path)
        second = flow_path.read_text()

        assert first == second

    def test_compile_flow_empty_body_raises(self, tmp_path: Path) -> None:
        """An empty body segment (zero steps) raises StructuralError("empty body")."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\n")
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(StructuralError, match="empty body"):
            compile_flow(pipeline_path, flow_path)

    def test_compile_flow_pipeline_file_not_found_propagates(self, tmp_path: Path) -> None:
        """A missing pipeline_path raises FileNotFoundError unwrapped (no try/except)."""
        pipeline_path = tmp_path / "missing.yml"
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(FileNotFoundError):
            compile_flow(pipeline_path, flow_path)

    def test_compile_flow_canonical_order_with_unknown_fields(self, tmp_path: Path) -> None:
        """Extras sort alphabetically after the known canonical keys.

        The source stage lacks ``agents`` — the compiler injects the single
        default field (``agents``) into the assembled ``FlowStage.fields``. It
        lands between ``interactive`` and the alphabetical extras (``apple``,
        ``zebra``).
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  zebra: 1\n  apple: 2\n  interactive: true\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        text = flow_path.read_text()

        # Canonical order: interactive (known), then the injected default
        # (agents — a known key in the canonical order), then apple, zebra
        # (extras sorted alphabetically).
        idx_interactive = text.index("interactive: true")
        idx_agents = text.index("agents:")
        idx_apple = text.index("apple: 2")
        idx_zebra = text.index("zebra: 1")
        assert idx_interactive < idx_agents < idx_apple < idx_zebra

    def test_compile_flow_phases_fixture_depends_on_chains(self, tmp_path: Path) -> None:
        """The canonical phases fixture compiles to a position-derived dependency chain."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_FEATURE_PHASES.read_text())
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        # First stage carries no depends_on; every later stage depends on its predecessor's id.
        assert "depends_on" not in stages[0]
        for prev, curr in pairwise(stages):
            assert curr["depends_on"] == [prev["id"]]

    def test_compile_flow_stages_fixture_preserves_authored_depends_on(self, tmp_path: Path) -> None:
        """The canonical stages fixture passes authored depends_on through unchanged."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(_FEATURE_STAGES.read_text())
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        # First stage (propose) authored no depends_on; second (propose-review) depends on propose.
        assert stages[0]["id"] == "propose"
        assert "depends_on" not in stages[0]
        assert stages[1]["depends_on"] == ["propose"]

    def test_compile_flow_deep_copies_fields(self, tmp_path: Path) -> None:
        """``_canonical_fields`` deep-copies values — mutating the source body cannot reach the fields.

        Verified directly on the helper because ``compile_flow`` reads from disk and
        discards its parsed body before returning, so the isolation is not observable
        through the public ``compile_flow`` return value.
        """
        from goga.pipeline.compiler.compile_flow import _canonical_fields

        source_body = {"roles": ["planner"], "nested": {"k": 1}}
        fields = _canonical_fields(source_body)

        # Canonical order is established (``agents`` is a known output key) and the
        # input ``roles`` was translated to the output ``agents`` via translate_role.
        assert list(fields.keys()) == ["agents", "nested"]
        assert fields["agents"] == ["planning"]
        # The input-only ``roles`` key never reaches the output fields.
        assert "roles" not in fields

        # Mutating the ordered fields must not reach back into the source body
        # (genuine deep-copy isolation, not an alias to the source values).
        fields["agents"].append("hacked")
        fields["nested"]["extra"] = True

        assert source_body["roles"] == ["planner"]
        assert source_body["nested"] == {"k": 1}

    def test_compile_flow_missing_flow_path_parent_raises(self, tmp_path: Path) -> None:
        """A flow_path whose parent directory does not exist raises FileNotFoundError."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\n- name: a\n  title: A\n")
        flow_path = tmp_path / "nonexistent_dir" / "flow.yml"

        with pytest.raises(FileNotFoundError):
            compile_flow(pipeline_path, flow_path)

    def test_compile_flow_phases_authored_id_does_not_clobber(self, tmp_path: Path) -> None:
        """An authored ``id`` in a phase item does not override the position-derived id chain.

        Without parser-level exclusion, the authored value would leak into
        ``FlowStage.fields`` and clobber the serializer's seeded ``id``, leaving the
        next stage's position-derived ``depends_on`` pointing at a non-existent id.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "- name: a\n"
            "  title: A\n"
            "  id: collision-a\n"
            "- name: b\n"
            "  title: B\n"
            "  id: collision-b\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        # ids derive from the step names; the authored collision values are dropped.
        assert [stage["id"] for stage in stages] == ["a", "b"]
        # b depends on its predecessor's id (a), not on any clobbered value.
        assert stages[1]["depends_on"] == ["a"]

    def test_compile_flow_stages_authored_name_does_not_clobber(self, tmp_path: Path) -> None:
        """An authored ``name`` in a stage value does not override the title-derived label."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\n"
            "description: T\n"
            "---\n"
            "\n"
            "a:\n"
            "  title: Real Label\n"
            "  name: Collision Name\n"
            "  roles:\n"
            "    - planner\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        assert stages[0]["id"] == "a"
        assert stages[0]["name"] == "Real Label"

    def test_compile_flow_strips_authored_depends_on_in_first_phase(self, tmp_path: Path) -> None:
        """An authored ``depends_on`` on the first phase step never leaks into the output.

        Phases derive depends_on from position (first step gets none). Without stripping the
        authored value, the first step's None position-derived depends_on lets the authored
        value leak through as a dangling dependency. The second step's position-derived value
        must still chain to the first step's id.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  depends_on: [zzz]\n- name: b\n  title: B\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        stages = yaml.safe_load(flow_path.read_text())["stages"]

        # First step: authored depends_on stripped, no key emitted (position 0).
        assert "depends_on" not in stages[0]
        # Second step: position-derived, chains to predecessor — authored value irrelevant.
        assert stages[1]["depends_on"] == ["a"]

    def test_compile_flow_rejects_non_string_stage_key(self, tmp_path: Path) -> None:
        """A non-string stage map key raises StructuralError through compile_flow."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\n1:\n  title: A\n")
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(StructuralError, match="stage name must be a string"):
            compile_flow(pipeline_path, flow_path)


class TestCompileFlowRolesTranslation:
    """The authoring-side ``roles`` stage-body field translates to the output ``agents`` field.

    Pins the input ``roles`` → output ``agents`` translation via the single
    ``translate_role`` source of truth: known aliases map, unknown values pass
    through verbatim, an empty/missing ``roles`` injects ``["auto"]``, and the
    input-only ``roles`` key never reaches the compiled flow-file. A legacy
    ``agents`` key in a stage body hard-fails with a structural error.
    """

    def test_compile_flow_translates_stage_roles_to_output_agents(self, tmp_path: Path) -> None:
        """A stage body ``roles: [planner, executor]`` compiles to ``agents: [planning, implementation]``.

        The known aliases are translated to their afm stems; the input-only
        ``roles`` key never appears in the compiled flow-file.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\n  roles:\n    - planner\n    - executor\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        text = flow_path.read_text()
        # Known aliases translated element-wise via translate_role (flow-style).
        assert "agents: [planning, implementation]" in text
        # The input-only ``roles`` key never reaches the compiled flow-file.
        assert "roles:" not in text

    def test_compile_flow_rejects_legacy_agents_in_stage_body(self, tmp_path: Path) -> None:
        """A legacy ``agents`` key in a stage body raises StructuralError.

        The authoring-side stage-body field is ``roles``; ``agents`` is the
        output-only afm field and is forbidden on the input side.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\n  agents:\n    - planning\n",
        )
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(StructuralError, match="agents key is forbidden in stage body; use roles"):
            compile_flow(pipeline_path, flow_path)

    def test_compile_flow_empty_roles_injects_auto(self, tmp_path: Path) -> None:
        """A stage body ``roles: []`` injects the single ``agents: [auto]`` default.

        An empty ``roles`` list is unusable, so the default fires; the
        input-only ``roles`` key never reaches the compiled flow-file.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\n  roles: []\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        text = flow_path.read_text()
        assert "agents: [auto]" in text
        assert "roles:" not in text

    def test_compile_flow_roles_verbatim_passthrough_values(self, tmp_path: Path) -> None:
        """Unknown ``roles`` values pass through verbatim (no translation, no validation).

        ``planning`` (an already-afm name) and ``custom-thing`` (an arbitrary
        afm name) are not aliases, so ``translate_role`` returns them unchanged.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\n  roles:\n    - planning\n    - custom-thing\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        assert fields["agents"] == ["planning", "custom-thing"]
        assert "roles" not in fields
