"""Contract tests for the ``ResolvedProfile`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the three
declared properties (``name``, ``data``, ``source``), kw_only construction, and
frozen immutability. These tests pin the contract surface — behavior lives in
the logic test module.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest
from goga.pipeline.workflow import ProfileSource, ResolvedProfile


class TestResolvedProfileContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_resolved_profile_importable_from_facade(self) -> None:
        """ResolvedProfile is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.ResolvedProfile is ResolvedProfile
        assert "ResolvedProfile" in facade.__all__

    def test_resolved_profile_has_name_property(self) -> None:
        """ResolvedProfile exposes a ``name`` property."""
        profile = ResolvedProfile(name="mixa", data={}, source=ProfileSource.PROJECT)

        assert hasattr(profile, "name")
        assert profile.name == "mixa"

    def test_resolved_profile_has_data_property(self) -> None:
        """ResolvedProfile exposes a ``data`` property."""
        profile = ResolvedProfile(name="mixa", data={"worker": {"agent": "codex"}}, source=ProfileSource.HOME)

        assert hasattr(profile, "data")
        assert profile.data == {"worker": {"agent": "codex"}}

    def test_resolved_profile_has_source_property(self) -> None:
        """ResolvedProfile exposes a ``source`` property carrying a ProfileSource."""
        profile = ResolvedProfile(name="mixa", data={}, source=ProfileSource.HOME)

        assert hasattr(profile, "source")
        assert profile.source is ProfileSource.HOME

    def test_resolved_profile_field_order_fixed(self) -> None:
        """Field order is fixed: name, data, source."""
        names = [field.name for field in fields(ResolvedProfile)]

        assert names == ["name", "data", "source"]

    def test_resolved_profile_constructible_kw_only(self) -> None:
        """ResolvedProfile is keyword-only — positional construction raises TypeError."""
        with pytest.raises(TypeError):
            ResolvedProfile("mixa", {}, ProfileSource.PROJECT)  # type: ignore[misc]

    def test_resolved_profile_frozen_immutable(self) -> None:
        """ResolvedProfile is frozen — field assignment raises FrozenInstanceError."""
        profile = ResolvedProfile(name="mixa", data={}, source=ProfileSource.PROJECT)

        with pytest.raises(FrozenInstanceError):
            profile.name = "other"  # type: ignore[misc]
