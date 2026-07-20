"""Contract and logic tests for the ``PipelineDocument`` dataclass."""

from __future__ import annotations

import dataclasses

import pytest
from goga.pipeline.compiler import (
    BodyFormat,
    PhasesBody,
    PipelineDocument,
    PipelineHeader,
    StagesBody,
    StageStep,
)


class TestPipelineDocumentContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_pipeline_document_importable_from_facade(self) -> None:
        """PipelineDocument must be importable from the compiler facade."""
        assert PipelineDocument is not None

    def test_pipeline_document_field_order_is_fixed(self) -> None:
        """Field order is exactly header, format, body."""
        field_names = [f.name for f in dataclasses.fields(PipelineDocument)]

        assert field_names == ["header", "format", "body"]

    def test_pipeline_document_constructible_with_phases_body(self) -> None:
        """PipelineDocument aggregates header, PHASES format, and a PhasesBody."""
        header = PipelineHeader(name="Goga feature", description="Feature implementation")
        body = PhasesBody(steps=[])

        doc = PipelineDocument(header=header, format=BodyFormat.PHASES, body=body)

        assert doc.header is header
        assert doc.format is BodyFormat.PHASES
        assert doc.body is body

    def test_pipeline_document_constructible_with_stages_body(self) -> None:
        """PipelineDocument aggregates header, STAGES format, and a StagesBody."""
        header = PipelineHeader(name="Goga feature", description="Feature implementation")
        body = StagesBody(steps=[StageStep(name="propose", title="Propose", depends_on=None, body={})])

        doc = PipelineDocument(header=header, format=BodyFormat.STAGES, body=body)

        assert doc.header is header
        assert doc.format is BodyFormat.STAGES
        assert doc.body is body

    def test_all_three_fields_are_required(self) -> None:
        """All three fields are required — no defaults."""
        header = PipelineHeader(name="x", description="y")
        body = PhasesBody(steps=[])

        with pytest.raises(TypeError):
            PipelineDocument(format=BodyFormat.PHASES, body=body)  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            PipelineDocument(header=header, body=body)  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            PipelineDocument(header=header, format=BodyFormat.PHASES)  # type: ignore[call-arg]

    def test_all_fields_are_kw_only(self) -> None:
        """Every field is keyword-only (no positional construction)."""
        header = PipelineHeader(name="x", description="y")

        with pytest.raises(TypeError):
            PipelineDocument(header, BodyFormat.PHASES, PhasesBody(steps=[]))  # type: ignore[misc]


class TestPipelineDocumentLogic:
    """Edge-case / behavior tests."""

    def test_passive_carrier_no_default_for_any_field(self) -> None:
        """No field has a default value — the dataclass is a pure passive carrier."""
        defaults = {
            f.name: f.default for f in dataclasses.fields(PipelineDocument) if f.default is not dataclasses.MISSING
        }

        assert defaults == {}
