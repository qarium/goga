"""Contract tests for the ``FlowMemory`` dataclass.

Verifies the public API declared by the compiler-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the five
declared properties, the fixed field order (the emission order of the block
keys), kw_only construction, and the no-default pins of the three required
fields (``path`` / ``max_rules`` / ``commit`` — only ``compile_flow`` builds
this type). These tests pin the contract surface — behavior lives in the
logic test module.
"""

from __future__ import annotations

from dataclasses import fields

import pytest
from goga.pipeline.compiler import FlowMemory


class TestFlowMemoryContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_flow_memory_importable_from_facade(self) -> None:
        """FlowMemory is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.compiler as facade

        assert facade.FlowMemory is FlowMemory
        assert "FlowMemory" in facade.__all__

    def test_flow_memory_has_path_property(self) -> None:
        """FlowMemory exposes a ``path`` property."""
        assert hasattr(FlowMemory(path=".goga/memory", max_rules=25, commit=False), "path")
        assert FlowMemory(path=".goga/memory/x", max_rules=25, commit=False).path == ".goga/memory/x"

    def test_flow_memory_has_mode_property(self) -> None:
        """FlowMemory exposes a ``mode`` property defaulting to None."""
        assert hasattr(FlowMemory(path=".goga/memory", max_rules=25, commit=False), "mode")
        block = FlowMemory(path=".goga/memory", max_rules=25, commit=False)
        assert block.mode is None
        assert FlowMemory(path=".goga/memory", mode="rw", max_rules=25, commit=False).mode == "rw"

    def test_flow_memory_has_memory_use_property(self) -> None:
        """FlowMemory exposes a ``memory_use`` property defaulting to None."""
        assert hasattr(FlowMemory(path=".goga/memory", max_rules=25, commit=False), "memory_use")
        block = FlowMemory(path=".goga/memory", max_rules=25, commit=False)
        assert block.memory_use is None
        assert FlowMemory(path=".goga/memory", memory_use=True, max_rules=25, commit=False).memory_use is True

    def test_flow_memory_has_max_rules_property(self) -> None:
        """FlowMemory exposes a ``max_rules`` property."""
        assert hasattr(FlowMemory(path=".goga/memory", max_rules=25, commit=False), "max_rules")
        assert FlowMemory(path=".goga/memory", max_rules=40, commit=False).max_rules == 40

    def test_flow_memory_has_commit_property(self) -> None:
        """FlowMemory exposes a ``commit`` property."""
        assert hasattr(FlowMemory(path=".goga/memory", max_rules=25, commit=False), "commit")
        assert FlowMemory(path=".goga/memory", max_rules=25, commit=True).commit is True

    def test_flow_memory_field_order_fixed(self) -> None:
        """Field order is fixed: path, mode, memory_use, max_rules, commit."""
        names = [field.name for field in fields(FlowMemory)]

        assert names == ["path", "mode", "memory_use", "max_rules", "commit"]

    def test_flow_memory_constructible_kw_only(self) -> None:
        """FlowMemory is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            FlowMemory(".goga/memory", None, None, 25, False)  # type: ignore[misc]

    def test_flow_memory_required_fields_have_no_defaults(self) -> None:
        """Only ``mode`` / ``memory_use`` default — every other field is required.

        ``path`` / ``max_rules`` / ``commit`` carry NO defaults: a block is
        always complete (``compile_flow`` is the single construction site, and
        a silently-defaulted field would fabricate emission values).
        """
        with pytest.raises(TypeError):
            FlowMemory()  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            FlowMemory(path=".goga/memory")  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            FlowMemory(path=".goga/memory", max_rules=25)  # type: ignore[call-arg]
