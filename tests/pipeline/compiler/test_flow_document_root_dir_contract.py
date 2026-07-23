"""Contract tests for the ``FlowDocument.root_dir`` slot extension.

Covers the ``root_dir`` data-model extension: ``FlowDocument`` gains an optional
``root_dir: str | None`` field as its SECOND slot (immediately after ``prompt``,
before ``name``), emitted as a top-level key by ``serialize_flow`` when not
``None`` and omitted entirely when ``None``. Because the dataclass is
``kw_only=True``, the new slot with a default does not break existing keyword
construction sites.
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields

from goga.pipeline.compiler import FlowDocument, FlowStage


class TestFlowDocumentRootDirContract:
    """Contract tests — the ``root_dir`` slot declared by the CODEMANIFEST."""

    def test_flow_document_has_root_dir_field(self) -> None:
        """The ``FlowDocument`` class must declare a ``root_dir`` field."""
        names = [f.name for f in dataclass_fields(FlowDocument)]

        assert "root_dir" in names

    def test_flow_document_root_dir_is_second_slot(self) -> None:
        """The ``root_dir`` field must be the SECOND field of ``FlowDocument`` (after ``prompt``)."""
        ordered = [f.name for f in dataclass_fields(FlowDocument)]

        assert ordered[0] == "prompt"
        assert ordered[1] == "root_dir"
        assert ordered[2] == "name"

    def test_flow_document_root_dir_type_is_optional_str(self) -> None:
        """The ``root_dir`` field must be typed ``str | None``."""
        root_dir_field = next(f for f in dataclass_fields(FlowDocument) if f.name == "root_dir")

        assert root_dir_field.type == "str | None"

    def test_flow_document_root_dir_defaults_to_none(self) -> None:
        """A ``FlowDocument`` built without ``root_dir`` has ``root_dir=None``."""
        doc = FlowDocument(name="N", description="D", stages=[])

        assert doc.root_dir is None

    def test_flow_document_round_trips_with_root_dir(self) -> None:
        """Explicit ``root_dir`` round-trips through construction alongside the other fields."""
        stage = FlowStage(id="a", name="A", depends_on=None, fields={})
        doc = FlowDocument(root_dir="/workspace", name="N", description="D", stages=[stage])

        assert doc.root_dir == "/workspace"
        assert doc.name == "N"
        assert doc.description == "D"
        assert doc.stages == [stage]

    def test_existing_construction_sites_without_root_dir_still_work(self) -> None:
        """Pre-existing kw_only construction without ``root_dir`` is unaffected."""
        doc = FlowDocument(name="Goga feature", description="Feature implementation", stages=[])

        # The carried fields are intact; root_dir falls back to its default.
        assert doc.name == "Goga feature"
        assert doc.description == "Feature implementation"
        assert doc.stages == []
        assert doc.root_dir is None

    def test_flow_document_carries_both_prompt_and_root_dir(self) -> None:
        """Both ``prompt`` and ``root_dir`` may be set simultaneously without collision."""
        doc = FlowDocument(
            prompt="Top-level workflow prompt",
            root_dir="/workspace",
            name="N",
            description="D",
            stages=[],
        )

        assert doc.prompt == "Top-level workflow prompt"
        assert doc.root_dir == "/workspace"
