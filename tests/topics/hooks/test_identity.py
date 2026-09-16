"""Contract and logic tests for the entity declared in
``goga/topics/hooks/CODEMANIFEST`` with ``location: identity.py``:
``TopicIdentity(slug, year, branch)`` — the identity vocabulary of every
topics event.

Pure composition — no fixtures, no mocks: the home path derives from the
slug and the year inputs through ``resolve_topic_dir`` and nothing is read
or created.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest
from goga.topics.hooks import TopicIdentity

from tests.conftest import is_kw_only_dataclass

# --- Contract tests ---


class TestTopicIdentityContract:
    def test_entity_is_importable_from_the_zone_facade(self) -> None:
        """The identity lives on the zone package and its ``__all__`` is exact."""
        import goga.topics.hooks as zone

        assert zone.TopicIdentity is TopicIdentity
        assert zone.__all__ == ["TopicIdentity"]

    def test_identity_is_a_kw_only_frozen_dataclass(self) -> None:
        """``TopicIdentity(slug=..., year=..., branch=...)`` — keyword-only, frozen."""
        identity = TopicIdentity(slug="feature-foo", year="2026", branch="feature-foo")

        assert identity.slug == "feature-foo"
        assert identity.year == "2026"
        assert identity.branch == "feature-foo"

        assert dataclasses.is_dataclass(TopicIdentity)
        assert TopicIdentity.__dataclass_params__.frozen
        assert is_kw_only_dataclass(TopicIdentity)

        with pytest.raises(TypeError):
            TopicIdentity("feature-foo", "2026", "feature-foo")  # type: ignore[misc]

    def test_identity_assignment_raises_frozen_instance_error(self) -> None:
        """The identity is read-only fact — no holder rewrites it."""
        identity = TopicIdentity(slug="feature-foo", year="2026", branch="feature-foo")

        with pytest.raises(dataclasses.FrozenInstanceError):
            identity.slug = "other"  # type: ignore[misc]

    def test_identity_carries_the_declared_fields_types_and_properties(self) -> None:
        """``slug``/``year``/``branch`` fields; ``home_path`` the sole computed member."""
        field_names = [field.name for field in dataclasses.fields(TopicIdentity)]
        field_types = typing.get_type_hints(TopicIdentity)

        assert field_names == ["slug", "year", "branch"]
        assert field_types["slug"] == str | None
        assert field_types["year"] is str
        assert field_types["branch"] == str | None
        assert isinstance(TopicIdentity.home_path, property)
        assert typing.get_type_hints(TopicIdentity.home_path.fget)["return"] == str | None


# --- Logic tests ---


class TestTopicIdentityComposition:
    def test_topic_identity_home_path_composes_purely(self) -> None:
        """The canonical addressing fact every notification carries.

        The composition runs through ``resolve_topic_dir`` — re-normalizing
        an already-normalized slug is the identity — and returns the posix
        string of the topic directory.
        """
        identity = TopicIdentity(
            slug="add-topics-hooks",
            year="2026",
            branch="add-topics-hooks",
        )

        assert identity.home_path == ".goga/history/2026/add-topics-hooks"
        assert identity.slug == "add-topics-hooks"
        assert identity.branch == "add-topics-hooks"

    def test_branch_only_form_has_no_home_path(self) -> None:
        """A switch onto a branch hosting no topic — slug None, home path None."""
        identity = TopicIdentity(slug=None, year="2026", branch="bare-branch")

        assert identity.slug is None
        assert identity.home_path is None
        assert identity.branch == "bare-branch"

    def test_deletion_form_keeps_the_home_path_composed(self) -> None:
        """The deletion context carries no branch fact — slug and home path stay."""
        identity = TopicIdentity(slug="feature-foo", year="2026", branch=None)

        assert identity.branch is None
        assert identity.home_path == ".goga/history/2026/feature-foo"
