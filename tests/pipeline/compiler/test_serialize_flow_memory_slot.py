"""Logic tests for the top-level ``memory`` slot + ``serialize_flow`` emission.

Covers the memory serializer extension: a non-``None`` ``FlowDocument.memory``
is emitted between ``description`` and ``stages`` with the fixed key order
``path, mode, memory_use, max_rules, commit`` and a ``None`` field omitted
entirely; a ``None`` memory omits the block entirely — byte-identical output
for memory-free workflows. The per-stage memory keys (``reflect`` mapping,
``memory_use`` bool) ride the existing ``fields`` passthrough: a dict renders
block-style under the default ``beautiful_yaml`` parameters, a bool renders as
a plain scalar — no representer and no ``_build_stage_repr`` change.
"""

from __future__ import annotations

from goga.pipeline.compiler import FlowDocument, FlowMemory, FlowStage, serialize_flow

# Golden byte-identity literal for a memory-free document — frozen from the
# serializer output BEFORE the memory branch existed. Any leak of memory into
# the output (a block, a stage key, a key-order shift) changes this string.
MEMORY_FREE_GOLDEN = (
    "name: demo\n"
    "description: Demo pipeline\n"
    "stages:\n"
    "- id: brainstorm\n"
    "  name: Brainstorm\n"
    "  agents: [auto]\n"
    "  prompt: Think\n"
    "- id: build\n"
    "  name: Build\n"
    "  agents: [auto]\n"
    "  prompt: Make\n"
    "  depends_on:\n"
    "  - brainstorm\n"
)


def _stage(id: str, name: str, fields: dict[str, object], depends_on: list[str] | None = None) -> FlowStage:
    """Build one ``FlowStage`` with the given fields (mirrors the compile output shape)."""
    return FlowStage(id=id, name=name, depends_on=depends_on, fields=fields)


class TestSerializeFlowMemoryBlock:
    """Behavioral tests for the top-level memory block emission rules."""

    def test_serialize_flow_memory_block_position_and_key_order(self) -> None:
        """The block sits between ``description`` and ``stages`` with fixed key order, plain scalars."""
        doc = FlowDocument(
            name="n",
            description="d",
            memory=FlowMemory(
                path=".goga/memory/x",
                mode="rw",
                memory_use=True,
                max_rules=25,
                commit=False,
            ),
            stages=[_stage("a", "A", {"prompt": "Do"})],
        )

        text = serialize_flow(doc)

        # Position: description < memory < stages.
        idx_description = text.index("description:")
        idx_memory = text.index("memory:")
        idx_stages = text.index("stages:")
        assert idx_description < idx_memory < idx_stages
        # In-block key order: path < mode < memory_use < max_rules < commit.
        idx_path = text.index("path: .goga/memory/x")
        idx_mode = text.index("mode: rw")
        idx_use = text.index("memory_use: true")
        idx_max = text.index("max_rules: 25")
        idx_commit = text.index("commit: false")
        assert idx_memory < idx_path < idx_mode < idx_use < idx_max < idx_commit
        assert idx_commit < idx_stages
        # The exact block literal — every value a plain scalar, 2-space indent
        # (beautiful_yaml indent=2; the nested stage keys sit at 4, not 2).
        assert (
            "memory:\n"
            "  path: .goga/memory/x\n"
            "  mode: rw\n"
            "  memory_use: true\n"
            "  max_rules: 25\n"
            "  commit: false\n"
        ) in text

    def test_serialize_flow_none_fields_omitted_from_block(self) -> None:
        """A ``None`` field is omitted entirely — the reflect-method block carries exactly path/max_rules/commit."""
        doc = FlowDocument(
            name="n",
            description="d",
            memory=FlowMemory(path=".goga/memory", max_rules=9, commit=True),
            stages=[_stage("a", "A", {"prompt": "Do"})],
        )

        text = serialize_flow(doc)

        block_text = text[text.index("memory:") : text.index("stages:")]
        assert "path: .goga/memory" in block_text
        assert "max_rules: 9" in block_text
        assert "commit: true" in text
        assert "commit: true" in block_text
        # None fields never reach the output — no key at all, not an empty value.
        assert "mode:" not in block_text
        assert "memory_use:" not in block_text

    def test_serialize_flow_document_without_memory_omits_block(self) -> None:
        """A ``None`` memory produces no top-level ``memory:`` key at all."""
        doc = FlowDocument(name="n", description="d", memory=None, stages=[_stage("a", "A", {})])

        text = serialize_flow(doc)

        assert "memory:" not in text
        assert "memory" not in text


class TestSerializeFlowStageMemoryKeys:
    """Behavioral tests for the per-stage memory keys riding the ``fields`` passthrough."""

    def test_serialize_flow_reflect_is_block_style_mapping(self) -> None:
        """A stage ``reflect`` dict renders block-style (4-space nested keys) without any block emitted."""
        doc = FlowDocument(
            name="n",
            description="d",
            stages=[_stage("s", "S", {"reflect": {"file": "shared.md", "mode": "rw"}})],
        )

        text = serialize_flow(doc)

        assert "reflect:" in text
        assert "file: shared.md" in text
        assert "mode: rw" in text
        # Block-style, not flow-style.
        assert "reflect: {file" not in text
        # The nested keys sit at 4 spaces — the second level under ``stages``.
        assert "    file: shared.md" in text
        assert "    mode: rw" in text
        # No block emitted -> no stage carries an opting-out key.
        assert "memory_use: false" not in text
        assert "memory:" not in text

    def test_serialize_flow_memory_use_is_plain_bool_scalar(self) -> None:
        """A stage ``memory_use`` bool renders as a plain scalar (true/false, unquoted, not block)."""
        doc = FlowDocument(
            name="n",
            description="d",
            stages=[
                _stage("s", "S", {"memory_use": True}),
                _stage("t", "T", {"memory_use": False}),
            ],
        )

        text = serialize_flow(doc)

        assert "memory_use: true" in text
        assert "memory_use: false" in text
        assert "memory_use: 'true'" not in text
        assert "memory_use: |" not in text


class TestSerializeFlowMemoryFreeByteIdentity:
    """The byte-identity barrier: a memory-free document serializes unchanged."""

    def test_serialize_flow_memory_free_document_is_byte_identical(self) -> None:
        """A document without memory serializes to the frozen pre-change golden, byte for byte."""
        doc = FlowDocument(
            name="demo",
            description="Demo pipeline",
            memory=None,
            stages=[
                _stage("brainstorm", "Brainstorm", {"agents": ["auto"], "prompt": "Think"}),
                _stage(
                    "build",
                    "Build",
                    {"agents": ["auto"], "prompt": "Make"},
                    depends_on=["brainstorm"],
                ),
            ],
        )

        text = serialize_flow(doc)

        assert text == MEMORY_FREE_GOLDEN
        # No memory key anywhere — top level or stage level.
        assert "memory" not in text
        assert "reflect" not in text
