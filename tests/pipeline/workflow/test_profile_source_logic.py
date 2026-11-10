"""Logic tests for the ``ProfileSource`` enum.

Covers behavior beyond the contract surface: value serialization of the
members — the str mixin the equality checks, JSON payloads, and dict-key
usage rely on. ``str()``/f-string formatting of a str-mixin enum member is
Python-version-dependent (3.11+ renders the member form) and is NOT part of
the serialization contract; the value-level guarantees below are.
"""

from __future__ import annotations

import json

from goga.pipeline.workflow import ProfileSource


class TestProfileSourceLogic:
    """Logic tests — value serialization of the ``ProfileSource`` members."""

    def test_members_equal_plain_strings(self) -> None:
        """Each member compares equal to its plain string value (str mixin)."""
        assert ProfileSource.PROJECT == "project"
        assert ProfileSource.HOME == "home"

    def test_value_yields_plain_strings(self) -> None:
        """``.value`` yields the plain string of each member."""
        assert ProfileSource.PROJECT.value == "project"
        assert ProfileSource.HOME.value == "home"

    def test_json_payload_serializes_plain(self) -> None:
        """A member flows into a JSON payload as its plain string value."""
        assert json.dumps({"source": ProfileSource.PROJECT}) == '{"source": "project"}'
        assert json.dumps(ProfileSource.HOME) == '"home"'

    def test_string_concatenation_uses_underlying_value(self) -> None:
        """Concatenation uses the underlying string data, not the member form."""
        assert "" + ProfileSource.PROJECT == "project"
        assert "origin-" + ProfileSource.HOME == "origin-home"

    def test_member_usable_as_plain_dict_key(self) -> None:
        """The str mixin keeps a member usable as a plain-string dict key."""
        by_source = {"project": "committed", "home": "personal"}

        assert by_source[ProfileSource.PROJECT] == "committed"
        assert by_source[ProfileSource.HOME] == "personal"

    def test_members_distinct(self) -> None:
        """The two members are distinct values and distinct identities."""
        assert ProfileSource.PROJECT != ProfileSource.HOME
        assert ProfileSource.PROJECT is not ProfileSource.HOME
        assert ProfileSource.PROJECT.value != ProfileSource.HOME.value

    def test_lookup_by_plain_string_value(self) -> None:
        """A member is retrievable by its plain string value."""
        assert ProfileSource("project") is ProfileSource.PROJECT
        assert ProfileSource("home") is ProfileSource.HOME
