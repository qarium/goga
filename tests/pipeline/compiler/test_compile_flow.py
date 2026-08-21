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
from goga.pipeline.workflow import parse_workflow

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "compile_flow"
_FEATURE_PHASES = _FIXTURES / "phases.yml"
_FEATURE_STAGES = _FIXTURES / "stages.yml"


class TestCompileFlowContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_compile_flow_importable_from_facade(self) -> None:
        """``compile_flow`` must be importable from the facade."""
        assert compile_flow is not None

    def test_compile_flow_signature(self) -> None:
        """``compile_flow`` takes five parameters (``project_name`` added)."""
        parameters = list(inspect.signature(compile_flow).parameters)

        assert parameters == ["pipeline_path", "flow_path", "workflow", "root_dir", "project_name"]

    def test_compile_flow_workflow_kwarg_defaults_to_none(self) -> None:
        """The optional ``workflow`` parameter defaults to ``None``."""
        workflow_param = inspect.signature(compile_flow).parameters["workflow"]

        assert workflow_param.default is None

    def test_compile_flow_root_dir_kwarg_defaults_to_none(self) -> None:
        """The optional ``root_dir`` parameter defaults to ``None``."""
        root_dir_param = inspect.signature(compile_flow).parameters["root_dir"]

        assert root_dir_param.default is None

    def test_compile_flow_project_name_kwarg_defaults_to_none(self) -> None:
        """The optional ``project_name`` parameter defaults to ``None``."""
        project_name_param = inspect.signature(compile_flow).parameters["project_name"]

        assert project_name_param.default is None

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

    def test_canonical_fields_signature_has_stage_name(self) -> None:
        """``_canonical_fields`` takes ``(body, stage_name)`` for the mutual-exclusion message."""
        import inspect

        from goga.pipeline.compiler.compile_flow import _canonical_fields

        parameters = list(inspect.signature(_canonical_fields).parameters)

        assert parameters == ["body", "stage_name"]

    def test_canonical_key_order_includes_approve_and_script_slots(self) -> None:
        """The extended canonical order slots ``auto_approve`` and the script_* keys."""
        from goga.pipeline.compiler.compile_flow import _CANONICAL_KEY_ORDER

        # ``auto_approve`` immediately follows ``interactive``; the script_*
        # family trails ``skills`` in authored order (before/script/after) and
        # closes with the translated ``script_timeout``.
        assert "auto_approve" in _CANONICAL_KEY_ORDER
        assert _CANONICAL_KEY_ORDER.index("auto_approve") == _CANONICAL_KEY_ORDER.index("interactive") + 1
        assert _CANONICAL_KEY_ORDER[-4:] == ["script_before", "script", "script_after", "script_timeout"]
        assert _CANONICAL_KEY_ORDER.index("skills") < _CANONICAL_KEY_ORDER.index("script_before")

    def test_approve_sentinel_constant_exists(self) -> None:
        """The ``_APPROVE_SENTINEL`` constant (approve directive plumbing) exists."""
        from goga.pipeline.compiler.compile_flow import _APPROVE_SENTINEL

        assert _APPROVE_SENTINEL == "_approve_directive"

    def test_compile_flow_and_structural_error_importable_from_facade(self) -> None:
        """``compile_flow`` and ``StructuralError`` are both importable from the facade.

        Step 4pre strict-validation raises ``StructuralError`` from ``compile_flow``;
        both names must be present on the compiler facade (no new export needed).
        """
        from goga.pipeline.compiler import StructuralError as FacadeStructuralError
        from goga.pipeline.compiler import compile_flow as facade_compile_flow

        assert facade_compile_flow is compile_flow
        assert FacadeStructuralError is StructuralError

    def test_strict_validate_stage_names_helper_exists(self) -> None:
        """The ``_strict_validate_stage_names`` reconstruction helper (step 4pre) exists."""
        from goga.pipeline.compiler.compile_flow import _strict_validate_stage_names

        assert callable(_strict_validate_stage_names)


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
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  zebra: 1\n  apple: 2\n  communication: true\n",
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
        fields = _canonical_fields(source_body, "deploy")

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

    def test_compile_flow_prefixes_description_with_project_name(self, tmp_path: Path) -> None:
        """A non-``None`` ``project_name`` prefixes the FlowDocument description.

        The prefix is OUTPUT-only: ``FlowDocument.description`` carries
        ``[{project_name}] {header.description}`` while the ``PipelineDocument``
        mirror stays unprefixed (the same OUTPUT-only posture as ``root_dir``).
        The written flow-file carries the prefixed description.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: Ship it\n---\n\n- name: a\n  title: A\n")
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path, project_name="widget")

        assert flow_doc.description == "[widget] Ship it"
        # PipelineDocument mirror stays unprefixed (OUTPUT-only, like root_dir).
        assert pipeline_doc.header.description == "Ship it"
        # The written flow-file carries the prefixed description.
        assert "description: '[widget] Ship it'" in flow_path.read_text()

    def test_compile_flow_no_prefix_when_project_name_none(self, tmp_path: Path) -> None:
        """A ``None`` ``project_name`` leaves the description unchanged (back-compat)."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: Ship it\n---\n\n- name: a\n  title: A\n")
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, flow_doc = compile_flow(pipeline_path, flow_path)

        assert flow_doc.description == "Ship it"
        assert pipeline_doc.header.description == "Ship it"


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


class TestCompileFlowCommunicationTranslation:
    """The authoring-side ``communication`` stage-body field translates to the output ``interactive`` field.

    Pins the input ``communication`` → output ``interactive`` translation: the
    authoring key is renamed into the canonical ``interactive`` slot before
    reordering, and an authoring ``interactive`` key hard-fails with a structural
    error (the afm output key ``interactive`` is stable — only ``communication``
    is ever authored). The canonical output key order (``interactive`` first) is
    unchanged by this rename.
    """

    def test_canonical_fields_translates_communication_to_interactive(self) -> None:
        """``_canonical_fields`` renames ``communication`` to the ``interactive`` slot.

        The renamed ``interactive`` lands in its canonical position (first among
        the known keys); the authoring ``communication`` key never reaches the
        output. Other keys (e.g. ``prompt``) are preserved.
        """
        from goga.pipeline.compiler.compile_flow import _canonical_fields

        result = _canonical_fields({"communication": True, "prompt": "p"}, "deploy")

        # ``interactive`` present (translated), ``communication`` absent.
        assert result["interactive"] is True
        assert "communication" not in result
        # ``interactive`` is the first known canonical key.
        assert next(iter(result)) == "interactive"
        # The unrelated ``prompt`` key survives.
        assert result["prompt"] == "p"

    def test_canonical_fields_rejects_authoring_interactive(self) -> None:
        """An authoring ``interactive`` key raises StructuralError.

        The authoring-side stage-body field is ``communication``; ``interactive``
        is the output-only afm field and is forbidden on the input side.
        """
        from goga.pipeline.compiler.compile_flow import _canonical_fields

        with pytest.raises(
            StructuralError,
            match="interactive key is forbidden in stage body; use communication",
        ):
            _canonical_fields({"interactive": True}, "deploy")

    def test_compile_flow_translates_stage_communication_to_output_interactive(self, tmp_path: Path) -> None:
        """A stage body ``communication: true`` compiles to ``interactive: true``.

        The authoring key is translated into the output ``interactive`` slot, and
        the authoring ``communication`` key never appears in the compiled flow-file.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\n  communication: true\n  prompt: do it\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        text = flow_path.read_text()
        fields = flow_doc.stages[0].fields
        # Translated into the output ``interactive`` slot.
        assert fields["interactive"] is True
        # Canonical ``interactive`` sits first among the known keys.
        assert next(iter(fields)) == "interactive"
        # The authoring ``communication`` key never reaches the output.
        assert "communication" not in fields
        assert "communication" not in text

    def test_compile_flow_rejects_authoring_interactive_in_stage_body(self, tmp_path: Path) -> None:
        """An authoring ``interactive`` key in a stage body raises StructuralError.

        Mirrors the legacy ``agents`` rejection: the authoring-side field is
        ``communication``; ``interactive`` is output-only.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\n  interactive: true\n",
        )
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(
            StructuralError,
            match="interactive key is forbidden in stage body; use communication",
        ):
            compile_flow(pipeline_path, flow_path)


class TestCompileFlowScriptDirectives:
    """Stage script directives ``before_script``/``script``/``after_script``.

    The authoring keys are consumed and translated to the output
    ``script_before``/``script``/``script_after`` keys (never passed through as
    unknown keys). ``script`` is mutually exclusive with ``prompt``/``skills``
    (a ``StructuralError`` naming the stage); ``before_script``/``after_script``
    are compatible with ``script``/``prompt``/``skills``.
    """

    def test_compile_script_directives_translated(self, tmp_path: Path) -> None:
        """``before_script``/``script``/``after_script`` translate to ``script_*``.

        The authoring keys are absent from the output; the output keys appear in
        authored order ``script_before`` before ``script`` before ``script_after``.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n"
            "a:\n"
            "  title: A\n"
            "  before_script: prep\n"
            "  script: run\n"
            "  after_script: cleanup\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)
        text = flow_path.read_text()

        fields = flow_doc.stages[0].fields
        # Authoring keys consumed; output keys present in authored order.
        assert fields["script_before"] == "prep"
        assert fields["script"] == "run"
        assert fields["script_after"] == "cleanup"
        keys = list(fields)
        assert keys.index("script_before") < keys.index("script") < keys.index("script_after")
        # The authoring keys never reach the output (not even as unknown keys).
        assert "before_script" not in fields
        assert "after_script" not in fields
        assert "before_script" not in text
        assert "after_script" not in text

    def test_compile_script_mutually_exclusive_with_prompt(self, tmp_path: Path) -> None:
        """``script`` + ``prompt`` raises ``StructuralError`` naming the stage."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\n  script: run\n  prompt: do it\n",
        )
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(
            StructuralError,
            match=r"script is mutually exclusive with prompt/skills in stage a",
        ):
            compile_flow(pipeline_path, flow_path)

    def test_compile_script_mutually_exclusive_with_skills(self, tmp_path: Path) -> None:
        """``script`` + ``skills`` raises ``StructuralError`` naming the stage (symmetric)."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\n  script: run\n  skills:\n    - web\n",
        )
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(
            StructuralError,
            match=r"script is mutually exclusive with prompt/skills in stage a",
        ):
            compile_flow(pipeline_path, flow_path)

    def test_compile_script_compatible_with_before_after(self, tmp_path: Path) -> None:
        """``script`` + ``before_script``/``after_script`` (no prompt/skills) compiles.

        The three authoring keys translate to ``script_before``/``script``/
        ``script_after`` with no error — ``before_script``/``after_script`` are
        compatible with ``script``.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n"
            "a:\n"
            "  title: A\n"
            "  before_script: prep\n"
            "  script: run\n"
            "  after_script: cleanup\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        assert fields["script_before"] == "prep"
        assert fields["script"] == "run"
        assert fields["script_after"] == "cleanup"

    def test_compile_script_suppresses_default_agents(self, tmp_path: Path) -> None:
        """``script`` without ``roles`` assembles NO ``agents`` key.

        afm rejects ``agents`` combined with ``script`` — the default
        ``["auto"]`` injection must not fire for script stages.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\na:\n  title: A\n  script: run\n")
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        assert "agents" not in flow_doc.stages[0].fields
        assert "agents" not in flow_path.read_text()

    def test_compile_script_suppresses_authored_roles(self, tmp_path: Path) -> None:
        """``script`` + authored ``roles`` emits no ``agents`` and raises no error.

        Both the translated ``roles`` value and the default are suppressed; the
        ``roles`` elements are still validated (a non-str element would raise).
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\n  script: run\n  roles:\n    - planner\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        assert fields["script"] == "run"
        assert "agents" not in fields
        assert "roles" not in fields

    def test_compile_script_with_roles_non_str_element_raises(self, tmp_path: Path) -> None:
        """A non-str ``roles`` element raises even under script suppression."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\n  script: run\n  roles:\n    - 1\n",
        )
        flow_path = tmp_path / "flow.yml"

        with pytest.raises(StructuralError, match=r"non-str value in stage roles list"):
            compile_flow(pipeline_path, flow_path)

    def test_compile_workflow_extend_script_suppresses_agents(self, tmp_path: Path) -> None:
        """An extend-stage body with ``script`` assembles no ``agents`` key.

        Extend-stages flow through the same ``_canonical_fields`` assembly, so
        the suppression covers them identically.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text("name: T\ndescription: T\n---\n\na:\n  title: A\n  prompt: p\n")
        flow_path = tmp_path / "flow.yml"
        workflow_path = tmp_path / "workflow.yml"
        workflow_path.write_text(
            "extend:\n"
            "  b:\n"
            "    after:\n"
            "      - a\n"
            "    title: B\n"
            "    script: run\n",
        )
        workflow = parse_workflow(workflow_path)

        _, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        by_id = {stage.id: stage.fields for stage in flow_doc.stages}
        assert "agents" not in by_id["b"]
        assert "agents" in by_id["a"]

    def test_compile_no_approve_baseline_byte_identical(self, tmp_path: Path) -> None:
        """A pipeline-file without approve/script directives compiles byte-identically.

        Backward-compat gate: the extended ``_CANONICAL_KEY_ORDER`` and the
        ``_canonical_fields`` rewrite must leave flow-files without the new
        directives byte-identical to the pre-change baseline — no ``auto_approve``,
        no ``script_*``, no ``_approve_directive`` sentinel, and the canonical
        ordering of the pre-existing fields unchanged.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: D\n---\n\n"
            "a:\n"
            "  title: A\n"
            "  communication: true\n"
            "  roles:\n"
            "    - planner\n"
            "  prompt: p\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        text = flow_path.read_text()
        # No new directives authored ⇒ none of the new keys appear.
        assert "auto_approve" not in text
        assert "script_before" not in text
        assert "script_after" not in text
        assert "_approve_directive" not in text
        # ``script:`` only matches the standalone key (no authored script here).
        assert "script:" not in text
        # Byte-exact baseline pinned: interactive (translated) → prompt → agents,
        # agents in flow-style, single trailing newline.
        assert text == (
            "name: T\n"
            "description: D\n"
            "stages:\n"
            "- id: a\n"
            "  name: A\n"
            "  interactive: true\n"
            "  prompt: p\n"
            "  agents: [planning]\n"
        )
