from __future__ import annotations

import pytest
from goga.afm import FlowEntry, Source
from pydantic import ValidationError


class TestFlowEntryContract:
    def test_flow_entry_importable_from_facade(self) -> None:
        """FlowEntry is importable from the goga.afm facade."""
        assert FlowEntry is not None

    def test_source_importable_from_facade(self) -> None:
        """Source enum is importable from the goga.afm facade."""
        assert Source is not None

    def test_source_enum_has_project_and_user(self) -> None:
        """Source exposes PROJECT ("project") and USER ("user") members."""
        assert Source.PROJECT.value == "project"
        assert Source.USER.value == "user"

    def test_source_inherits_str(self) -> None:
        """Source is a str-backed enum for pydantic serialization compatibility."""
        assert isinstance(Source.PROJECT, str)

    def test_flow_entry_constructs_and_exposes_fields(self) -> None:
        """A well-formed FlowEntry exposes its name and source."""
        entry = FlowEntry(name="deploy", source=Source.PROJECT)

        assert entry.name == "deploy"
        assert entry.source == Source.PROJECT

    def test_flow_entry_rejects_yml_extension(self) -> None:
        """name must not carry the .yml extension."""
        with pytest.raises(ValidationError):
            FlowEntry(name="deploy.yml", source=Source.PROJECT)

    def test_flow_entry_rejects_forward_slash(self) -> None:
        """name must not contain path separators."""
        with pytest.raises(ValidationError):
            FlowEntry(name="a/b", source=Source.USER)

    def test_flow_entry_rejects_positional_args(self) -> None:
        """kw_only is enforced: positional construction is rejected."""
        with pytest.raises((TypeError, ValidationError)):
            FlowEntry("deploy", Source.PROJECT)


class TestFlowEntryLogic:
    def test_flow_entry_allows_dot_when_not_yml(self) -> None:
        """A dot is allowed as long as the name does not end with .yml."""
        entry = FlowEntry(name="my.flow", source=Source.USER)

        assert entry.name == "my.flow"
        assert entry.source == Source.USER

    def test_flow_entry_allows_non_ascii_name(self) -> None:
        """Non-ASCII names are valid as long as they carry no separators."""
        entry = FlowEntry(name="déploy", source=Source.PROJECT)

        assert entry.name == "déploy"
        assert entry.source == Source.PROJECT

    def test_flow_entry_rejects_backslash(self) -> None:
        """name must not contain backslash path separators."""
        with pytest.raises(ValidationError):
            FlowEntry(name="a\\b", source=Source.PROJECT)
