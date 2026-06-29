"""End-to-end integration tests for the ``pipeline`` CLI command.

These exercise the full cross-cell path through the root ``app`` group:

    goga pipeline <name> -> pipeline.run -> goga.pipeline.run_pipeline
                                          -> goga.afm.run_flow
                                          -> subprocess.run(["flowmanager", ...])
    goga pipeline         -> pipeline.discovery -> goga.pipeline.list_pipelines -> filesystem

The ``flowmanager`` binary is mocked at the subprocess boundary (inside
``goga.afm.run_flow``) so the real binary is never invoked. The pipeline command
is registered on ``app`` under the name ``pipeline``.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

from click.testing import CliRunner
from goga.cli import app


class TestPipelineCliCrossEntity:
    def test_run_invokes_flowmanager_with_absolute_path(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """goga pipeline <name> reaches run_flow and passes the absolute pipeline path."""
        project_tmp = tmp_path / "project"
        project_tmp.mkdir()
        user_tmp = tmp_path / "user"
        user_tmp.mkdir()

        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "deploy.yml").write_text("pipeline")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        runner = CliRunner()
        with mock.patch(
            "goga.afm.run_flow.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            result = runner.invoke(app, ["pipeline", "deploy"])

        assert result.exit_code == 0
        mock_subprocess.assert_called_once()
        called_args = mock_subprocess.call_args.args[0]
        assert called_args[0] == "flowmanager"
        assert called_args[1] == "run"
        # The absolute pipeline path (not the bare name) reaches the binary.
        # run_pipeline .resolve()s the path; assert against the resolved form.
        assert called_args[2] == str((project_pipelines / "deploy.yml").resolve())

    def test_run_missing_pipeline_is_nonzero_without_subprocess(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """goga pipeline <missing> returns nonzero without invoking flowmanager."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        with mock.patch("goga.afm.run_flow.subprocess.run") as mock_subprocess:
            result = runner.invoke(app, ["pipeline", "missing"])

        assert result.exit_code != 0
        mock_subprocess.assert_not_called()

    def test_run_propagates_nonzero_flowmanager_exit_code(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """goga pipeline <name> propagates a non-zero flowmanager exit code via ctx.exit."""
        project_tmp = tmp_path / "project"
        project_tmp.mkdir()
        user_tmp = tmp_path / "user"
        user_tmp.mkdir()

        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "deploy.yml").write_text("pipeline")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        runner = CliRunner()
        with mock.patch(
            "goga.afm.run_flow.subprocess.run",
            return_value=MagicMock(returncode=7),
        ):
            result = runner.invoke(app, ["pipeline", "deploy"])

        # The flowmanager exit code flows run_pipeline -> ctx.exit verbatim.
        assert result.exit_code == 7

    def test_run_resolves_project_source_on_name_conflict(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """When a name exists in both sources, the project pipeline path reaches flowmanager."""
        project_tmp = tmp_path / "project"
        project_tmp.mkdir()
        user_tmp = tmp_path / "user"
        user_tmp.mkdir()

        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "shared.yml").write_text("project-shared")

        user_pipelines = user_tmp / ".goga" / "pipelines"
        user_pipelines.mkdir(parents=True)
        (user_pipelines / "shared.yml").write_text("user-shared")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        runner = CliRunner()
        with mock.patch(
            "goga.afm.run_flow.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            result = runner.invoke(app, ["pipeline", "shared"])

        assert result.exit_code == 0
        called_args = mock_subprocess.call_args.args[0]
        # Project wins on conflict: the project path (not the user path) reaches the binary.
        assert called_args[2] == str((project_pipelines / "shared.yml").resolve())

    def test_run_with_yml_suffix_name_is_not_found(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """goga pipeline deploy.yml does NOT strip the suffix — 'deploy.yml' never matches entry 'deploy'."""
        project_tmp = tmp_path / "project"
        project_tmp.mkdir()
        user_tmp = tmp_path / "user"
        user_tmp.mkdir()

        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "deploy.yml").write_text("pipeline")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        runner = CliRunner()
        with mock.patch("goga.afm.run_flow.subprocess.run") as mock_subprocess:
            result = runner.invoke(app, ["pipeline", "deploy.yml"])

        # The CLI layer does not strip .yml; run_pipeline finds no 'deploy.yml' entry → exit 1.
        assert result.exit_code == 1
        mock_subprocess.assert_not_called()
        assert "not found" in result.output


class TestPipelineCliList:
    def test_discovery_mode_marks_project_pipelines_only(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """goga pipeline (no name) annotates project pipelines with (project) and user pipelines bare."""
        project_tmp = tmp_path / "project"
        project_tmp.mkdir()
        user_tmp = tmp_path / "user"
        user_tmp.mkdir()

        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "deploy.yml").write_text("pipeline")

        user_pipelines = user_tmp / ".goga" / "pipelines"
        user_pipelines.mkdir(parents=True)
        (user_pipelines / "build.yml").write_text("pipeline")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        runner = CliRunner()
        result = runner.invoke(app, ["pipeline"])

        assert result.exit_code == 0
        assert "Available pipelines:" in result.output
        assert "deploy (project)" in result.output
        assert "build" in result.output
        assert "build (project)" not in result.output

    def test_discovery_project_wins_on_name_conflict(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A name present in both sources appears once, as the project pipeline."""
        project_tmp = tmp_path / "project"
        project_tmp.mkdir()
        user_tmp = tmp_path / "user"
        user_tmp.mkdir()

        project_pipelines = project_tmp / ".goga" / "pipelines"
        project_pipelines.mkdir(parents=True)
        (project_pipelines / "shared.yml").write_text("project-shared")

        user_pipelines = user_tmp / ".goga" / "pipelines"
        user_pipelines.mkdir(parents=True)
        (user_pipelines / "shared.yml").write_text("user-shared")

        monkeypatch.setattr(Path, "cwd", lambda: project_tmp)
        monkeypatch.setattr(Path, "home", lambda: user_tmp)

        runner = CliRunner()
        result = runner.invoke(app, ["pipeline"])

        assert result.exit_code == 0
        assert "Available pipelines:" in result.output
        # The project entry wins and is annotated; the user duplicate is suppressed.
        assert "shared (project)" in result.output
        assert result.output.count("shared") == 1

    def test_discovery_mode_prints_header_when_empty(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The 'Available pipelines:' header is printed before an empty list."""
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(app, ["pipeline"])

        assert result.exit_code == 0
        assert "Available pipelines:" in result.output

    def test_flow_command_not_registered(self) -> None:
        """The legacy 'flow' command is NOT registered on the app group."""
        assert "flow" not in app.commands

    def test_pipeline_command_registered(self) -> None:
        """The new 'pipeline' command is registered on the app group."""
        assert "pipeline" in app.commands

    def test_root_help_lists_pipeline_not_flow(self) -> None:
        """goga --help lists the 'pipeline' command and does NOT list 'flow' (Task 8 contract)."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "pipeline" in result.output
        assert "flow" not in result.output
