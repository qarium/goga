"""Logic tests for the top-level ``repeat`` slot + ``serialize_flow`` emission.

Covers the repeat serializer arm: a non-``None`` ``FlowDocument.repeat`` is
emitted between ``description`` and ``memory`` — an instance carrying no
authored key is the scalar form (written ``repeat: true``); otherwise a
block-style mapping of the authored keys in the fixed order ``max_cycles,
keep_runs`` (present keys only, plain scalars). A ``None`` repeat omits the
key entirely — byte-identical output for non-repeatable pipelines. No new
``_CanonicalDumper`` representer: the plain ``bool`` / dict-of-ints emission
rides the ``beautiful_yaml`` defaults exactly as the memory block does.
"""

from __future__ import annotations

from goga.pipeline.compiler import FlowDocument, FlowMemory, FlowRepeat, FlowStage, serialize_flow


def _stage(stage_id: str, name: str) -> FlowStage:
    """Build one minimal ``FlowStage`` (mirrors the compile output shape)."""
    return FlowStage(id=stage_id, name=name, depends_on=None, fields={"prompt": "Do"})


class TestSerializeFlowRepeatForms:
    """Behavioral tests for the three serializer arms (omitted / scalar / block)."""

    def test_serialize_flow_repeat_none_omits_key(self) -> None:
        """A ``None`` repeat produces no top-level ``repeat`` key at all."""
        doc = FlowDocument(name="n", description="d", repeat=None, stages=[_stage("a", "A")])

        text = serialize_flow(doc)

        assert "repeat" not in text

    def test_serialize_flow_repeat_scalar_form(self) -> None:
        """A directive carrying no authored key writes the scalar ``repeat: true``."""
        doc = FlowDocument(name="n", description="d", repeat=FlowRepeat(), stages=[_stage("a", "A")])

        text = serialize_flow(doc)

        assert "\nrepeat: true\n" in text

    def test_serialize_flow_repeat_block_form_present_keys_only(self) -> None:
        """A directive carrying one authored key writes the block map with that key only."""
        doc = FlowDocument(name="n", description="d", repeat=FlowRepeat(max_cycles=3), stages=[_stage("a", "A")])

        text = serialize_flow(doc)

        assert "repeat:\n  max_cycles: 3\n" in text
        assert "keep_runs" not in text

    def test_serialize_flow_repeat_block_form_fixed_key_order(self) -> None:
        """Both authored keys write in the fixed order max_cycles, keep_runs."""
        doc = FlowDocument(
            name="n",
            description="d",
            repeat=FlowRepeat(max_cycles=3, keep_runs=5),
            stages=[_stage("a", "A")],
        )

        text = serialize_flow(doc)

        assert "repeat:\n  max_cycles: 3\n  keep_runs: 5\n" in text

    def test_serialize_flow_repeat_block_form_zero_is_written(self) -> None:
        """An authored zero is a value — it is written, never dropped."""
        doc = FlowDocument(name="n", description="d", repeat=FlowRepeat(keep_runs=0), stages=[_stage("a", "A")])

        text = serialize_flow(doc)

        assert "repeat:\n  keep_runs: 0\n" in text
        assert "max_cycles" not in text

    def test_serialize_flow_repeat_position_between_description_and_memory(self) -> None:
        """The directive sits between ``description`` and the memory block."""
        doc = FlowDocument(
            name="n",
            description="d",
            repeat=FlowRepeat(max_cycles=2),
            memory=FlowMemory(path=".goga/memory", max_rules=25, commit=False),
            stages=[_stage("a", "A")],
        )

        text = serialize_flow(doc)

        assert text.index("description:") < text.index("repeat:") < text.index("memory:")

    def test_serialize_flow_repeat_block_is_plain_scalars(self) -> None:
        """The block values render as plain int scalars (no quoting, no flow style)."""
        doc = FlowDocument(
            name="n",
            description="d",
            repeat=FlowRepeat(max_cycles=3, keep_runs=5),
            stages=[_stage("a", "A")],
        )

        text = serialize_flow(doc)

        assert "max_cycles: 3" in text
        assert "max_cycles: '3'" not in text
        assert "repeat: {max_cycles" not in text

    def test_serialize_flow_repeat_after_root_dir_and_prompt(self) -> None:
        """The directive keeps its slot when ``prompt``/``root_dir`` are present."""
        doc = FlowDocument(
            prompt="Top",
            root_dir="/workspace",
            name="n",
            description="d",
            repeat=FlowRepeat(),
            stages=[_stage("a", "A")],
        )

        text = serialize_flow(doc)

        assert text.index("root_dir:") < text.index("name:") < text.index("repeat:")
