"""Contract and logic tests for the seven compiler-cell dataclass models.

Covers ``PipelineHeader``, ``PhaseStep``, ``StageStep``, ``PhasesBody``,
``StagesBody``, ``FlowStage`` and ``FlowDocument`` — every data model that is
not the ``BodyFormat`` enum.
"""

from __future__ import annotations

import pytest
from goga.pipeline.compiler import (
    FlowDocument,
    FlowStage,
    PhasesBody,
    PhaseStep,
    PipelineHeader,
    StagesBody,
    StageStep,
)


class TestDataModelsContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_all_models_importable_from_facade(self) -> None:
        """Every data model must be importable from the compiler facade."""
        assert PipelineHeader is not None
        assert PhaseStep is not None
        assert StageStep is not None
        assert PhasesBody is not None
        assert StagesBody is not None
        assert FlowStage is not None
        assert FlowDocument is not None

    def test_pipeline_header_constructible_kw_only(self) -> None:
        """PipelineHeader accepts its two required keyword-only fields."""
        header = PipelineHeader(name="Goga feature", description="Feature implementation")

        assert header.name == "Goga feature"
        assert header.description == "Feature implementation"

    def test_phase_step_constructible_kw_only(self) -> None:
        """PhaseStep accepts name, description and the verbatim body dict."""
        step = PhaseStep(name="propose", description="Propose a design", body={"prompt": "draft"})

        assert step.name == "propose"
        assert step.description == "Propose a design"
        assert step.body == {"prompt": "draft"}

    def test_stage_step_constructible_kw_only(self) -> None:
        """StageStep accepts name, description, depends_on and the verbatim body dict."""
        step = StageStep(name="propose", description="Propose", depends_on=None, body={"prompt": "draft"})

        assert step.name == "propose"
        assert step.description == "Propose"
        assert step.depends_on is None
        assert step.body == {"prompt": "draft"}

    def test_phases_body_constructible_kw_only(self) -> None:
        """PhasesBody wraps the ordered list of PhaseStep items."""
        body = PhasesBody(steps=[])

        assert body.steps == []

    def test_stages_body_constructible_kw_only(self) -> None:
        """StagesBody wraps the ordered list of StageStep items."""
        body = StagesBody(steps=[])

        assert body.steps == []

    def test_flow_stage_constructible_kw_only(self) -> None:
        """FlowStage accepts id, name, depends_on and the canonical-order fields dict."""
        stage = FlowStage(id="propose", name="Propose", depends_on=None, fields={"interactive": True})

        assert stage.id == "propose"
        assert stage.name == "Propose"
        assert stage.depends_on is None
        assert stage.fields == {"interactive": True}

    def test_flow_document_constructible_kw_only(self) -> None:
        """FlowDocument accepts the carried name, description and the stages list."""
        doc = FlowDocument(name="Goga feature", description="Feature implementation", stages=[])

        assert doc.name == "Goga feature"
        assert doc.description == "Feature implementation"
        assert doc.stages == []

    @pytest.mark.parametrize(
        "model",
        [
            PipelineHeader,
            PhaseStep,
            StageStep,
            PhasesBody,
            StagesBody,
            FlowStage,
            FlowDocument,
        ],
    )
    def test_keyword_only_enforcement(self, model: type) -> None:
        """Every dataclass field is keyword-only — positional args are rejected."""
        with pytest.raises(TypeError):
            model("x", "y")

    def test_field_types_are_correct(self) -> None:
        """Construct each model and confirm field attribute types."""
        header = PipelineHeader(name="x", description="y")
        assert isinstance(header.name, str)
        assert isinstance(header.description, str)

        phase = PhaseStep(name="a", description="b", body={})
        assert isinstance(phase.name, str)
        assert isinstance(phase.description, str)
        assert isinstance(phase.body, dict)

        stage_step = StageStep(name="a", description="b", depends_on=[], body={})
        assert isinstance(stage_step.depends_on, list)

        phases_body = PhasesBody(steps=[phase])
        assert isinstance(phases_body.steps, list)

        flow_stage = FlowStage(id="a", name="b", depends_on=None, fields={})
        assert isinstance(flow_stage.id, str)
        assert isinstance(flow_stage.name, str)
        assert isinstance(flow_stage.fields, dict)

        doc = FlowDocument(name="a", description="b", stages=[flow_stage])
        assert isinstance(doc.stages, list)


class TestDataModelsLogic:
    """Edge-case / behavior tests."""

    def test_stage_step_tristate_none_vs_empty_distinct(self) -> None:
        """depends_on None and [] are distinct explicit values, preserved on construction."""
        none_step = StageStep(name="a", description="b", depends_on=None, body={})
        empty_step = StageStep(name="a", description="b", depends_on=[], body={})

        assert none_step.depends_on is None
        assert empty_step.depends_on == []
        assert none_step != empty_step

    def test_flow_stage_tristate_none_vs_empty_distinct(self) -> None:
        """depends_on None and [] are distinct explicit values on FlowStage too."""
        none_stage = FlowStage(id="a", name="b", depends_on=None, fields={})
        empty_stage = FlowStage(id="a", name="b", depends_on=[], fields={})

        assert none_stage.depends_on is None
        assert empty_stage.depends_on == []
        assert none_stage != empty_stage

    def test_phase_step_body_retains_arbitrary_keys(self) -> None:
        """The body dict carries verbatim content with no normalization."""
        payload = {"foo": [1, 2, 3], "nested": {"k": "v"}, "agents": ["planning"]}
        step = PhaseStep(name="a", description="b", body=payload)

        assert step.body == payload
        assert step.body["foo"] == [1, 2, 3]

    def test_phases_body_preserves_insertion_order(self) -> None:
        """PhasesBody.steps keeps the order of the source list (3 elements)."""
        steps = [
            PhaseStep(name="a", description="A", body={}),
            PhaseStep(name="b", description="B", body={}),
            PhaseStep(name="c", description="C", body={}),
        ]
        body = PhasesBody(steps=steps)

        assert [s.name for s in body.steps] == ["a", "b", "c"]

    def test_stages_body_preserves_insertion_order(self) -> None:
        """StagesBody.steps keeps the order of the source list too."""
        steps = [
            StageStep(name="a", description="A", depends_on=None, body={}),
            StageStep(name="b", description="B", depends_on=["a"], body={}),
            StageStep(name="c", description="C", depends_on=["b"], body={}),
        ]
        body = StagesBody(steps=steps)

        assert [s.name for s in body.steps] == ["a", "b", "c"]

    def test_flow_stage_fields_retains_insertion_order(self) -> None:
        """FlowStage.fields keeps insertion order — the serializer iterates it as-is."""
        fields = {"interactive": True, "prompt": "x", "agents": ["a"]}
        stage = FlowStage(id="a", name="b", depends_on=None, fields=fields)

        assert list(stage.fields.keys()) == ["interactive", "prompt", "agents"]

    def test_dataclass_equality(self) -> None:
        """Two instances built with equal fields compare equal."""
        left = FlowStage(id="a", name="b", depends_on=None, fields={"x": 1})
        right = FlowStage(id="a", name="b", depends_on=None, fields={"x": 1})

        assert left == right
