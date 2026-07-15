"""Contract and logic tests for the ``BodyFormat`` str-backed enum."""

from __future__ import annotations

import pytest
from goga.pipeline.compiler import BodyFormat


class TestBodyFormatContract:
    """Contract tests — the public API declared by the compiler-cell CODEMANIFEST."""

    def test_body_format_importable_from_facade(self) -> None:
        """BodyFormat must be importable from the compiler facade."""
        assert BodyFormat is not None

    @pytest.mark.parametrize(
        ("member", "value"),
        [
            (BodyFormat.PHASES, "phases"),
            (BodyFormat.STAGES, "stages"),
        ],
    )
    def test_member_values(self, member: BodyFormat, value: str) -> None:
        """Each member must serialize to its plain string value."""
        assert member.value == value

    def test_phases_value(self) -> None:
        """PHASES serializes to the plain string ``"phases"``."""
        assert BodyFormat.PHASES.value == "phases"

    def test_stages_value(self) -> None:
        """STAGES serializes to the plain string ``"stages"``."""
        assert BodyFormat.STAGES.value == "stages"

    def test_str_mixin(self) -> None:
        """Members are plain strings thanks to the ``str`` mixin."""
        assert isinstance(BodyFormat.PHASES, str)
        assert isinstance(BodyFormat.STAGES, str)

    @pytest.mark.parametrize(
        ("raw", "member"),
        [
            ("phases", BodyFormat.PHASES),
            ("stages", BodyFormat.STAGES),
        ],
    )
    def test_value_of_constructor(self, raw: str, member: BodyFormat) -> None:
        """``BodyFormat(value)`` resolves the member by value."""
        assert BodyFormat(raw) == member


class TestBodyFormatLogic:
    """Edge-case / behavior tests."""

    def test_invalid_value_raises_value_error(self) -> None:
        """An unknown value must raise ``ValueError`` from the value-of constructor."""
        with pytest.raises(ValueError, match="invalid"):
            BodyFormat("invalid")

    def test_iteration_yields_two_members_in_declaration_order(self) -> None:
        """Iterating yields exactly the two members in declaration order."""
        members = list(BodyFormat)

        assert members == [BodyFormat.PHASES, BodyFormat.STAGES]
        assert len(members) == 2
