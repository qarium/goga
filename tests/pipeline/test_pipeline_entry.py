from __future__ import annotations

import pytest
from goga.pipeline import PipelineEntry, PipelineSource


class TestPipelineEntryContract:
    def test_pipeline_entry_importable_from_facade(self) -> None:
        """PipelineEntry is importable from the goga.pipeline facade."""
        assert PipelineEntry is not None

    def test_pipeline_source_importable_from_facade(self) -> None:
        """PipelineSource enum is importable from the goga.pipeline facade."""
        assert PipelineSource is not None

    def test_pipeline_source_enum_has_project_and_user(self) -> None:
        """PipelineSource exposes PROJECT ("project") and USER ("user") members."""
        assert PipelineSource.PROJECT.value == "project"
        assert PipelineSource.USER.value == "user"

    def test_pipeline_source_inherits_str(self) -> None:
        """PipelineSource is a str-backed enum for serialization compatibility."""
        assert isinstance(PipelineSource.PROJECT, str)

    def test_pipeline_entry_constructs_and_exposes_fields(self) -> None:
        """A well-formed PipelineEntry exposes its name and source."""
        entry = PipelineEntry(name="deploy", source=PipelineSource.PROJECT)

        assert entry.name == "deploy"
        assert entry.source == PipelineSource.PROJECT

    def test_pipeline_entry_rejects_yml_extension(self) -> None:
        """name must not carry the .yml extension."""
        with pytest.raises(ValueError):
            PipelineEntry(name="deploy.yml", source=PipelineSource.PROJECT)

    def test_pipeline_entry_rejects_forward_slash(self) -> None:
        """name must not contain path separators."""
        with pytest.raises(ValueError):
            PipelineEntry(name="a/b", source=PipelineSource.USER)

    def test_pipeline_entry_rejects_positional_args(self) -> None:
        """kw_only is enforced: positional construction is rejected."""
        with pytest.raises(TypeError):
            PipelineEntry("deploy", PipelineSource.PROJECT)


class TestPipelineEntryLogic:
    def test_pipeline_entry_allows_dot_when_not_yml(self) -> None:
        """A dot is allowed as long as the name does not end with .yml."""
        entry = PipelineEntry(name="my.flow", source=PipelineSource.USER)

        assert entry.name == "my.flow"
        assert entry.source == PipelineSource.USER

    def test_pipeline_entry_allows_non_ascii_name(self) -> None:
        """Non-ASCII names are valid as long as they carry no separators."""
        entry = PipelineEntry(name="déploy", source=PipelineSource.PROJECT)

        assert entry.name == "déploy"
        assert entry.source == PipelineSource.PROJECT

    def test_pipeline_entry_rejects_backslash(self) -> None:
        """name must not contain backslash path separators."""
        with pytest.raises(ValueError):
            PipelineEntry(name="a\\b", source=PipelineSource.PROJECT)

    def test_pipeline_entry_rejects_empty_name(self) -> None:
        """name must not be empty."""
        with pytest.raises(ValueError):
            PipelineEntry(name="", source=PipelineSource.PROJECT)
