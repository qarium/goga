"""Logic tests for the ``FlowMemory`` dataclass.

Covers construction behavior beyond the contract surface: the emission-order
pin of the field list and the two method shapes — the reflect-method block
(``mode: r`` / ``memory_use: False``) versus the alignment-method block
(``mode`` the materialized authored value, ``memory_use`` ``False``). The
``None`` fields are the omission signal the serializer drops — a block must
never conflate an unset field with an authored value.
"""

from __future__ import annotations

from dataclasses import fields

from goga.pipeline.compiler import FlowMemory


class TestFlowMemoryLogic:
    """Logic tests — construction behavior of the ``FlowMemory`` dataclass."""

    def test_flow_memory_field_order_is_emission_order(self) -> None:
        """Field order equals the emission order of the block keys.

        ``serialize_flow`` reads the block in this order (path, mode,
        memory_use, max_rules, commit) — a reorder of the dataclass fields
        would silently shift the compiled output.
        """
        names = [field.name for field in fields(FlowMemory)]

        assert names == ["path", "mode", "memory_use", "max_rules", "commit"]

    def test_flow_memory_none_fields_distinct_from_values(self) -> None:
        """The reflect shape carries ``mode: r``/``memory_use: False``; alignment the authored mode.

        A reflect-method block is the shape the compiler builds from a bare
        reflect configuration — the fixed ``mode: r`` and the global opt-out
        ``memory_use: False`` (read-only project memory, no global
        participation). The alignment-method block carries the materialized
        authored mode (``rw`` by default) and the same global
        ``memory_use: False`` — participation is per-stage opt-in. The model's
        ``None`` defaults remain the omission signal for the serializer — a
        block must never conflate an unset field with an authored value.
        """
        reflect_block = FlowMemory(path=".goga/memory", mode="r", memory_use=False, max_rules=25, commit=False)

        assert reflect_block.mode == "r"
        assert reflect_block.memory_use is False
        assert reflect_block.path == ".goga/memory"
        assert reflect_block.max_rules == 25
        assert reflect_block.commit is False

        alignment_block = FlowMemory(
            path=".goga/memory/goga-development",
            mode="rw",
            memory_use=False,
            max_rules=25,
            commit=False,
        )

        assert alignment_block.mode == "rw"
        assert alignment_block.memory_use is False
        assert alignment_block.path == ".goga/memory/goga-development"

    def test_flow_memory_equality_of_identical_constructions(self) -> None:
        """Two blocks with identical fields compare equal (dataclass equality)."""
        left = FlowMemory(path=".goga/memory", max_rules=25, commit=False)
        right = FlowMemory(
            path=".goga/memory", mode=None, memory_use=None, max_rules=25, commit=False
        )

        assert left == right
