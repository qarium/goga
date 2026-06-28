from __future__ import annotations

import inspect

from goga.afm import FlowEntry, Source, list_flows


class TestListFlowsContract:
    def test_list_flows_importable_from_facade(self) -> None:
        """list_flows is importable from the goga.afm facade."""
        assert list_flows is not None

    def test_list_flows_returns_list_of_flow_entries(self, tmp_path) -> None:
        """list_flows returns a list whose elements are FlowEntry instances."""
        entries = list_flows(tmp_path / "project_flows", tmp_path / "user_flows")

        assert isinstance(entries, list)
        assert all(isinstance(entry, FlowEntry) for entry in entries)

    def test_list_flows_signature_matches_contract(self) -> None:
        """list_flows exposes the (project_dir, user_dir) signature."""
        signature = inspect.signature(list_flows)
        parameters = list(signature.parameters)

        assert parameters == ["project_dir", "user_dir"]


class TestListFlowsLogic:
    def test_list_flows_returns_entries_from_both_sources(
        self, tmp_path
    ) -> None:
        """Project source wins on name conflicts; user entries are appended."""
        project_dir = tmp_path / "project_flows"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text("project")
        (project_dir / "build.yml").write_text("project")

        user_dir = tmp_path / "user_flows"
        user_dir.mkdir()
        (user_dir / "deploy.yml").write_text("user")
        (user_dir / "test.yml").write_text("user")

        entries = list_flows(project_dir, user_dir)

        assert len(entries) == 3

        names = {entry.name for entry in entries}
        assert names == {"build", "deploy", "test"}

        by_name = {entry.name: entry for entry in entries}
        assert by_name["deploy"].source == Source.PROJECT
        assert by_name["test"].source == Source.USER

    def test_list_flows_orders_project_entries_before_user_entries(
        self, tmp_path
    ) -> None:
        """Project entries precede user entries even when sorted after the user name."""
        project_dir = tmp_path / "project_flows"
        project_dir.mkdir()
        (project_dir / "zeta.yml").write_text("project")

        user_dir = tmp_path / "user_flows"
        user_dir.mkdir()
        (user_dir / "alpha.yml").write_text("user")

        entries = list_flows(project_dir, user_dir)

        assert [entry.name for entry in entries] == ["zeta", "alpha"]
        assert entries[0].source == Source.PROJECT
        assert entries[1].source == Source.USER

    def test_list_flows_treats_missing_directories_as_empty(
        self, tmp_path
    ) -> None:
        """Neither directory existing yields an empty list (no error)."""
        project_dir = tmp_path / "project_flows"
        user_dir = tmp_path / "user_flows"

        entries = list_flows(project_dir, user_dir)

        assert entries == []

    def test_list_flows_ignores_subdirectories(self, tmp_path) -> None:
        """Only top-level *.yml files are discovered (non-recursive scan)."""
        project_dir = tmp_path / "project_flows"
        project_dir.mkdir()
        (project_dir / "top.yml").write_text("top")

        subdir = project_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.yml").write_text("nested")

        user_dir = tmp_path / "user_flows"

        entries = list_flows(project_dir, user_dir)

        assert [entry.name for entry in entries] == ["top"]

    def test_list_flows_skips_files_with_invalid_stem(self, tmp_path) -> None:
        """A stray top-level .yml (stem is not a valid flow name) is skipped, not crashed on."""
        project_dir = tmp_path / "project_flows"
        project_dir.mkdir()
        (project_dir / ".yml").write_text("hidden")
        (project_dir / "deploy.yml").write_text("flow")

        user_dir = tmp_path / "user_flows"
        user_dir.mkdir()
        (user_dir / ".yml").write_text("hidden")

        entries = list_flows(project_dir, user_dir)

        assert [entry.name for entry in entries] == ["deploy"]
