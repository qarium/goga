"""Contract and logic tests for the ``serialize_flow`` pure serializer.

Covers the serialization half of the compiler cell: rendering a ``FlowDocument``
into canonical afm flow-file YAML — fixed top-level order (``name``,
``description``, ``stages``), per-stage order (``id``, ``name``, canonical
fields, ``depends_on``), flow-style for ``agents`` (via the ``_FlowAgents``
marker) and block-style for ``skills``/``depends_on``, ending with exactly one
trailing newline. ``serialize_flow`` does not reorder; it assumes the document
is already well-formed.
"""

from __future__ import annotations

import inspect

from goga.pipeline.compiler import FlowDocument, FlowStage, serialize_flow


def _two_stage_document() -> FlowDocument:
    """Build the 2-stage canonical fixture used by the ordering/style tests."""
    return FlowDocument(
        name="Test",
        description="Test description",
        stages=[
            FlowStage(
                id="step-a",
                name="Step A",
                depends_on=None,
                fields={
                    "interactive": True,
                    "prompt": "Do A",
                    "agents": ["planning"],
                    "skills": ["goga-propose"],
                },
            ),
            FlowStage(
                id="step-b",
                name="Step B",
                depends_on=["step-a"],
                fields={
                    "interactive": True,
                    "prompt": "Do B",
                    "agents": ["planning", "implementation"],
                    "skills": ["goga-review"],
                },
            ),
        ],
    )


class TestSerializeFlowContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_serialize_flow_importable_from_facade(self) -> None:
        """``serialize_flow`` must be importable from the facade."""
        assert serialize_flow is not None

    def test_serialize_flow_signature(self) -> None:
        """``serialize_flow`` takes exactly one parameter named ``doc``."""
        parameters = list(inspect.signature(serialize_flow).parameters)

        assert parameters == ["doc"]

    def test_serialize_flow_returns_str_on_minimal_document(self) -> None:
        """A minimal 1-stage ``FlowDocument`` serializes to a ``str``."""
        doc = FlowDocument(
            name="N",
            description="D",
            stages=[
                FlowStage(id="a", name="A", depends_on=None, fields={}),
            ],
        )

        text = serialize_flow(doc)

        assert isinstance(text, str)
        assert text.startswith("name: N\n")


class TestSerializeFlowLogic:
    """Behavioral tests against the documented canonical output format."""

    def test_serialize_flow_canonical_order_and_styles(self) -> None:
        """Per-stage key order is fixed; agents are flow-style; skills/depends_on block-style."""
        text = serialize_flow(_two_stage_document())

        # Top-level shape.
        assert text.startswith("name: Test\n")
        assert "description: Test description" in text
        assert "stages:" in text

        # Stage A — canonical key order: id < name < interactive < prompt < agents < skills.
        idx_id_a = text.index("- id: step-a")
        idx_name_a = text.index("name: Step A")
        idx_interactive_a = text.index("interactive: true")
        idx_prompt_a = text.index("prompt: Do A")
        idx_agents_a = text.index("agents: [planning]")
        idx_skills_a = text.index("skills:")
        assert idx_id_a < idx_name_a < idx_interactive_a < idx_prompt_a
        assert idx_prompt_a < idx_agents_a < idx_skills_a

        # agents in flow-style (not block-style).
        assert "agents: [planning]" in text
        assert "agents: [planning, implementation]" in text

        # skills in block-style (indent=2 per beautiful_yaml).
        assert "skills:\n  - goga-propose" in text

        # depends_on absent for stage A, present in block-style for stage B.
        assert "depends_on:" not in text[: text.index("- id: step-b")]
        assert "depends_on:\n  - step-a" in text

        # Exactly one trailing newline.
        assert text.endswith("\n")
        assert not text.endswith("\n\n")

    def test_serialize_flow_explicit_empty_depends_on_emitted(self) -> None:
        """An explicit empty list produces ``depends_on: []`` (distinguished from absent)."""
        doc = FlowDocument(
            name="T",
            description="D",
            stages=[
                FlowStage(id="a", name="A", depends_on=[], fields={}),
            ],
        )

        text = serialize_flow(doc)

        assert "depends_on: []" in text

    def test_serialize_flow_absent_depends_on_omitted(self) -> None:
        """A ``None`` depends_on produces no depends_on key at all."""
        doc = FlowDocument(
            name="T",
            description="D",
            stages=[
                FlowStage(id="a", name="A", depends_on=None, fields={}),
            ],
        )

        text = serialize_flow(doc)

        assert "depends_on" not in text

    def test_serialize_flow_round_trips_through_safe_load(self) -> None:
        """Serialized output parses back to an equivalent data structure."""
        import yaml

        doc = _two_stage_document()
        text = serialize_flow(doc)
        loaded = yaml.safe_load(text)

        assert loaded["name"] == "Test"
        assert loaded["description"] == "Test description"
        assert len(loaded["stages"]) == 2
        assert loaded["stages"][0]["id"] == "step-a"
        assert loaded["stages"][0]["agents"] == ["planning"]
        # No depends_on key for stage A (None).
        assert "depends_on" not in loaded["stages"][0]
        assert loaded["stages"][1]["depends_on"] == ["step-a"]
