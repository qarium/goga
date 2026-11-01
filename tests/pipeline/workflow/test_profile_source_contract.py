"""Contract tests for the ``ProfileSource`` enum.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade (including the ``__all__`` obligation), the two
declared members with their exact str values, and the str mixin (values
serialize as plain strings). These tests pin the contract surface — behavior
lives in the logic test module.
"""

from __future__ import annotations

from goga.pipeline.workflow import ProfileSource


class TestProfileSourceContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_profile_source_importable_from_facade(self) -> None:
        """ProfileSource is importable from the facade and listed in ``__all__``."""
        import goga.pipeline.workflow as facade

        assert facade.ProfileSource is ProfileSource
        assert "ProfileSource" in facade.__all__

    def test_profile_source_project_member_value(self) -> None:
        """ProfileSource.PROJECT carries the declared value "project"."""
        assert ProfileSource.PROJECT.value == "project"

    def test_profile_source_home_member_value(self) -> None:
        """ProfileSource.HOME carries the declared value "home"."""
        assert ProfileSource.HOME.value == "home"

    def test_profile_source_str_backed(self) -> None:
        """ProfileSource mixes in str — every member IS a plain string value."""
        assert isinstance(ProfileSource.PROJECT, str)
        assert isinstance(ProfileSource.HOME, str)

    def test_profile_source_member_set_exact(self) -> None:
        """The enum declares exactly the two members PROJECT and HOME."""
        assert {member.name for member in ProfileSource} == {"PROJECT", "HOME"}
        assert len(ProfileSource) == 2
