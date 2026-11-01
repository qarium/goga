"""Contract tests for the ``FlowDocument`` slot extensions.

Covers the Task 5 data-model extension: ``FlowDocument`` gains an optional
``prompt: str | None`` field as its FIRST slot (default ``None``), emitted as
the first top-level key by ``serialize_flow`` when not ``None`` and omitted
entirely when ``None``. Because the dataclass is ``kw_only=True``, the new
first-slot field with a default does not break existing keyword construction
sites.

Also covers the memory-slot extension: ``FlowDocument`` gains an optional
``memory: FlowMemory | None`` field between ``description`` and ``stages``
(default ``None``), emitted between the two by ``serialize_flow`` when not
``None`` and omitted entirely when ``None`` — the byte-identity default for
memory-free workflows.

Also covers the collaboration-slot extension: ``FlowDocument`` gains the
optional ``collaboration: FlowCollaboration | None`` and
``team: list[FlowTeamMember] | None`` fields between ``memory`` and
``stages`` (both default ``None``) — the canonical top-level emission order
of the collaboration block and the team list.
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields

from goga.pipeline.compiler import FlowCollaboration, FlowDocument, FlowMemory, FlowStage, FlowTeamMember


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


class TestFlowDocumentMemoryContract:
    """Contract tests — the ``memory`` slot declared by the CODEMANIFEST."""

    def test_flow_document_has_memory_field(self) -> None:
        """``FlowDocument`` must declare a ``memory`` field."""
        names = [f.name for f in dataclass_fields(FlowDocument)]

        assert "memory" in names

    def test_flow_document_field_order_with_memory_slot(self) -> None:
        """The fixed field order is prompt, root_dir, name, description, memory, collaboration, team, stages.

        The order matches the canonical emission order in ``serialize_flow`` —
        the memory block sits strictly between ``description`` and the
        collaboration block; the team list sits strictly between the
        collaboration block and ``stages``.
        """
        ordered = [f.name for f in dataclass_fields(FlowDocument)]

        assert ordered == [
            "prompt",
            "root_dir",
            "name",
            "description",
            "memory",
            "collaboration",
            "team",
            "stages",
        ]
        assert ordered[4] == "memory"
        assert ordered[5] == "collaboration"
        assert ordered[6] == "team"
        assert ordered[7] == "stages"

    def test_flow_document_memory_type_is_optional_flow_memory(self) -> None:
        """``memory`` must be typed ``FlowMemory | None``."""
        memory_field = next(f for f in dataclass_fields(FlowDocument) if f.name == "memory")

        assert memory_field.type == "FlowMemory | None"

    def test_flow_document_memory_defaults_to_none(self) -> None:
        """A ``FlowDocument`` built without ``memory`` has ``memory=None``.

        The default is the byte-identity pin — a document without memory
        serializes without the block entirely.
        """
        doc = FlowDocument(name="N", description="D", stages=[])

        assert doc.memory is None

    def test_flow_document_round_trips_with_memory(self) -> None:
        """An explicit ``FlowMemory`` round-trips through construction verbatim."""
        stage = FlowStage(id="a", name="A", depends_on=None, fields={})
        block = FlowMemory(path=".goga/memory/x", mode="rw", memory_use=True, max_rules=25, commit=False)
        doc = FlowDocument(name="N", description="D", memory=block, stages=[stage])

        assert doc.memory is block
        assert doc.name == "N"
        assert doc.description == "D"
        assert doc.stages == [stage]


class TestFlowDocumentCollaborationContract:
    """Contract tests — the ``collaboration`` and ``team`` slots declared by the CODEMANIFEST."""

    def test_flow_document_has_collaboration_and_team_fields(self) -> None:
        """``FlowDocument`` must declare both new fields."""
        names = [f.name for f in dataclass_fields(FlowDocument)]

        assert "collaboration" in names
        assert "team" in names

    def test_flow_document_collaboration_type_is_optional_flow_collaboration(self) -> None:
        """``collaboration`` must be typed ``FlowCollaboration | None``."""
        collaboration_field = next(f for f in dataclass_fields(FlowDocument) if f.name == "collaboration")

        assert collaboration_field.type == "FlowCollaboration | None"

    def test_flow_document_team_type_is_optional_member_list(self) -> None:
        """``team`` must be typed ``list[FlowTeamMember] | None``."""
        team_field = next(f for f in dataclass_fields(FlowDocument) if f.name == "team")

        assert team_field.type == "list[FlowTeamMember] | None"

    def test_flow_document_collaboration_and_team_default_to_none(self) -> None:
        """A ``FlowDocument`` built without the new slots carries ``None``/``None``.

        The defaults are the omission pins — a document without collaboration
        slots serializes without those keys entirely (the byte-identity
        default for collaboration-free hand-built documents).
        """
        doc = FlowDocument(name="N", description="D", stages=[])

        assert doc.collaboration is None
        assert doc.team is None

    def test_flow_document_round_trips_with_collaboration_and_team(self) -> None:
        """Explicit collaboration and team values round-trip through construction."""
        stage = FlowStage(id="a", name="A", depends_on=None, fields={})
        block = FlowCollaboration(mode="assistants", max_depth=2)
        members = [
            FlowTeamMember(id="reviewer", title="reviewer", profile="goga-reviewer", instruction="Review.", skills=[]),
        ]
        doc = FlowDocument(name="N", description="D", collaboration=block, team=members, stages=[stage])

        assert doc.collaboration is block
        assert doc.team is members
        assert doc.stages == [stage]

    def test_existing_construction_sites_without_collaboration_still_work(self) -> None:
        """Pre-existing kw_only construction without the new slots is unaffected."""
        doc = FlowDocument(name="Goga feature", description="Feature implementation", stages=[])

        assert doc.name == "Goga feature"
        assert doc.description == "Feature implementation"
        assert doc.stages == []
        assert doc.collaboration is None
        assert doc.team is None
