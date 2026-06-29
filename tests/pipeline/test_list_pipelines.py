from __future__ import annotations

import inspect

from goga.pipeline import PipelineEntry, PipelineSource, list_pipelines


class TestListPipelinesContract:
    def test_list_pipelines_importable_from_facade(self) -> None:
        """list_pipelines is importable from the goga.pipeline facade."""
        assert list_pipelines is not None

    def test_list_pipelines_returns_list_of_pipeline_entries(self, tmp_path) -> None:
        """list_pipelines returns a list whose elements are PipelineEntry instances."""
        entries = list_pipelines(tmp_path / "project_pipelines", tmp_path / "user_pipelines")

        assert isinstance(entries, list)
        assert all(isinstance(entry, PipelineEntry) for entry in entries)

    def test_list_pipelines_signature_matches_contract(self) -> None:
        """list_pipelines exposes the (project_dir, user_dir) signature."""
        signature = inspect.signature(list_pipelines)
        parameters = list(signature.parameters)

        assert parameters == ["project_dir", "user_dir"]


class TestListPipelinesLogic:
    def test_list_pipelines_returns_entries_from_both_sources(
        self, tmp_path
    ) -> None:
        """Project source wins on name conflicts; user entries are appended."""
        project_dir = tmp_path / "project_pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("project")
        (project_dir / "build.yml").write_text("project")

        user_dir = tmp_path / "user_pipelines"
        user_dir.mkdir()
        (user_dir / "deploy.yml").write_text("user")
        (user_dir / "test.yml").write_text("user")

        entries = list_pipelines(project_dir, user_dir)

        assert len(entries) == 3

        names = {entry.name for entry in entries}
        assert names == {"build", "deploy", "test"}

        by_name = {entry.name: entry for entry in entries}
        assert by_name["deploy"].source == PipelineSource.PROJECT
        assert by_name["test"].source == PipelineSource.USER

    def test_list_pipelines_orders_project_entries_before_user_entries(
        self, tmp_path
    ) -> None:
        """Project entries precede user entries even when sorted after the user name."""
        project_dir = tmp_path / "project_pipelines"
        project_dir.mkdir()
        (project_dir / "zeta.yml").write_text("project")

        user_dir = tmp_path / "user_pipelines"
        user_dir.mkdir()
        (user_dir / "alpha.yml").write_text("user")

        entries = list_pipelines(project_dir, user_dir)

        assert [entry.name for entry in entries] == ["zeta", "alpha"]
        assert entries[0].source == PipelineSource.PROJECT
        assert entries[1].source == PipelineSource.USER

    def test_list_pipelines_treats_missing_directories_as_empty(
        self, tmp_path
    ) -> None:
        """Neither directory existing yields an empty list (no error)."""
        project_dir = tmp_path / "project_pipelines"
        user_dir = tmp_path / "user_pipelines"

        entries = list_pipelines(project_dir, user_dir)

        assert entries == []

    def test_list_pipelines_ignores_subdirectories(self, tmp_path) -> None:
        """Only top-level *.yml files are discovered (non-recursive scan)."""
        project_dir = tmp_path / "project_pipelines"
        project_dir.mkdir()
        (project_dir / "top.yml").write_text("top")

        subdir = project_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.yml").write_text("nested")

        user_dir = tmp_path / "user_pipelines"

        entries = list_pipelines(project_dir, user_dir)

        assert [entry.name for entry in entries] == ["top"]

    def test_list_pipelines_skips_files_with_invalid_stem(self, tmp_path) -> None:
        """Stems that fail PipelineEntry validation are skipped, not crashed on.

        Covers two distinct rejection paths: an empty stem (``.yml``) and a
        stem that ends with ``.yml`` (``weird.yml.yml`` → stem ``weird.yml``).
        """
        project_dir = tmp_path / "project_pipelines"
        project_dir.mkdir()
        (project_dir / "valid.yml").write_text("pipeline")
        (project_dir / ".yml").write_text("empty-stem")
        (project_dir / "weird.yml.yml").write_text("yml-suffix-stem")

        user_dir = tmp_path / "user_pipelines"
        user_dir.mkdir()
        (user_dir / ".yml").write_text("hidden")

        entries = list_pipelines(project_dir, user_dir)

        assert [entry.name for entry in entries] == ["valid"]

    def test_list_pipelines_ignores_non_yml_files(self, tmp_path) -> None:
        """Only ``*.yml`` files are discovered — ``.yaml``, ``.txt``, and extensionless files are skipped."""
        project_dir = tmp_path / "project_pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("pipeline")
        (project_dir / "staging.yaml").write_text("ignored-yaml")
        (project_dir / "notes.txt").write_text("ignored-txt")
        (project_dir / "extensionless").write_text("ignored-noext")

        user_dir = tmp_path / "user_pipelines"

        entries = list_pipelines(project_dir, user_dir)

        assert [entry.name for entry in entries] == ["deploy"]
