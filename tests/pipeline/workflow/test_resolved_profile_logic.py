"""Logic tests for the ``ResolvedProfile`` dataclass.

Covers behavior beyond the contract surface: the ``data`` mapping carried
verbatim (arbitrary nested content), the two sources, and value equality.
"""

from __future__ import annotations

from goga.pipeline.workflow import ProfileSource, ResolvedProfile


class TestResolvedProfileLogic:
    """Logic tests — value carriage of the ``ResolvedProfile`` dataclass."""

    def test_data_carries_arbitrary_mapping_verbatim(self) -> None:
        """``data`` carries an arbitrary mapping verbatim — the same object, nested content intact."""
        payload = {
            "worker": {"agent": "codex", "model": "sonnet"},
            "hardening": True,
            "limits": [1, 2, 3],
            "note": "текст",
        }
        profile = ResolvedProfile(name="mixa", data=payload, source=ProfileSource.PROJECT)

        assert profile.data is payload
        assert profile.data == {
            "worker": {"agent": "codex", "model": "sonnet"},
            "hardening": True,
            "limits": [1, 2, 3],
            "note": "текст",
        }

    def test_data_empty_mapping_carried_verbatim(self) -> None:
        """An empty ``data`` mapping is a valid value (a profile file with an empty root)."""
        profile = ResolvedProfile(name="empty", data={}, source=ProfileSource.HOME)

        assert profile.data == {}

    def test_construction_with_both_sources(self) -> None:
        """Both origins round-trip: PROJECT for committed, HOME for personal."""
        project_profile = ResolvedProfile(name="mixa", data={}, source=ProfileSource.PROJECT)
        home_profile = ResolvedProfile(name="mixa", data={}, source=ProfileSource.HOME)

        assert project_profile.source is ProfileSource.PROJECT
        assert home_profile.source is ProfileSource.HOME

    def test_name_carried_verbatim(self) -> None:
        """The profile name round-trips verbatim."""
        profile = ResolvedProfile(name="release.2.1-hard", data={}, source=ProfileSource.HOME)

        assert profile.name == "release.2.1-hard"

    def test_equality_of_identical_constructions(self) -> None:
        """Two profiles with identical fields compare equal."""
        first = ResolvedProfile(name="mixa", data={"worker": {"agent": "codex"}}, source=ProfileSource.PROJECT)
        second = ResolvedProfile(name="mixa", data={"worker": {"agent": "codex"}}, source=ProfileSource.PROJECT)

        assert first == second

    def test_inequality_on_differing_source(self) -> None:
        """Profiles differing only in source are distinct values."""
        project_profile = ResolvedProfile(name="mixa", data={}, source=ProfileSource.PROJECT)
        home_profile = ResolvedProfile(name="mixa", data={}, source=ProfileSource.HOME)

        assert project_profile != home_profile
