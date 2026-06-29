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
        assert called_args[2] == str(project_pipelines / "deploy.yml")

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

    def test_flow_command_not_registered(self) -> None:
        """The legacy 'flow' command is NOT registered on the app group."""
        assert "flow" not in app.commands

    def test_pipeline_command_registered(self) -> None:
        """The new 'pipeline' command is registered on the app group."""
        assert "pipeline" in app.commands
