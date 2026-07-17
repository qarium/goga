"""Contract tests for the ``FlowDocument.prompt`` first-slot extension.

Covers the Task 5 data-model extension: ``FlowDocument`` gains an optional
``prompt: str | None`` field as its FIRST slot (default ``None``), emitted as
the first top-level key by ``serialize_flow`` when not ``None`` and omitted
entirely when ``None``. Because the dataclass is ``kw_only=True``, the new
first-slot field with a default does not break existing keyword construction
sites.
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields

from goga.pipeline.compiler import FlowDocument, FlowStage


class TestFlowDocumentPromptContract:
    """Contract tests — the ``prompt`` first-slot declared by the CODEMANIFEST."""

    def test_flow_document_has_prompt_field(self) -> None:
        """``FlowDocument`` must declare a ``prompt`` field."""
        names = [f.name for f in dataclass_fields(FlowDocument)]

        assert "prompt" in names

    def test_flow_document_prompt_is_first_slot(self) -> None:
        """``prompt`` must be the FIRST field of ``FlowDocument``."""
        first = dataclass_fields(FlowDocument)[0]

        assert first.name == "prompt"

    def test_flow_document_prompt_type_is_optional_str(self) -> None:
        """``prompt`` must be typed ``str | None``."""
        prompt_field = next(f for f in dataclass_fields(FlowDocument) if f.name == "prompt")

        assert prompt_field.type == "str | None"

    def test_flow_document_prompt_defaults_to_none(self) -> None:
        """A ``FlowDocument`` built without ``prompt`` has ``prompt=None``."""
        doc = FlowDocument(name="N", description="D", stages=[])

        assert doc.prompt is None

    def test_flow_document_round_trips_with_prompt(self) -> None:
        """Explicit ``prompt`` round-trips through construction alongside the other fields."""
        stage = FlowStage(id="a", name="A", depends_on=None, fields={})
        doc = FlowDocument(prompt="Top-level prompt", name="N", description="D", stages=[stage])

        assert doc.prompt == "Top-level prompt"
        assert doc.name == "N"
        assert doc.description == "D"
        assert doc.stages == [stage]

    def test_existing_construction_sites_without_prompt_still_work(self) -> None:
        """Pre-existing kw_only construction without ``prompt`` is unaffected."""
        doc = FlowDocument(name="Goga feature", description="Feature implementation", stages=[])

        # The carried fields are intact; prompt falls back to its default.
        assert doc.name == "Goga feature"
        assert doc.description == "Feature implementation"
        assert doc.stages == []
        assert doc.prompt is None
